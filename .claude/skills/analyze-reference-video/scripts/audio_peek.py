# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
# /// script
# dependencies = ["numpy", "scipy", "pillow"]
# ///
"""Look at sound as numbers and pictures, because Claude cannot hear.

Each subcommand reads any audio or video file (ffmpeg decodes it to mono 48 kHz) and prints text Claude can read.
All levels are RMS dBFS. A pause in a voice track is about -45 dB or lower; speech is -35 to -10;
after Concat's denoise a pause can be digital silence (-90 or less), so never compare against 0.

  env      FILE --from A --to B [--step 0.04]     level every STEP s ("12.34:-31")
  silences FILE [--thr -45] [--min 0.25]          every silence of at least MIN s: start,length
  cuts     FILE T1 T2 ...                         level of the last 80 ms before each time and the 80 ms before
                                                  that: a clip that ends on a word is still loud (> -38 dB).
  lead     FILE T1 T2 ... [--thr -34]             seconds of quiet AFTER each time (dead air at the start of a clip)
  tail     FILE T1 T2 ... [--thr -34]             seconds of quiet BEFORE each time (dead air at the end of a clip)
  spec     FILE --from A --to B [--fmax 4000] --out spec.png     spectrogram picture (voice = stripes, noise = haze)
  tones    FILE --from A --to B                   steady tones in a pause (a motor hum at 68/136/204 Hz) to find
                                                  what to filter; pass a window with no voice in it

Typical uses
  * Link a transcript to real time: Whisper times drift on long files; take the word's time, then `env` around it
    to find where the voice really starts and dies (the voice is where the level rises 15 dB over the pause).
  * Check every cut of an export: `cuts export.mp4 4.90 11.30 21.37` -> any "last80ms" above -38 dB means the
    clip was cut while a word was still sounding; extend the end (up to 0.8 s) until it is under -38 dB.
  * Find a pause the user calls too long: `silences export.mp4 --thr -45 --min 0.25`.
  * Decide where a clip may start: `lead raw.mov 18.98` says how much dead air there is after that time.
"""
import argparse
import subprocess
import sys

import numpy as np

SR = 48000


def load(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if not r.stdout:
        sys.exit(f"no audio in {path}")
    return np.frombuffer(r.stdout, np.float32).astype(np.float64)


def lv(x, a, b):
    s = x[max(0, int(a * SR)):int(b * SR)]
    return 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9) if len(s) else -99.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["env", "silences", "cuts", "lead", "tail", "spec", "tones"])
    ap.add_argument("file")
    ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--step", type=float, default=0.04)
    ap.add_argument("--thr", type=float)
    ap.add_argument("--min", dest="minlen", type=float, default=0.25)
    ap.add_argument("--fmax", type=float, default=4000)
    ap.add_argument("--out")
    a = ap.parse_args()
    x = load(a.file)
    dur = len(x) / SR
    t1 = a.t1 if a.t1 is not None else dur

    if a.cmd == "env":
        t = a.t0
        out = []
        while t < t1:
            out.append(f"{t:.2f}:{lv(x, t, t + a.step):.0f}")
            t += a.step
        print(" ".join(out))
    elif a.cmd == "silences":
        thr = -45 if a.thr is None else a.thr
        hop = int(SR * 0.02)
        levels = [20 * np.log10(np.sqrt((x[i:i + hop] ** 2).mean()) + 1e-9) for i in range(0, len(x) - hop, hop)]
        runs, s = [], None
        for i, v in enumerate(levels + [0]):
            if v < thr and s is None:
                s = i
            if v >= thr and s is not None:
                if (i - s) * 0.02 >= a.minlen:
                    runs.append((round(s * 0.02, 2), round((i - s) * 0.02, 2)))
                s = None
        print(f"silences >= {a.minlen}s under {thr} dB (start, length):", runs)
    elif a.cmd == "cuts":
        for t in a.times:
            last, before = lv(x, t - 0.08, t), lv(x, t - 0.16, t - 0.08)
            flag = "  <-- cut while a word still sounds" if last > -38 else ""
            print(f"cut {t:.2f}: last80ms {last:.0f} dB | before {before:.0f} dB{flag}")
    elif a.cmd in ("lead", "tail"):
        thr = -34 if a.thr is None else a.thr
        for t in a.times:
            lim, step = 1.0, 0.02
            q = 0.0
            if a.cmd == "lead":
                while q < lim and lv(x, t + q, t + q + step) <= thr:
                    q += step
            else:
                while q < lim and lv(x, t - q - step, t - q) <= thr:
                    q += step
            print(f"{a.cmd} at {t:.2f}: {q:.2f} s of quiet (limit {lim}, threshold {thr} dB)")
    elif a.cmd == "spec":
        from PIL import Image
        from scipy.signal import spectrogram
        seg = x[int(a.t0 * SR):int(t1 * SR)]
        f, t, S = spectrogram(seg, SR, nperseg=4096, noverlap=3072)
        S = 10 * np.log10(S + 1e-14)[f < a.fmax][::-1]
        img = np.clip((S + 110) / 50, 0, 1)
        Image.fromarray((img * 255).astype(np.uint8)).resize((1000, 350)).save(a.out or "spec.png")
        print(a.out or "spec.png", f"{a.t0:.1f}-{t1:.1f}s up to {a.fmax:.0f} Hz; rms {20*np.log10(np.sqrt((seg**2).mean())+1e-9):.1f} dBFS")
    elif a.cmd == "tones":
        seg = x[int(a.t0 * SR):int(t1 * SR)]
        n = 2 ** int(np.floor(np.log2(len(seg))))
        sp = np.abs(np.fft.rfft(seg[:n] * np.hanning(n)))
        fr = np.fft.rfftfreq(n, 1 / SR)
        db = 20 * np.log10(sp + 1e-9)
        peaks = []
        for i in range(2, len(fr) - 2):
            if fr[i] < 40 or fr[i] > 2000:
                continue
            w = db[max(0, i - 120):i + 120]
            if db[i] == db[i - 2:i + 3].max() and db[i] - np.median(w) > 12:
                peaks.append((round(float(fr[i]), 1), round(float(db[i] - np.median(w)), 1)))
        print("tones (Hz, dB above the surrounding floor):", peaks[:20])


if __name__ == "__main__":
    main()

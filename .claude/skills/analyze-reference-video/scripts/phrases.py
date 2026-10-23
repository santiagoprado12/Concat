#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy"]
# ///
"""List every spoken phrase of a long recording with exact times and its own transcript.

  uv run phrases.py RAW --model ggml-base.bin --out DIR [--lang es] [--gap 0.45]

For raw footage with many retakes. Whisper's word timestamps drift on long files (a 5-minute take
was off by up to 5 s, and several words share one time), so the times come from energy instead:
the voice is the part of the track within 14 dB of the speaking level, small holes (<0.12 s) are
closed, and regions separated by less than --gap seconds are one phrase. Each phrase is then cut out
and transcribed by itself with whisper.cpp, so the text is attached to exact times.

Writes DIR/vad.json (regions, for takes_to_plan.py --vad) and DIR/phrases.json, and prints one line per
phrase. Read the list and pick the best take of each line (usually the last complete one; a take whose
transcript is clean is a good sign, a trailing fragment is a bad one). Needs ffmpeg and whisper-cli
(brew install whisper-cpp) and a ggml model file; nothing is downloaded here.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

SR, HOP = 16000, 160


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--gap", type=float, default=0.45)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a.raw), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    y = np.frombuffer(p.stdout, dtype=np.float32)
    db = 20 * np.log10(np.sqrt(np.convolve(y ** 2, np.ones(HOP) / HOP, mode="same")[::HOP] + 1e-12))
    level = float(np.percentile(db[db > -60], 85))
    voiced = db > level - 14
    regs, i, n = [], 0, len(voiced)
    while i < n:
        if voiced[i]:
            j = i
            while j < n and voiced[j]:
                j += 1
            regs.append([i, j])
            i = j
        else:
            i += 1
    merged: list[list[int]] = []
    for r in regs:
        if merged and r[0] - merged[-1][1] < 12:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    regions = [[s / 100, e / 100] for s, e in merged if e - s >= 8]
    (a.out / "vad.json").write_text(json.dumps({"level": level, "thr": level - 14, "regions": regions}))

    phrases: list[list[float]] = []
    for s, e in regions:
        if phrases and s - phrases[-1][1] < a.gap:
            phrases[-1][1] = e
        else:
            phrases.append([s, e])
    (a.out / "phr").mkdir(exist_ok=True)
    out = []
    for k, (s, e) in enumerate(phrases):
        wav = a.out / "phr" / f"p{k:02d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(s - 0.25, 0):.2f}", "-t", f"{e - s + 0.5:.2f}",
                        "-i", str(a.raw), "-vn", "-ac", "1", "-ar", str(SR), str(wav)])
        r = subprocess.run(["whisper-cli", "-m", str(a.model), "-l", a.lang, "-f", str(wav), "-nt", "-np"],
                           capture_output=True, text=True)
        text = " ".join(r.stdout.split())
        out.append({"i": k, "start": s, "end": e, "text": text})
        print(f"{k:3d} {s:7.2f}-{e:7.2f} ({e - s:4.1f}s) {text}")
    (a.out / "phrases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

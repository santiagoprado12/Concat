#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "librosa"]
# ///
"""Find which stretches of the RAW recording the EDITED video's sound was cut from.

  uv run align_audio.py RAW EDITED --out DIR [--shots DIR/shots.json]

Use this when the footage is mostly one person talking (so pictures all look alike and
align.py cannot tell shots apart) or when the edit keeps the voice but cuts the picture away.
The edited audio is compared with the raw audio on log-mel features, window by window; runs of
windows that sit at the same raw offset become one *segment*: edited [a, b] <- raw [a+d, b+d].
Cut points are then refined to ~10 ms. If shots.json is given, every edited shot is also tagged
`talking_head` (the picture matches the raw picture at the aligned time) or `other` (B-roll, a
screenshot, an overlay) by comparing 16x9 thumbnails.

Writes audio_alignment.json. Needs ffmpeg. Reads both files' audio; nothing leaves the machine.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np

SR, HOP, NMEL = 16000, 160, 40  # 10 ms frames
FPS_F = SR / HOP


def load(path: Path) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if p.returncode:
        sys.exit(p.stderr.decode())
    return np.frombuffer(p.stdout, dtype=np.float32)


def feats(y: np.ndarray) -> np.ndarray:
    m = librosa.feature.melspectrogram(y=y, sr=SR, n_fft=400, hop_length=HOP, n_mels=NMEL, fmin=60, fmax=7500)
    return librosa.power_to_db(m + 1e-10).T.astype(np.float64)  # (frames, bands)


def cos_scan(raw: np.ndarray, win: np.ndarray) -> np.ndarray:
    """Cosine similarity of `win` (W x B, mean removed) with every W-frame slice of `raw` (T x B)."""
    t, b = raw.shape
    w = win.shape[0]
    n = 1 << int(np.ceil(np.log2(t + w)))
    num = np.zeros(t - w + 1)
    for j in range(b):
        c = np.fft.irfft(np.fft.rfft(raw[:, j], n) * np.fft.rfft(win[::-1, j], n), n)
        num += c[w - 1:t]
    cs1 = np.concatenate([[0], np.cumsum(raw.sum(axis=1))])
    cs2 = np.concatenate([[0], np.cumsum((raw ** 2).sum(axis=1))])
    cnt = w * b
    s1 = cs1[w:] - cs1[:-w]
    s2 = cs2[w:] - cs2[:-w]
    var = s2 - s1 ** 2 / cnt
    den = np.sqrt(np.maximum(var, 1e-9)) * np.sqrt((win ** 2).sum())
    return num / den


def frame_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    return (a * b).sum(axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-9)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path)
    ap.add_argument("edited", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shots", type=Path)
    ap.add_argument("--win", type=float, default=1.0, help="window length in seconds")
    ap.add_argument("--hop", type=float, default=0.25)
    ap.add_argument("--min-score", type=float, default=0.55)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    R, E = feats(load(a.raw)), feats(load(a.edited))
    mu = R.mean(axis=0)
    R, E = R - mu, E - E.mean(axis=0)
    W, H = int(a.win * FPS_F), int(a.hop * FPS_F)
    wins = []
    for s in range(0, len(E) - W + 1, H):
        win = E[s:s + W]
        win = win - win.mean()
        sc = cos_scan(R, win)
        k = int(sc.argmax())
        guard = int(0.4 * FPS_F)
        mask = np.ones(len(sc), bool)
        mask[max(0, k - guard):k + guard] = False
        wins.append({"e": s / FPS_F, "d": (k - s) / FPS_F, "score": float(sc[k]),
                     "margin": float(sc[k] - sc[mask].max()) if mask.any() else 1.0})
    good = [w for w in wins if w["score"] >= a.min_score and w["margin"] >= 0.04]

    # runs of windows at the same raw offset
    runs: list[list[dict]] = []
    for w in good:
        if runs and abs(runs[-1][-1]["d"] - w["d"]) <= 0.05 and w["e"] - runs[-1][-1]["e"] <= a.hop * 4 + 1e-6:
            runs[-1].append(w)
        else:
            runs.append([w])
    segs = [{"d": float(np.median([w["d"] for w in r])), "e0": r[0]["e"], "e1": r[-1]["e"] + a.win,
             "score": float(np.mean([w["score"] for w in r]))} for r in runs if len(r) >= 2]
    segs.sort(key=lambda s: s["e0"])

    # refine the boundary between neighbours, and stretch the first and last segment to the file's ends
    dur_e = len(E) / FPS_F
    for left, right in zip(segs, segs[1:]):
        lo, hi = left["e1"] - a.win * 0.5, right["e0"] + a.win * 0.5
        flo, fhi = int(max(lo, 0) * FPS_F), int(min(hi, dur_e) * FPS_F)
        fidx = np.arange(flo, fhi)
        def sims(d):
            rf = np.clip(fidx + int(round(d * FPS_F)), 0, len(R) - 1)
            return frame_sim(E[fidx], R[rf])
        sa, sb = sims(left["d"]), sims(right["d"])
        best = int(np.argmax(np.concatenate([[0], np.cumsum(sa)])[:len(sa) + 1] +
                             (np.sum(sb) - np.concatenate([[0], np.cumsum(sb)])[:len(sb) + 1])))
        cut = (flo + best) / FPS_F
        left["e1"] = right["e0"] = round(cut, 3)
    if segs:
        segs[0]["e0"] = 0.0
        segs[-1]["e1"] = round(dur_e, 3)
    out_segs = []
    for s in segs:
        out_segs.append({"edited_start": round(s["e0"], 3), "edited_end": round(s["e1"], 3),
                         "raw_start": round(s["e0"] + s["d"], 3), "raw_end": round(s["e1"] + s["d"], 3),
                         "duration": round(s["e1"] - s["e0"], 3), "score": round(s["score"], 2)})
    covered = sum(s["duration"] for s in out_segs)
    result = {"edited_duration": round(dur_e, 3), "covered_seconds": round(covered, 2),
              "windows": len(wins), "confident_windows": len(good), "segments": out_segs}

    if a.shots and a.shots.exists():
        result["shots"] = tag_shots(a, json.loads(a.shots.read_text())["shots"], out_segs)
    (a.out / "audio_alignment.json").write_text(json.dumps(result, indent=2))
    print(f"{len(out_segs)} segments cover {covered:.1f}s of {dur_e:.1f}s edited audio -> {a.out / 'audio_alignment.json'}")
    for s in out_segs:
        print(f"edited {s['edited_start']:7.2f}-{s['edited_end']:7.2f}  <- raw {s['raw_start']:7.2f}-{s['raw_end']:7.2f}  score {s['score']}")
    for s in result.get("shots", []):
        print(f"shot {s['index']:>3} {s['start']:6.2f}-{s['end']:6.2f}: {s['kind']} (picture diff {s['picture_diff']})")


def thumbs(video: Path, times: list[float]) -> np.ndarray:
    out = []
    for t in times:
        p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=16:9:flags=area,format=gray", "-f", "rawvideo", "-"], capture_output=True)
        out.append(np.frombuffer(p.stdout, np.uint8).astype(np.float32) if len(p.stdout) == 144 else np.full(144, 255.0))
    return np.array(out)


def tag_shots(a, shots: list[dict], segs: list[dict]) -> list[dict]:
    def raw_time(t: float):
        for s in segs:
            if s["edited_start"] - 1e-3 <= t <= s["edited_end"] + 1e-3:
                return t + (s["raw_start"] - s["edited_start"])
        return None
    mids = [(s["start"] + s["end"]) / 2 for s in shots]
    rts = [raw_time(t) for t in mids]
    et = thumbs(a.edited, mids)
    rt = thumbs(a.raw, [r if r is not None else 0 for r in rts])
    res = []
    for s, r, e, rr in zip(shots, rts, et, rt):
        diff = float(np.abs(e - rr).mean()) if r is not None else None
        kind = "unknown" if diff is None else ("talking_head" if diff < 14 else "other")
        res.append({"index": s["index"], "start": s["start"], "end": s["end"], "raw_time": None if r is None else round(r, 3),
                    "picture_diff": None if diff is None else round(diff, 1), "kind": kind})
    return res


if __name__ == "__main__":
    main()

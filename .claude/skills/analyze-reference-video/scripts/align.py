#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy"]
# ///
"""Find where each shot of an EDITED video comes from in the RAW footage.

  uv run align.py RAW EDITED --out DIR [--shots DIR_OF_EDITED_ANALYSIS/shots.json]

Both videos are reduced to 16x9 grey thumbnails. Each edited shot is sampled at 15%, 50% and 85%
of its length and matched against the raw footage, giving the source in/out and the playback speed.
Zooms, crops, heavy colour grades and overlays lower the match quality; `confidence` says so.
Writes alignment.json. Reads shots.json (from analyze.py) for the edited cut list.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H = 16, 9


def thumbs(video: Path, fps: float) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-an",
                        "-vf", f"fps={fps},scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    if p.returncode:
        sys.exit(p.stderr.decode())
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape(-1, W * H).astype(np.float32)


def best(raw: np.ndarray, probe: np.ndarray, step: float) -> tuple[float, float, float]:
    """(raw time, mean abs difference, margin to the best match elsewhere)."""
    d = np.abs(raw - probe).mean(axis=1)
    i = int(d.argmin())
    guard = max(1, int(0.6 / step))
    mask = np.ones(len(d), bool)
    mask[max(0, i - guard):i + guard + 1] = False
    second = float(d[mask].min()) if mask.any() else float("inf")
    return i * step, float(d[i]), second - float(d[i])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path)
    ap.add_argument("edited", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shots", type=Path, help="shots.json of the edited video (default: OUT/../edited/shots.json)")
    ap.add_argument("--fps", type=float, default=10.0, help="sampling rate of the raw footage")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    shots_path = a.shots or a.out / "shots.json"
    shots = json.loads(shots_path.read_text())["shots"]

    raw = thumbs(a.raw.expanduser(), a.fps)
    ed_fps = 25.0
    ed = thumbs(a.edited.expanduser(), ed_fps)
    step = 1 / a.fps
    out = []
    for s in shots:
        dur = s["end"] - s["start"]
        ts = [s["start"] + dur * f for f in (0.15, 0.5, 0.85)]
        hits = []
        for t in ts:
            k = min(int(t * ed_fps), len(ed) - 1)
            hits.append(best(raw, ed[k], step))
        r = [h[0] for h in hits]
        dist = float(np.mean([h[1] for h in hits]))
        margin = float(np.min([h[2] for h in hits]))
        span_e, span_r = ts[2] - ts[0], r[2] - r[0]
        speed = span_r / span_e if span_e > 0.2 and r[2] > r[0] else None
        consistent = speed is not None and 0.2 < speed < 5 and abs(r[1] - (r[0] + (ts[1] - ts[0]) * speed)) < 0.5
        if not consistent:
            speed = 1.0
        raw_in = r[1] - (ts[1] - s["start"]) * speed
        conf = "high" if dist < 8 and margin > 6 and consistent else ("medium" if dist < 18 and margin > 2 else "low")
        out.append({"shot": s["index"], "edited_start": s["start"], "edited_end": s["end"],
                    "raw_in": round(max(raw_in, 0), 2), "raw_out": round(raw_in + dur * speed, 2),
                    "speed": round(speed, 3), "match_distance": round(dist, 1), "margin": round(margin, 1),
                    "confidence": conf})
    (a.out / "alignment.json").write_text(json.dumps(out, indent=2))
    from collections import Counter
    print(dict(Counter(o["confidence"] for o in out)), f"-> {a.out / 'alignment.json'}")
    for o in out:
        print(f"shot {o['shot']:>3}: edited {o['edited_start']:.2f}-{o['edited_end']:.2f}s <- raw "
              f"{o['raw_in']:.2f}-{o['raw_out']:.2f}s x{o['speed']} [{o['confidence']}]")


if __name__ == "__main__":
    main()

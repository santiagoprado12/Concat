#!/usr/bin/env python3
# /// script
# dependencies = ["numpy"]
# ///
"""Tiny grayscale thumbnails of a video region over time, to measure how visible a cut would be.

  uv run frame_descriptors.py VIDEO --out desc.npy [--crop X:Y:W:H] [--fps 10] [--size 48x72]
  uv run frame_descriptors.py --diff desc.npy T1 T2 [--fps 10]      # difference between two times

The number is the mean absolute pixel difference (0-255) between two thumbnails of the same region.
Measured on a locked-off shot of one person (see learnings.md, 2026-11-07):
  * two frames 0.1 s apart in a calm moment: 1 to 3
  * two frames 1 s apart in a calm moment: 8 to 12
  * cuts a human accepted as invisible in a reel: 4.8 to 10.6
  * cuts a human called "jumps": 12 and above
So choose the end of one clip and the start of the next so the difference is under about 9, and make the
cut where the person is still (low motion), which this number does not see by itself.
Region: use the same crop for both frames; crop to the person (not the whole frame) so the static
background does not dilute the number.
"""
import argparse
import subprocess
from pathlib import Path

import numpy as np


def probe_size(video: Path) -> tuple[int, int]:
    import json
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    rot = next((abs(int(d["rotation"])) for d in s.get("side_data_list", []) if "rotation" in d), 0)
    return (s["height"], s["width"]) if rot in (90, 270) else (s["width"], s["height"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--crop", default="0:0:1:1", help="X:Y:W:H as fractions of the (rotated) frame")
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--size", default="48x72")
    ap.add_argument("--diff", nargs=3, metavar=("DESC.npy", "T1", "T2"))
    a = ap.parse_args()

    if a.diff:
        d = np.load(a.diff[0])
        i, j = (int(round(float(t) * a.fps)) for t in a.diff[1:])
        print(f"{float(np.abs(d[i] - d[j]).mean()):.1f}")
        return
    if not a.video or not a.out:
        ap.error("VIDEO and --out are required")
    fw, fh = probe_size(a.video)
    x, y, w, h = (float(v) for v in a.crop.split(":"))
    tw, th = (int(v) for v in a.size.split("x"))
    vf = (f"fps={a.fps},crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={tw}:{th},format=gray")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a.video), "-vf", vf, "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, tw * th).astype(np.float32)
    np.save(a.out, arr)
    print(f"{arr.shape[0]} thumbnails of {tw}x{th} -> {a.out}")


if __name__ == "__main__":
    main()

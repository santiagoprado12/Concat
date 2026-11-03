# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Jareer Abdullah and Concat contributors
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Recover how an edit framed and graded the raw footage, as Concat `clip_transform` and colour numbers.

Give it pairs of frames of the same moment, both scaled to the project size (1080x1920 by default):
a frame of the raw footage and the matching frame of the finished edit (for a phone screen
recording of an editor's preview, crop the 9:16 preview area first and scale it up). It matches
SIFT features, fits a similarity transform with RANSAC (so a moving person does not matter, the
static room does) and prints:

  scale, rotation (degrees, positive = clockwise, the sign Concat's `rotation` uses) and offsetX/offsetY
  (fractions of the frame width/height, positive right/down) for `clip_transform`;
  per-channel gains of the edit over the warped raw (B, G, R), the saturation ratio and the luma ratio
  in stops, measured on pixels that agree (text, people and other overlays are excluded by a
  difference mask and by `--skip-top`/`--skip-bottom`).

    uv run --python 3.12 register_frames.py raw_a.png edit_a.png raw_b.png edit_b.png

Verified against Concat: render the clip with the printed numbers (`preview_frame`) and register that
render against the edit frame again; the residual should be under 0.1 degree and 2 px. Gains below 1 on
blue and above 1 on red mean the edit is warmer: in Concat that is `concat.white-balance` (6500 K is as
shot, lower is warmer), checked the same closed-loop way.
"""
import argparse
import sys

import cv2
import numpy as np


def register(raw, edit, width, height):
    g1 = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(edit, cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT_create(5000)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    pairs = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [a for a, b in pairs if a.distance < 0.7 * b.distance]
    if len(good) < 12:
        return None
    p1 = np.float32([k1[a.queryIdx].pt for a in good])
    p2 = np.float32([k2[a.trainIdx].pt for a in good])
    m, inliers = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=3)
    if m is None:
        return None
    a, t = m[:, :2], m[:, 2]
    c = np.array([width / 2, height / 2])
    off = a @ c + t - c
    return m, {
        "matches": len(good),
        "inliers": int(inliers.sum()),
        "scale": float(np.hypot(a[0, 0], a[1, 0])),
        "rotation": float(np.degrees(np.arctan2(a[1, 0], a[0, 0]))),
        "offsetX": float(off[0] / width),
        "offsetY": float(off[1] / height),
    }


def colour(raw, edit, m, width, height, skip_top, skip_bottom):
    warped = cv2.warpAffine(raw, m, (width, height), flags=cv2.INTER_AREA)
    w = cv2.GaussianBlur(warped, (0, 0), 1.5)
    e = cv2.GaussianBlur(edit, (0, 0), 1.5)
    ok = np.abs(w.astype(int) - e.astype(int)).max(axis=2) < 30
    ok[: int(skip_top * height)] = False
    ok[height - int(skip_bottom * height):] = False
    ok[:, :30] = False
    ok = cv2.erode(ok.astype(np.uint8), np.ones((15, 15))) > 0
    a, b = w[ok].astype(float), e[ok].astype(float)
    gains = []
    for ch in range(3):
        design = np.vstack([a[:, ch], np.ones(len(a))]).T
        gains.append(float(np.linalg.lstsq(design, b[:, ch], rcond=None)[0][0]))
    sat = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2HSV)[ok][:, 1].astype(float).mean()
    luma = lambda x: (x @ [0.114, 0.587, 0.299]).mean()
    return {
        "gain_BGR": [round(g, 3) for g in gains],
        "saturation_ratio": round(float(sat(e) / sat(w)), 3),
        "luma_stops": round(float(np.log2(luma(b) / luma(a))), 3),
        "pixels": int(ok.sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frames", nargs="+", help="raw1 edit1 [raw2 edit2 ...]")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--skip-top", type=float, default=0.10, help="fraction of the height ignored for colour (titles)")
    ap.add_argument("--skip-bottom", type=float, default=0.05)
    args = ap.parse_args()
    if len(args.frames) % 2:
        ap.error("frames come in raw/edit pairs")
    for raw_path, edit_path in zip(args.frames[::2], args.frames[1::2]):
        raw, edit = cv2.imread(raw_path), cv2.imread(edit_path)
        if raw is None or edit is None or raw.shape != edit.shape:
            print(f"{raw_path} / {edit_path}: unreadable or different sizes", file=sys.stderr)
            continue
        found = register(raw, edit, args.width, args.height)
        if not found:
            print(f"{raw_path}: too few matches (a flat or blurred frame)")
            continue
        m, geo = found
        print(raw_path, edit_path)
        print("  clip_transform:", {k: round(geo[k], 4) for k in ("scale", "rotation", "offsetX", "offsetY")},
              f"({geo['inliers']}/{geo['matches']} inliers)")
        print("  colour:", colour(raw, edit, m, args.width, args.height, args.skip_top, args.skip_bottom))
    return 0


if __name__ == "__main__":
    sys.exit(main())

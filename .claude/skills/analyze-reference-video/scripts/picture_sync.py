# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Jareer Abdullah and Concat contributors
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Find which raw frame each frame of an edit shows, by the picture (not the sound).

For an edit that keeps the voice (a talking head) `align_audio.py` gives the raw time of each segment
on the audio clock. A phone screen recording of an editor's preview has its audio about 0.2 s behind
its picture, and a cut inside a pause can sit anywhere in the pause, so the picture is the truth for
lip sync: warp each raw frame with the edit's framing (`register_frames.py` prints it) and find the
raw time whose person region best matches the recorded frame. The answer is an offset per segment
relative to the audio-based time `edit_time + audio_offset`; it was constant inside each segment
(0.187 s on the first use), which is the number to add to the audio offset for the raw in-point.

    uv run --python 3.12 picture_sync.py --edit EDIT.mov --raw RAW.mov \\
        --crop 828:1472:0:175 --scale 1.16 --offset-y -0.046 \\
        --segment 0.3:3.3:4.64:1.2 --segment 3.5:6.3:5.36:1.0

`--segment from:to:audio_offset:rotation` (edit seconds, raw = edit + audio_offset, degrees clockwise).
`--crop W:H:X:Y` is the 9:16 preview area inside the recording's frame. The person region is the left
half below the first third of the frame, so the overlays (which sit on the right) do not count.
"""
import argparse
import subprocess
import sys

import cv2
import numpy as np

W, H = 270, 480


def frames(path, vf, fps=30):
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"fps={fps},{vf}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (W * H)
    return np.frombuffer(raw, np.uint8).reshape(n, H, W)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edit", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--crop", default="", help="W:H:X:Y of the 9:16 picture inside the edit's frame")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--offset-x", type=float, default=0.0)
    ap.add_argument("--offset-y", type=float, default=0.0)
    ap.add_argument("--segment", action="append", required=True, help="from:to:audio_offset:rotation")
    ap.add_argument("--window", type=float, default=0.6, help="search +-seconds around the audio-based time")
    ap.add_argument("--step", type=float, default=0.2)
    args = ap.parse_args()

    edit_vf = (f"crop={args.crop}," if args.crop else "") + f"scale={W}:{H}"
    edit = frames(args.edit, edit_vf)
    raw = frames(args.raw, f"scale={W}:{H}")

    def warp(img, rotation):
        m = cv2.getRotationMatrix2D((W / 2, H / 2), -rotation, args.scale)  # cv2 turns counter-clockwise
        m[0, 2] += args.offset_x * W
        m[1, 2] += args.offset_y * H
        return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_AREA)

    for spec in args.segment:
        start, end, audio_offset, rotation = (float(x) for x in spec.split(":"))
        offsets = []
        for t in np.arange(start, end, args.step):
            i = int(round(t * 30))
            if i >= len(edit):
                break
            target = edit[i].astype(float)[H // 3:, : W // 2]
            best = None
            for k in range(int((t + audio_offset - args.window) * 30), int((t + audio_offset + args.window) * 30)):
                if 0 <= k < len(raw):
                    err = np.abs(warp(raw[k], rotation).astype(float)[H // 3:, : W // 2] - target).mean()
                    if best is None or err < best[0]:
                        best = (err, k)
            offsets.append(best[1] / 30 - (t + audio_offset))
        if offsets:
            print(f"segment {spec}: picture minus audio offset median {np.median(offsets):+.3f} s "
                  f"(min {min(offsets):+.3f}, max {max(offsets):+.3f}, {len(offsets)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

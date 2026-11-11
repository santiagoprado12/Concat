# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
# /// script
# dependencies = ["pillow"]
# ///
"""Many frames of a video in ONE image, each labelled with its time.

Claude cannot watch a video but can read one picture with 40 frames in it. Use it to:
  - see a whole shot, a gesture, a gaze or a cut at a glance (a frame every 0.1-0.5 s),
  - check a person's face on every candidate second before using footage (crop to the face),
  - compare the start of every clip of a build (--times from a list),
  - look around a second the user named in a screenshot (e.g. 51.5:54.5:0.1).

Examples
  uv run frames_grid.py VIDEO --times 3:9:0.5 --out grid.jpg
  uv run frames_grid.py VIDEO --times 12.3 40.2 57.0 --crop 0.5:0.17:0.5:0.62 --tile 200 --out faces.jpg
  uv run frames_grid.py VIDEO --times 0:60:2 --cols 10 --tile 120 --out overview.jpg
  uv run frames_grid.py --images a.png b.png c.png d.png --labels A B C D --tile 400 --cols 4 --out options.jpg
      (the same sheet from existing pictures: four exposures of one frame for the user to choose from, before/after)

--times accepts numbers and ranges START:END:STEP (seconds), any mix.
--crop X:Y:W:H are fractions of the frame (0.5:0.17:0.5:0.62 = right half, from 17 % down, 62 % tall).
--tile is the width of one thumbnail in pixels; keep the whole sheet under about 2000 px wide and
40-60 tiles, or Claude will not read the small ones (split into several sheets with --per-sheet).
"""
import argparse
import io
import subprocess
import sys

from PIL import Image, ImageDraw


def parse_times(items):
    ts = []
    for it in items:
        if ":" in it:
            a, b, s = (float(x) for x in it.split(":"))
            t = a
            while t <= b + 1e-6:
                ts.append(round(t, 3))
                t += s
        else:
            ts.append(float(it))
    return ts


def grab(video, t, crop, tile):
    vf = []
    if crop:
        x, y, w, h = crop
        vf.append(f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}")
    vf.append(f"scale={tile}:-2")
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", ",".join(vf),
         "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--times", nargs="+")
    ap.add_argument("--images", nargs="+", help="tile these picture files instead of video frames")
    ap.add_argument("--labels", nargs="+", help="one label per image (default: the file name)")
    ap.add_argument("--crop", help="X:Y:W:H as fractions of the frame")
    ap.add_argument("--tile", type=int, default=160, help="thumbnail width in px")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--per-sheet", type=int, default=64, help="tiles per output image (extra sheets get _1, _2 ...)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    crop = [float(x) for x in a.crop.split(":")] if a.crop else None
    if a.images:
        ts = list(range(len(a.images)))
    else:
        if not a.video or not a.times:
            sys.exit("give VIDEO and --times, or --images")
        ts = parse_times(a.times)
    if not ts:
        sys.exit("no times")
    sheets = 0
    for si in range(0, len(ts), a.per_sheet):
        chunk = ts[si:si + a.per_sheet]
        if a.images:
            ims = []
            for i in chunk:
                im = Image.open(a.images[i]).convert("RGB")
                im = im.resize((a.tile, round(im.height * a.tile / im.width)))
                ims.append((i, im))
        else:
            ims = [(t, grab(a.video, t, crop, a.tile)) for t in chunk]
        ims = [(t, im) for t, im in ims if im is not None]
        if not ims:
            continue
        tw, th = ims[0][1].size
        cols = min(a.cols, len(ims))
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        for j, (t, im) in enumerate(ims):
            x, y = (j % cols) * tw, (j // cols) * th
            sheet.paste(im.resize((tw, th)), (x, y))
            if a.images:
                label = (a.labels[t] if a.labels and t < len(a.labels) else a.images[t].split("/")[-1])[:24]
            else:
                label = f"{t:.2f}".rstrip("0").rstrip(".")
            d.rectangle([x, y, x + 8 * len(label) + 6, y + 12], fill=(0, 0, 0))
            d.text((x + 3, y + 1), label, fill=(255, 255, 0))
        out = a.out if sheets == 0 else a.out.replace(".jpg", f"_{sheets}.jpg")
        sheet.save(out, quality=85)
        print(out, f"{len(ims)} frames", sheet.size)
        sheets += 1


if __name__ == "__main__":
    main()

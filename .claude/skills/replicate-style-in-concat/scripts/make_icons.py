#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["pillow"]
# ///
"""Draw the simple overlay icons the style uses, as transparent PNGs (512x512).

  uv run make_icons.py OUT_DIR

Writes check.png (green circle with a tick), cross.png (red circle with an X), cross_check.png (the two side by
side, 1024x512), bookmark.png (yellow ribbon with a white outline) and comment.png (white speech bubble).
Plain shapes, so they can be replaced by the real artwork later with the same file names.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

S = 512


def circle_icon(color, mark) -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([16, 16, S - 16, S - 16], fill=color, outline=(255, 255, 255, 255), width=18)
    w = 46
    if mark == "tick":
        d.line([(132, 270), (222, 360), (390, 160)], fill=(255, 255, 255, 255), width=w, joint="curve")
    else:
        d.line([(158, 158), (354, 354)], fill=(255, 255, 255, 255), width=w)
        d.line([(354, 158), (158, 354)], fill=(255, 255, 255, 255), width=w)
    return im


def bookmark() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(120, 40), (392, 40), (392, 472), (256, 360), (120, 472)]
    d.polygon(pts, fill=(247, 201, 52, 255), outline=(255, 255, 255, 255), width=18)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=18, joint="curve")
    return im


def comment() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([30, 60, S - 30, 360], radius=70, fill=(255, 255, 255, 255))
    d.polygon([(110, 340), (110, 470), (230, 350)], fill=(255, 255, 255, 255))
    for x in (150, 256, 362):
        d.ellipse([x - 24, 190, x + 24, 238], fill=(142, 94, 103, 255))
    return im


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    check = circle_icon((46, 160, 90, 255), "tick")
    cross = circle_icon((205, 70, 64, 255), "cross")
    pair = Image.new("RGBA", (S * 2, S), (0, 0, 0, 0))
    pair.paste(cross, (0, 0))
    pair.paste(check, (S, 0))
    for name, im in {"check": check, "cross": cross, "cross_check": pair, "bookmark": bookmark(), "comment": comment()}.items():
        im.save(out / f"{name}.png")
        print("wrote", out / f"{name}.png")


if __name__ == "__main__":
    main()

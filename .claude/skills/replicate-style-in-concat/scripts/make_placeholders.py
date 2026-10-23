#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["pillow"]
# ///
"""Make labelled placeholder images for footage the user has not supplied yet.

  uv run make_placeholders.py SPEC.json OUT_DIR [--size 1080x1920]

SPEC.json is a list of {"id": "03", "kind": "broll|capture|image", "text": "what goes here",
"start": 4.1, "end": 5.0}. Each becomes OUT_DIR/placeholder_<id>.png showing the kind, the
description and the time slot, so whoever opens the project knows what to drop in.
"""
import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLORS = {"broll": (46, 74, 98), "capture": (30, 104, 96), "image": (122, 84, 30)}
LABEL = {"broll": "B-ROLL", "capture": "CAPTURA", "image": "IMAGEN"}
FONTS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--size", default="1080x1920")
    a = ap.parse_args()
    w, h = map(int, a.size.split("x"))
    a.out.mkdir(parents=True, exist_ok=True)
    for item in json.loads(a.spec.read_text()):
        kind = item.get("kind", "broll")
        im = Image.new("RGB", (w, h), COLORS.get(kind, COLORS["broll"]))
        d = ImageDraw.Draw(im)
        d.rectangle([w * 0.04, h * 0.03, w * 0.96, h * 0.97], outline=(255, 255, 255), width=max(4, w // 180))
        d.text((w / 2, h * 0.20), f"{LABEL.get(kind, 'B-ROLL')} {item['id']}", fill=(255, 255, 255),
               font=font(w // 7), anchor="mm")
        lines = textwrap.wrap(item["text"], width=22)
        y = h * 0.33
        for line in lines:
            d.text((w / 2, y), line, fill=(255, 244, 214), font=font(w // 15), anchor="mm")
            y += w // 12
        dur = item["end"] - item["start"]
        d.text((w / 2, h * 0.60), f"{item['start']:.2f} - {item['end']:.2f} s  ({dur:.2f} s)", fill=(255, 255, 255),
               font=font(w // 18), anchor="mm")
        d.text((w / 2, h * 0.65), "reemplaza este clip", fill=(220, 220, 220), font=font(w // 24), anchor="mm")
        im.save(a.out / f"placeholder_{item['id']}.png")
    print(f"wrote {len(json.loads(a.spec.read_text()))} placeholders to {a.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Turn two CC0 sound sets into a small named palette of effects, all peaking at -6 dBFS.

  python3 -I make_sfx_pack.py --swishes DIR_WITH_swish-N.wav --kenney DIR_WITH_kenney_wavs --out OUT_DIR

Sources (both CC0, see references/sfx-sources.md): "Swishes Sound Pack" by artisticdude and
Kenney's "Interface Sounds". The raw swishes are 0.07-0.2 s long, too short for a slide, so
`slide_in` is a heavy one slowed to about 0.36 s with a short echo and `slide_out` is its reverse.
Writes: slide_in, slide_out, swish_short, swish_light, pop, tick, appear, click (.wav, mono 44.1 kHz).
Needs ffmpeg. Prints each file's duration so the caller can place it.
"""
import argparse
import re
import subprocess
from pathlib import Path


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def render(src: Path, dest: Path, chain: str = "") -> float:
    """Convert src to mono 44.1 kHz, apply `chain`, normalise the peak to -6 dBFS; return the duration."""
    base = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    flt = (chain + "," if chain else "") + "aformat=channel_layouts=mono"
    probe = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", flt + ",volumedetect", "-ar", "44100",
                 "-f", "null", "-"])
    m = re.search(r"max_volume: (-?[\d.]+) dB", probe.stderr)
    gain = -6.0 - float(m.group(1)) if m else 0.0
    run(base + ["-af", f"{flt},volume={gain:.2f}dB,alimiter=limit=0.55", "-ar", "44100", "-c:a", "pcm_s16le", str(dest)])
    d = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dest)])
    return float(d.stdout.strip() or 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--swishes", type=Path, required=True)
    ap.add_argument("--kenney", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sw, kn = a.swishes, a.kenney
    jobs = {
        "slide_in": (sw / "swish-9.wav", "atempo=0.55,highpass=f=200,aecho=0.7:0.55:38:0.25,afade=t=in:d=0.04"),
        "slide_out": (sw / "swish-9.wav", "atempo=0.55,highpass=f=200,aecho=0.7:0.55:38:0.25,areverse"),
        "swish_short": (sw / "swish-7.wav", "highpass=f=180"),
        "swish_light": (sw / "swish-12.wav", "highpass=f=250"),
        "pop": (kn / "pluck_001.wav", ""),
        "tick": (kn / "tick_001.wav", ""),
        "appear": (kn / "maximize_001.wav", ""),
        "click": (kn / "click_001.wav", ""),
    }
    for name, (src, chain) in jobs.items():
        if not src.exists():
            print(f"missing {src}")
            continue
        print(f"{name:12s} {render(src, a.out / (name + '.wav'), chain):.2f}s  <- {src.name}")


if __name__ == "__main__":
    main()

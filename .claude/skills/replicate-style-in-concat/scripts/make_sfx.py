#!/usr/bin/env python3
"""Synthesize placeholder sound effects with ffmpeg, for when the user has no SFX files.

  python3 -I make_sfx.py OUT_DIR

Writes whoosh_short / whoosh_long / impact / riser / click / pop / ding as 44.1 kHz mono wavs.
They are plain synthesis, not recordings: good enough to place and time effects the way a
reference does, and to be swapped later for real files with the same names. Needs ffmpeg.
"""
import subprocess
import sys
from pathlib import Path

NOISE_HP = "anoisesrc=d={d}:c=white:a=0.6,highpass=f=3000,afade=t=in:d={i},afade=t=out:st={i}:d={o}"
SOUNDS = {
    "whoosh_short": NOISE_HP.format(d=0.7, i=0.6, o=0.1),
    "whoosh_long": NOISE_HP.format(d=1.4, i=1.1, o=0.3),
    "impact": "aevalsrc='0.9*sin(2*PI*55*t)*exp(-5*t)+0.3*(random(0)-0.5)*exp(-30*t)':d=1.5:s=44100",
    "riser": "aevalsrc='0.5*sin(2*PI*(200*t+250*t*t))*(t/2.5)':d=2.5:s=44100,lowpass=f=6000",
    "click": "aevalsrc='0.7*(random(0)-0.5)*exp(-400*t)':d=0.08:s=44100",
    "pop": "aevalsrc='0.8*sin(2*PI*(900-4000*t)*t)*exp(-60*t)':d=0.12:s=44100",
    "ding": "aevalsrc='0.5*sin(2*PI*1568*t)*exp(-6*t)+0.25*sin(2*PI*3136*t)*exp(-9*t)':d=1.2:s=44100",
}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for name, src in SOUNDS.items():
        dest = out / f"{name}.wav"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-ar", "44100", "-ac", "1",
                            str(dest)], capture_output=True, text=True)
        print(("wrote " if r.returncode == 0 else "FAILED ") + str(dest), r.stderr.strip()[:200])


if __name__ == "__main__":
    main()

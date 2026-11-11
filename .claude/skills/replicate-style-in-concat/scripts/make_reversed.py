# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
"""Pre-render a reversed or boomerang piece of a raw video, so Concat can use it (it cannot play backwards).

  make_reversed.py RAW --in 51.2 --len 2.0 --out rev.mp4                   # the piece played backwards
  make_reversed.py RAW --in 51.2 --len 2.0 --out boom.mp4 --boomerang      # forward then backwards, one file
  make_reversed.py RAW --in 51.2 --len 2.0 --out boom.mp4 --boomerang --reverse-first

Why: a calm piece of 2 s can be made 4 s long by playing it forward and then back from the same frame; the join is
invisible (difference 0) when the person's pose stays within about 0.02 of the pivot frame. A reversed lean or
a head turn is obvious ("forward and then back"), so only use calm pieces (see learnings.md, 2026-11-07).

The reversed file has 0.12 s of spare frames at its tail so a later `clip_trim` never runs short. It is video only
(muted listening clips need no audio) at 30 fps, H.264 crf 16. The script prints the container duration: pass it as
`L` to the trim recipe in SKILL.md (start trim = in/speed, with the file's own `in` = 0).
Import the output with `media_import`, then place it with the normal recipe: `clip_add`, `clip_trim` start/end, `clips_move`.
"""
import argparse
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw")
    ap.add_argument("--in", dest="t_in", type=float, required=True, help="start of the piece in the raw (s)")
    ap.add_argument("--len", type=float, required=True, help="length of the piece (s)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--boomerang", action="store_true")
    ap.add_argument("--reverse-first", action="store_true", help="boomerang: backwards part first, then forward")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    if a.boomerang:
        # pivot frame appears once (the first frame of the second part is dropped)
        first, second = ("r", "a") if a.reverse_first else ("a", "r")
        vf = (f"[0:v]fps={a.fps},split[a0][b0];[a0]setpts=PTS-STARTPTS[a];[b0]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[r];"
              f"[{first}][{second}]concat=n=2:v=1[v]")
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{a.t_in:.4f}", "-t", f"{a.len:.4f}", "-i", a.raw,
               "-filter_complex", vf, "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", a.out]
    else:
        start = max(0.0, a.t_in - 0.12)
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.4f}", "-t", f"{a.len + 0.12:.4f}", "-i", a.raw,
               "-vf", f"reverse,fps={a.fps}", "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", a.out]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit(r.returncode)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.out],
                       capture_output=True, text=True).stdout.strip()
    print(f"{a.out}: container duration {float(d):.4f} s")


if __name__ == "__main__":
    main()

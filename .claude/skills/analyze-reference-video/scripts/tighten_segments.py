#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy"]
# ///
"""Tidy the cut points of an audio alignment so each clip starts when the voice is about to.

  uv run tighten_segments.py RAW audio_alignment.json --out tight.json
        [--lead 0.08] [--lead-trigger 0.12] [--max-tail 0.15] [--tail-trigger 0.25]

A reference's jump cuts often sit inside a pause: the clip then opens on a person who has not
started to speak, and looks away from the camera. For every segment this finds the first and
last frame where the voice is above a threshold (14 dB under the speaking level) and:
  - trims the head when more than --lead-trigger of silence precedes the voice, leaving --lead;
  - extends the head earlier (into raw footage that the edit skipped) when the voice starts
    within 40 ms of the cut, so the first syllable is not clipped;
  - trims a tail longer than --tail-trigger down to --max-tail.
Segments get new edited_start/edited_end (they are laid back to back), and `timemap` lets
captions, titles and placeholders written against the reference timeline be moved with them:
new_time = map_time(t). Writes tight.json (same shape as audio_alignment.json + `timemap`).
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

SR, HOP = 16000, 160


def voice_db(raw: Path) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(raw), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    y = np.frombuffer(p.stdout, dtype=np.float32)
    rms = np.sqrt(np.convolve(y ** 2, np.ones(HOP) / HOP, mode="same")[::HOP] + 1e-12)
    return 20 * np.log10(rms)


def map_time(t: float, knots: list[dict]) -> float:
    """Move a time on the reference timeline to the tightened timeline."""
    for k in knots:
        if t <= k["e1"] + 1e-9:
            u = min(max(t - k["e0"], 0.0), k["e1"] - k["e0"])
            return k["ns"] + min(max(u - k["head_adj"], 0.0), k["nd"])
    last = knots[-1]
    return last["ns"] + last["nd"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path)
    ap.add_argument("alignment", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lead", type=float, default=0.08)
    ap.add_argument("--lead-trigger", type=float, default=0.12)
    ap.add_argument("--max-tail", type=float, default=0.15)
    ap.add_argument("--tail-trigger", type=float, default=0.25)
    a = ap.parse_args()

    db = voice_db(a.raw)
    thr = np.percentile(db[db > -60], 85) - 14
    al = json.loads(a.alignment.read_text())
    segs = al["segments"]
    knots, out, cursor, prev_raw_end = [], [], 0.0, 0.0
    for s in segs:
        i0, i1 = int(round(s["raw_start"] * 100)), int(round(s["raw_end"] * 100))
        idx = np.where(db[i0:i1] > thr)[0]
        lead = idx[0] / 100 if len(idx) else 0.0
        tail = (i1 - i0) / 100 - idx[-1] / 100 if len(idx) else 0.0
        head_adj = 0.0
        if lead > a.lead_trigger:
            head_adj = lead - a.lead
        elif lead < 0.04:
            head_adj = -min(a.lead - lead, max(s["raw_start"] - prev_raw_end - 0.02, 0.0))
        tail_adj = tail - a.max_tail if tail > a.tail_trigger else 0.0
        dur = (s["raw_end"] - s["raw_start"]) - head_adj - tail_adj
        ns = cursor
        knots.append({"e0": s["edited_start"], "e1": s["edited_end"], "ns": round(ns, 3), "nd": round(dur, 3),
                      "head_adj": round(head_adj, 3)})
        out.append({**s, "edited_start": round(ns, 3), "edited_end": round(ns + dur, 3), "duration": round(dur, 3),
                    "raw_start": round(s["raw_start"] + head_adj, 3), "raw_end": round(s["raw_end"] - tail_adj, 3),
                    "head_adj": round(head_adj, 3), "tail_adj": round(tail_adj, 3), "lead_before": round(lead, 2)})
        cursor += dur
        prev_raw_end = s["raw_end"] - tail_adj
    res = {**al, "segments": out, "timemap": knots, "tightened": {"total_seconds": round(cursor, 3),
           "removed_seconds": round(al["edited_duration"] - cursor, 3), "threshold_db": round(float(thr), 1)}}
    a.out.write_text(json.dumps(res, indent=1))
    print(f"{len(out)} segments: {al['edited_duration']:.2f}s -> {cursor:.2f}s")
    for o in out:
        flag = "trim head" if o["head_adj"] > 0 else ("extend head" if o["head_adj"] < 0 else "")
        print(f"seg {o['edited_start']:7.2f}  lead {o['lead_before']:.2f}s {flag} {abs(o['head_adj']):.2f}s  tail trimmed {o['tail_adj']:.2f}s")


if __name__ == "__main__":
    main()

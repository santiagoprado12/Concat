#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "librosa", "pillow"]
# ///
"""Check analyze.py against a synthetic video whose cuts and sound effects are known.

  uv run selftest.py --work DIR

Builds a 10 s clip: hard cuts at 2.5 / 5.0 / 8.0 s, a high-pass noise swell ("whoosh") peaking
0.1 s before each cut, a low impact at 5.0 s, and a 120 BPM tick under everything. Then runs
analyze.py and asserts the cuts, the whoosh offset and the tempo come back within tolerance.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CUTS = [2.5, 5.0, 8.0]


def build(video: Path) -> None:
    whoosh = ("anoisesrc=d=0.7:c=white:a=0.6,highpass=f=3000,afade=t=in:d=0.6,afade=t=out:st=0.6:d=0.1,"
              "adelay={ms}|{ms}")
    parts = []
    for i, c in enumerate(CUTS):
        ms = int((c - 0.7) * 1000)
        parts.append(f"{whoosh.format(ms=ms)}[w{i}]")
    graph = (
        "color=c=red:s=640x360:r=25:d=2.5[v0];testsrc2=s=640x360:r=25:d=2.5[v1];"
        "color=c=blue:s=640x360:r=25:d=3[v2];smptebars=s=640x360:r=25:d=2[v3];"
        "[v0][v1][v2][v3]concat=n=4:v=1:a=0[v]"
    )
    audio_inputs = []
    # tick every 0.5 s (120 BPM), low pad, impact at 5.0 s
    tick = "aevalsrc='0.5*(random(0)-0.5)*exp(-90*mod(t,0.5))':d=10:s=22050"
    pad = "aevalsrc='0.08*sin(2*PI*220*t)+0.06*sin(2*PI*277*t)':d=10:s=22050"
    impact = "aevalsrc='0.9*sin(2*PI*55*t)*exp(-5*t)':d=1.2:s=22050,adelay=5000|5000"
    noise_chains = ";".join(f"{p}" for p in parts)
    fc = (f"{graph};{tick}[t];{pad}[p];{impact}[i];{noise_chains};"
          f"[t][p][i]" + "".join(f"[w{i}]" for i in range(len(CUTS))) +
          f"amix=inputs={3 + len(CUTS)}:normalize=0:duration=longest,atrim=0:10[a]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", "10", str(video)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    del audio_inputs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    video, out = a.work / "synthetic.mp4", a.work / "out"
    build(video)
    r = subprocess.run([sys.executable, str(HERE / "analyze.py"), "all", str(video), "--out", str(out)],
                       capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.returncode:
        sys.exit(r.stderr)
    rep = json.loads((out / "style-report.json").read_text())
    ok = True

    def check(name: str, cond: bool, detail: str) -> None:
        nonlocal ok
        ok &= cond
        print(("PASS " if cond else "FAIL ") + name + " - " + detail)

    found = [b["time"] for b in rep["boundaries"]]
    check("cuts", len(found) == len(CUTS) and all(abs(f - c) < 0.1 for f, c in zip(found, CUTS)),
          f"expected {CUTS}, got {found}")
    corr = rep["correlations"].get("sfx_near_cuts", {})
    w = corr.get("whoosh_swell")
    check("whoosh before cuts", bool(w) and w["count"] >= 2 and -0.35 < w["median_offset_s"] < 0.05,
          f"{w}")
    imp = [e for e in rep["sfx_events"] if abs(e["time"] - 5.0) < 0.12 and e["label"] in ("impact_boom", "hit_thump")]
    check("impact at 5.0 s", bool(imp), f"{[ (e['time'], e['label']) for e in rep['sfx_events'] if abs(e['time']-5.0) < 0.3]}")
    bpm = rep["music"].get("bpm", 0)
    check("tempo", any(abs(bpm - t) < 6 for t in (60, 120, 240)), f"bpm {bpm}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

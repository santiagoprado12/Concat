#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "pillow"]
# ///
"""Score a replica against the reference it copies.

  uv run compare.py REF_DIR RESULT_DIR [--ref-video V --result-video V] [--out DIR]

REF_DIR and RESULT_DIR are analyze.py output folders (each holds style-report.json).
Reports cut placement, pacing, loudness, and sound effects matched by kind and time.
With both videos it also writes side_by_side.jpg: reference above, replica below, at each cut.
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

KIND = {"hit_thump": "hit", "impact_boom": "hit", "click_pop": "click", "transient": "click",
        "whoosh_swell": "whoosh", "riser": "riser", "ambience_or_swell": "whoosh"}


def match(a: list[float], b: list[float], tol: float) -> list[tuple[float, float]]:
    pairs, used = [], set()
    for x in a:
        cand = [(abs(x - y), j, y) for j, y in enumerate(b) if j not in used and abs(x - y) <= tol]
        if cand:
            _, j, y = min(cand)
            used.add(j)
            pairs.append((x, y))
    return pairs


def prf(n_ref: int, n_res: int, n_match: int) -> str:
    rec = n_match / n_ref if n_ref else 0
    pre = n_match / n_res if n_res else 0
    return f"{n_match}/{n_ref} reference found ({rec:.0%}), {n_res - n_match} extra in replica (precision {pre:.0%})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", type=Path)
    ap.add_argument("result", type=Path)
    ap.add_argument("--ref-video", type=Path)
    ap.add_argument("--result-video", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--cut-tol", type=float, default=0.15)
    ap.add_argument("--sfx-tol", type=float, default=0.2)
    a = ap.parse_args()
    ref = json.loads((a.ref / "style-report.json").read_text())
    res = json.loads((a.result / "style-report.json").read_text())
    out = a.out or a.result
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Replica vs reference", ""]

    rc = [b["time"] for b in ref["boundaries"]]
    sc = [b["time"] for b in res["boundaries"]]
    pairs = match(rc, sc, a.cut_tol)
    lines += ["## Cuts", prf(len(rc), len(sc), len(pairs))]
    if pairs:
        off = [y - x for x, y in pairs]
        lines.append(f"timing error on matched cuts: median {np.median(off):+.3f}s, worst {max(map(abs, off)):.3f}s")
    missing = [round(x, 2) for x in rc if all(abs(x - y) > a.cut_tol for y in sc)]
    extra = [round(y, 2) for y in sc if all(abs(x - y) > a.cut_tol for x in rc)]
    if missing:
        lines.append(f"missing cuts at: {missing[:30]}")
    if extra:
        lines.append(f"extra cuts at: {extra[:30]}")
    rp, sp = ref["pacing"], res["pacing"]
    lines += ["", "## Pacing", f"average shot length: reference {rp.get('avg_shot_length')}s, replica {sp.get('avg_shot_length')}s",
              f"duration: reference {ref['probe'].get('duration'):.2f}s, replica {res['probe'].get('duration'):.2f}s"]

    rl, sl = ref["loudness"], res["loudness"]
    lines += ["", "## Loudness (LUFS, LU)"]
    for k in ("integrated_lufs", "lra", "true_peak_db"):
        if rl.get(k) is not None and sl.get(k) is not None:
            lines.append(f"{k}: reference {rl[k]}, replica {sl[k]} (diff {sl[k] - rl[k]:+.1f})")

    lines += ["", "## Sound effects (matched by kind, within +-%.2fs)" % a.sfx_tol]
    rm, sm = ref.get("music", {}), res.get("music", {})
    lines.append(f"music tempo: reference {rm.get('bpm')} BPM, replica {sm.get('bpm')} BPM")
    for kind in ("hit", "whoosh", "riser", "click"):
        re_ = [e["time"] for e in ref["sfx_events"] if KIND.get(e["label"]) == kind and not e.get("on_beat")]
        se_ = [e["time"] for e in res["sfx_events"] if KIND.get(e["label"]) == kind and not e.get("on_beat")]
        if not re_ and not se_:
            continue
        pm = match(re_, se_, a.sfx_tol)
        extra = f", median offset {np.median([y - x for x, y in pm]):+.3f}s" if pm else ""
        lines.append(f"{kind} (off-beat only): {prf(len(re_), len(se_), len(pm))}{extra}")
    lines += ["", "Detectors are heuristic on both sides; a gap here means 'look at the spectrogram', not 'wrong'."]
    text = "\n".join(lines)
    (out / "compare.md").write_text(text)
    print(text)

    if a.ref_video and a.result_video and pairs:
        spec = importlib.util.spec_from_file_location("analyze", Path(__file__).with_name("analyze.py"))
        an = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(an)
        tmp = out / "_pairs"
        tmp.mkdir(exist_ok=True)
        items = []
        picks = pairs[:: max(1, len(pairs) // 8)][:8]
        for n, (x, y) in enumerate(picks):
            for tag, vid, t in (("ref", a.ref_video, x), ("res", a.result_video, y)):
                p = tmp / f"{tag}_{n}.jpg"
                if an.grab(vid, t + 0.3, p, 300):
                    items.append((p, f"{tag} {t:.1f}s"))
        top = [i for i in items if i[1].startswith("ref")]
        bottom = [i for i in items if i[1].startswith("res")]
        an.sheet(top + bottom, out / "side_by_side.jpg", max(1, len(top)))
        print(f"wrote {out / 'side_by_side.jpg'} (top row reference, bottom row replica)")


if __name__ == "__main__":
    main()

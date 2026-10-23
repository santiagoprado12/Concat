#!/usr/bin/env python3
"""Turn chosen takes of a raw recording into a timeline plan: cuts, captions, titles, placeholders, effects.

  python3 -I takes_to_plan.py --takes takes.json --overlays overlays.json --out DIR [--vad vad.json]

For raw footage of one person talking, with many retakes. Pick the take of each line by listening
to a per-phrase transcript (see analyze-reference-video), then describe the edit by what is SAID,
not by timestamps of the finished video:

takes.json   {"raw": "/abs/raw.mov", "raw_duration": 301.9, "lead": 0.12, "tail": 0.15,
              "takes": [{"id": "hook", "phrases": [
                  {"start": 0.26, "end": 2.62, "chunks": ["Y si te digo", "que vas a conversar"]}, ...]}, ...]}
             `start`/`end` are the voiced region of each phrase in the raw file (energy detection, exact);
             `chunks` are the caption texts of the phrase, in order.
overlays.json {"title_style": {...}, "caption": {"offsetY": 0.28, "style": {...}},
              "titles":  [{"anchor": "Primero", "text": "PASO 1", "typed": true, "dur": 1.9, "offsetY": -0.28}],
              "accents": [{"anchor": "Cálido", "text": "Cálido", "dur": 0.9, "offsetY": -0.05, "style": {...}}],
              "cards":   [{"id": "01", "kind": "capture|broll|image", "text": "what goes here", "anchor": "con un chat",
                           "offset": 0.0, "dur": 2.3, "slide": true}],
              "icons":   [{"icon": "check", "anchor": "...", "dur": 1.0, "scale": 0.2, "offsetX": 0, "offsetY": -0.25}],
              "punches": [{"anchor": "perfecto", "scale": 1.07, "ramp": 0.25}],
              "sfx": {"slide_in": "/abs/slide_in.wav", "swish_short": "...", "swish_light": "...", "pop": "..."}}
An `anchor` is text found inside a caption chunk (first match); its start time is where the overlay begins.

Cuts: each phrase becomes a clip from `lead` before its voice to `tail` after it, never into a neighbour's
speech (`--vad`: the regions from the energy detector). Phrases of one take whose margins touch are joined
into one clip; pauses longer than lead+tail are cut out. Caption chunk times are spread over the voiced
part of the phrase by character count.

Writes into OUT: alignment.json, captions.json, titles.json, placeholders_spec.json, placeholders.json
(png paths under OUT/placeholders, made by make_placeholders.py), icons.json, punches.json, sfx.json, plan.md.
"""
import argparse
import json
import sys
from pathlib import Path

SFX_LEN = {"slide_in": 0.363, "swish_short": 0.19, "swish_light": 0.08, "pop": 0.11}
TYPE_STEP = 0.06


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--takes", type=Path, required=True)
    ap.add_argument("--overlays", type=Path, required=True)
    ap.add_argument("--vad", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tk = json.loads(a.takes.read_text())
    ov = json.loads(a.overlays.read_text())
    lead, tail = tk.get("lead", 0.12), tk.get("tail", 0.15)
    raw_dur = tk["raw_duration"]
    regions = json.loads(a.vad.read_text())["regions"] if a.vad else []

    # ---- cuts
    segs: list[dict] = []
    phrases: list[dict] = []
    cursor = 0.0
    for take in tk["takes"]:
        prev_seg = None
        for ph in take["phrases"]:
            a0, b0 = ph["start"], ph["end"]
            pe = max([r[1] for r in regions if r[1] <= a0 - 0.05] or [0.0])
            ns = min([r[0] for r in regions if r[0] >= b0 + 0.05] or [raw_dur])
            rs, re = max(a0 - lead, pe + 0.03), min(b0 + tail, ns - 0.03)
            if prev_seg is not None and rs <= prev_seg["raw_end"] + 1e-6:
                cursor -= prev_seg["duration"]
                prev_seg["raw_end"] = re
                prev_seg["duration"] = re - prev_seg["raw_start"]
                cursor += prev_seg["duration"]
                seg = prev_seg
            else:
                seg = {"raw_start": rs, "raw_end": re, "duration": re - rs, "edited_start": cursor, "take": take["id"]}
                segs.append(seg)
                cursor += seg["duration"]
            phrases.append({"seg": seg, "a0": a0, "b0": b0, "chunks": ph["chunks"], "take": take["id"]})
            prev_seg = seg
    for s in segs:
        s["edited_end"] = s["edited_start"] + s["duration"]
        for k in ("raw_start", "raw_end", "edited_start", "edited_end", "duration"):
            s[k] = round(s[k], 3)
    total = round(cursor, 3)

    # ---- captions
    chunks: list[dict] = []
    for ph in phrases:
        on = ph["seg"]["edited_start"] + (ph["a0"] - ph["seg"]["raw_start"])
        off = ph["seg"]["edited_start"] + (ph["b0"] - ph["seg"]["raw_start"])
        weights = [max(len(c), 1) for c in ph["chunks"]]
        acc = 0.0
        for c, wgt in zip(ph["chunks"], weights):
            s0 = on + (off - on) * acc / sum(weights)
            acc += wgt
            e0 = on + (off - on) * acc / sum(weights)
            chunks.append({"text": c, "start": s0, "end": e0, "take": ph["take"]})
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1]["start"] if i + 1 < len(chunks) else total
        c["end"] = round(min(max(c["end"] + 0.12, c["start"] + 0.3), nxt if nxt - c["start"] > 0.3 else c["start"] + 0.3, total), 3)
        c["start"] = round(c["start"], 3)
    cap = dict(ov.get("caption", {}))
    cap["captions"] = [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in chunks]

    def find(anchor: str, nth: int = 0) -> dict:
        hits = [c for c in chunks if anchor.lower() in c["text"].lower()]
        if len(hits) <= nth:
            sys.exit(f"anchor not found in any caption chunk: {anchor!r}")
        return hits[nth]

    # ---- titles and accents
    tstyle = ov.get("title_style", {})
    titles, first_title_times = [], []
    for t in ov.get("titles", []):
        t0 = find(t["anchor"], t.get("nth", 0))["start"] + t.get("offset", 0.0)
        style = {**tstyle, **t.get("style", {})}
        text = t["text"]
        first_title_times.append(t0)
        if t.get("typed"):
            n = len(text)
            for k in range(1, n + 1):
                d = TYPE_STEP if k < n else max(t["dur"] - (n - 1) * TYPE_STEP, 0.3)
                titles.append({"start": round(t0 + (k - 1) * TYPE_STEP, 3), "duration": round(d, 3),
                               "offsetY": t.get("offsetY", -0.28), "style": {**style, "content": text[:k]}})
        else:
            titles.append({"start": round(t0, 3), "duration": t["dur"], "offsetY": t.get("offsetY", -0.28),
                           "style": {**style, "content": text}})
    for t in ov.get("accents", []):
        t0 = find(t["anchor"], t.get("nth", 0))["start"] + t.get("offset", 0.0)
        first_title_times.append(t0)
        titles.append({"start": round(t0, 3), "duration": t["dur"], "offsetY": t.get("offsetY", -0.05),
                       "style": {**ov.get("accent_style", {}), **t.get("style", {}), "content": t["text"]}})
    titles.sort(key=lambda x: x["start"])

    # ---- cards (placeholders)
    spec, cards = [], []
    last_end = 0.0
    for c in sorted(ov.get("cards", []), key=lambda c: find(c["anchor"], c.get("nth", 0))["start"] + c.get("offset", 0)):
        s0 = find(c["anchor"], c.get("nth", 0))["start"] + c.get("offset", 0.0)
        s0 = max(s0, last_end)  # one lane: no overlap
        e0 = min(s0 + c["dur"], total)
        last_end = e0
        spec.append({"id": c["id"], "kind": c["kind"], "text": c["text"], "start": round(s0, 3), "end": round(e0, 3)})
        cards.append({"png": str((a.out / "placeholders" / f"placeholder_{c['id']}.png").resolve()), "start": round(s0, 3),
                      "end": round(e0, 3), "slide": bool(c.get("slide", c["kind"] in ("capture", "image"))), "kind": c["kind"],
                      "transition": c.get("transition")})

    icons = []
    for ic in ov.get("icons", []):
        s0 = find(ic["anchor"], ic.get("nth", 0))["start"] + ic.get("offset", 0.0)
        icons.append({"png": str((a.out / "icons" / f"{ic['icon']}.png").resolve()), "start": round(s0, 3),
                      "end": round(min(s0 + ic["dur"], total), 3), "scale": ic.get("scale", 0.2),
                      "offsetX": ic.get("offsetX", 0.0), "offsetY": ic.get("offsetY", -0.25)})

    punches = [{"time": find(p["anchor"], p.get("nth", 0))["start"], "scale": p.get("scale", 1.07), "ramp": p.get("ramp", 0.25)}
               for p in ov.get("punches", [])]

    # ---- sound effects, greedy over lanes so nothing overlaps on a lane
    files = ov.get("sfx", {})
    wanted: list[tuple[float, str, float]] = []
    for c in cards:
        if c["kind"] == "broll":
            wanted.append((c["start"] - 0.04, "swish_short", 0.45))
        else:
            wanted.append((c["start"] - 0.08, "slide_in", 0.7))
            wanted.append((c["end"] - 0.10, "swish_light", 0.4))
    for t in first_title_times:
        wanted.append((t, "pop", 0.5))
    sfx, lane_end = [], {}
    for t0, name, vol in sorted(wanted):
        if name not in files:
            continue
        t0 = max(t0, 0.0)
        for lane in "ABCDEF":
            if lane_end.get(lane, -1) <= t0 + 1e-6:
                lane_end[lane] = t0 + SFX_LEN.get(name, 0.3)
                sfx.append({"file": files[name], "start": round(t0, 3), "volume": vol, "lane": lane, "name": name})
                break

    # ---- write
    def dump(name: str, data) -> None:
        (a.out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False))

    dump("alignment.json", {"edited_duration": total, "segments": segs})
    dump("captions.json", cap)
    dump("titles.json", titles)
    dump("placeholders_spec.json", spec)
    dump("placeholders.json", cards)
    dump("icons.json", icons)
    dump("punches.json", punches)
    dump("sfx.json", sfx)
    md = [f"# Plan: {total:.1f}s, {len(segs)} clips, {len(chunks)} captions, {len(titles)} title clips, "
          f"{len(cards)} placeholders, {len(icons)} icons, {len(sfx)} effects", ""]
    md += [f"- {c['start']:6.2f}-{c['end']:6.2f}  {c['text']}" for c in chunks]
    (a.out / "plan.md").write_text("\n".join(md))
    print(f"{total:.1f}s: {len(segs)} clips, {len(chunks)} captions, {len(titles)} title clips, {len(cards)} placeholders, "
          f"{len(icons)} icons, {len(punches)} punch-ins, {len(sfx)} effects on lanes {sorted(lane_end)}")


if __name__ == "__main__":
    main()

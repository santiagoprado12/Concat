#!/usr/bin/env python3
"""Turn an alignment (or a takes plan) into a mcp_run.py steps file that builds the edit in Concat.

  python3 -I build_steps.py --raw RAW.mp4 --raw-duration 243.73 --alignment alignment.json \
      --location ~/concat-analysis/job --name project --size 1080x1920 --fps 30 \
      [--placeholders P.json] [--icons I.json] [--captions C.json] [--titles T.json] [--sfx S.json] \
      [--punches U.json] [--music M.wav --music-duration 224 --music-volume 0.1] [--voice-target -16] \
      [--export out.mp4] [--preview 3.0,17.5] --out steps.json

Layout built (lane numbers are what Concat's `title_add above` and captions_add put above the rest):
  T1  the raw recording, one clip per aligned segment (picture and voice), laid back to back
  T2  placeholder images for shots whose picture is not in the raw footage
  T3  small overlay icons
  above  captions and titles;  new audio lanes at the bottom: effects (one lane per letter), music
Inputs (all times in seconds on the timeline the alignment defines; --remap moves them with a tightened one):
  alignment: {"segments": [{"edited_start","edited_end","raw_start","raw_end"}, ...], "edited_duration"?}
  placeholders: [{"png","start","end","slide"?: true}]     icons: [{"png","start","end","scale","offsetX","offsetY"}]
  captions: {"offsetY","style","captions":[{"start","end","text"}]}   titles: [{"start","duration","offsetY","style":{...}}]
  sfx: [{"file","start","volume","lane"}]                  punches: [{"time","scale","ramp"}] (zoom on the clip holding `time`)
All output paths must be under the home folder (the MCP server refuses to write elsewhere).
"""
import argparse
import json
from pathlib import Path


def map_time(t: float, knots: list) -> float:
    """Move a time from the reference timeline to the tightened one (see tighten_segments.py)."""
    for k in knots:
        if t <= k["e1"] + 1e-9:
            u = min(max(t - k["e0"], 0.0), k["e1"] - k["e0"])
            return k["ns"] + min(max(u - k["head_adj"], 0.0), k["nd"])
    return knots[-1]["ns"] + knots[-1]["nd"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--raw-duration", type=float, required=True, help="length of the raw file in seconds")
    ap.add_argument("--alignment", type=Path, required=True)
    ap.add_argument("--location", required=True, help="existing folder; the project is created inside it")
    ap.add_argument("--name", default="project")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--placeholders", type=Path)
    ap.add_argument("--icons", type=Path)
    ap.add_argument("--captions", type=Path)
    ap.add_argument("--titles", type=Path)
    ap.add_argument("--sfx", type=Path, help="each lane gets its own audio track so effects never overlap on one")
    ap.add_argument("--punches", type=Path)
    ap.add_argument("--music", help="a long audio file; it is trimmed to the edit and faded")
    ap.add_argument("--music-duration", type=float, help="length of the music file in seconds")
    ap.add_argument("--music-volume", type=float, default=0.1, help="gain; 0.1 is about 20 dB under the voice")
    ap.add_argument("--music-fade-in", type=float, default=1.5)
    ap.add_argument("--music-fade-out", type=float, default=2.5)
    ap.add_argument("--voice-target", type=float, help="normalise each voice clip to this loudness in dB (e.g. -16)")
    ap.add_argument("--preview", default="", help="comma separated times to render as PNGs next to the project")
    ap.add_argument("--export", help="mp4 path to export, under the home folder")
    ap.add_argument("--remap", action="store_true",
                    help="--alignment is a tighten_segments.py output: move captions, titles, placeholders and "
                         "previews (written against the reference timeline) with the tightened cuts")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    loc = str(Path(a.location).expanduser())
    proj = f"{loc}/{a.name}"
    w, h = map(int, a.size.split("x"))
    steps: list[dict] = [
        {"tool": "project_create", "args": {"location": loc, "name": a.name,
                                            "video": {"width": w, "height": h, "rateNum": a.fps, "rateDen": 1}}},
        {"tool": "media_import", "args": {"path": proj, "file": a.raw}, "as": "raw"},
    ]

    aligned = json.loads(a.alignment.read_text())
    segs = aligned["segments"]
    total = aligned.get("edited_duration") or segs[-1]["edited_end"]
    knots = aligned.get("timemap") if a.remap else None
    mt = (lambda t: round(map_time(t, knots), 3)) if knots else (lambda t: round(t, 3))

    def key(cid: str, prop: str, at: float, value: float) -> dict:
        return {"tool": "keyframe_set", "args": {"path": proj, "clipId": f"${cid}.createdId", "property": prop,
                                                 "at": round(min(max(at, 0.0), 1.0), 4), "value": value}}

    for i, s in enumerate(segs):
        dur = s["edited_end"] - s["edited_start"]
        tail = a.raw_duration - s["raw_start"] - dur
        cid = f"seg{i}"
        steps += [
            {"tool": "clip_add", "args": {"path": proj, "mediaId": "$raw.createdId", "trackId": "T1",
                                          "start": round(s["edited_start"], 3)}, "as": cid},
            {"tool": "clip_trim", "args": {"path": proj, "clipId": f"${cid}.createdId", "edge": "start",
                                           "delta": round(s["raw_start"], 3)}},
            {"tool": "clip_trim", "args": {"path": proj, "clipId": f"${cid}.createdId", "edge": "end",
                                           "delta": -round(tail, 3)}},
            {"tool": "clips_move", "args": {"path": proj, "moves": [
                {"clipId": f"${cid}.createdId", "start": round(s["edited_start"], 3), "trackId": "T1"}]}},
        ]
        if a.voice_target is not None:
            steps.append({"tool": "clip_update", "args": {"path": proj, "clipId": f"${cid}.createdId", "patch": {
                "filters": [{"id": "concat.loudness", "params": {"target": a.voice_target}}]}}})

    if a.punches:
        for n, p in enumerate(json.loads(a.punches.read_text())):
            t = mt(p["time"])
            seg = next((k for k, s in enumerate(segs) if s["edited_start"] - 1e-6 <= t < s["edited_end"] + 1e-6), None)
            if seg is None:
                continue
            s = segs[seg]
            dur = s["edited_end"] - s["edited_start"]
            f0 = (t - s["edited_start"]) / dur
            steps += [key(f"seg{seg}", "scale", f0, 1.0), key(f"seg{seg}", "scale", f0 + p.get("ramp", 0.25) / dur, p["scale"])]

    if a.placeholders:
        for i, p in enumerate(json.loads(a.placeholders.read_text())):
            p = {**p, "start": mt(p["start"]), "end": mt(p["end"])}
            dur = p["end"] - p["start"]
            if dur < 0.05:
                continue
            m, c = f"ph{i}", f"phc{i}"
            steps += [
                {"tool": "media_import", "args": {"path": proj, "file": p["png"]}, "as": m},
                {"tool": "clip_add", "args": {"path": proj, "mediaId": f"${m}.createdId", "trackId": "T2",
                                              "start": round(p["start"], 3)}, "as": c},
                {"tool": "clip_trim", "args": {"path": proj, "clipId": f"${c}.createdId", "edge": "end",
                                               "delta": -round(5.0 - dur, 3)}},
            ]
            if p.get("transition"):  # e.g. {"id": "concat.dissolve", "duration": 0.4}
                steps.append({"tool": "clip_update", "args": {"path": proj, "clipId": f"${c}.createdId",
                                                              "patch": {"transitionIn": p["transition"]}}})
            if p.get("slide"):  # rises 10 % of the frame while fading in over 0.22 s
                f = min(0.22 / dur, 0.9)
                steps += [key(c, "opacity", 0.0, 0.0), key(c, "opacity", f, 1.0),
                          key(c, "offsetY", 0.0, 0.10), key(c, "offsetY", f, 0.0)]

    if a.icons:
        for i, p in enumerate(json.loads(a.icons.read_text())):
            p = {**p, "start": mt(p["start"]), "end": mt(p["end"])}
            dur = p["end"] - p["start"]
            if dur < 0.05:
                continue
            m, c = f"ic{i}", f"icc{i}"
            steps += [
                {"tool": "media_import", "args": {"path": proj, "file": p["png"]}, "as": m},
                {"tool": "clip_add", "args": {"path": proj, "mediaId": f"${m}.createdId", "trackId": "T3",
                                              "start": round(p["start"], 3)}, "as": c},
                {"tool": "clip_trim", "args": {"path": proj, "clipId": f"${c}.createdId", "edge": "end",
                                               "delta": -round(5.0 - dur, 3)}},
                {"tool": "clip_transform", "args": {"path": proj, "clipId": f"${c}.createdId",
                                                    "scale": p.get("scale", 0.25), "offsetX": p.get("offsetX", 0.0),
                                                    "offsetY": p.get("offsetY", -0.3)}},
            ]

    if a.sfx:
        items = json.loads(a.sfx.read_text())
        files = sorted({i["file"] for i in items})
        for k, f in enumerate(files):
            steps.append({"tool": "media_import", "args": {"path": proj, "file": f}, "as": f"sfxm{k}"})
        lanes = sorted({i.get("lane", "A") for i in items})
        for ln in lanes:
            steps.append({"tool": "track_add", "args": {"path": proj, "bottom": True}, "as": f"sfxlane{ln}"})
        for n, i in enumerate(items):
            steps.append({"tool": "clip_add", "args": {"path": proj, "mediaId": f"$sfxm{files.index(i['file'])}.createdId",
                                                       "trackId": f"$sfxlane{i.get('lane', 'A')}.createdId",
                                                       "start": max(0.0, mt(i["start"]))}, "as": f"sfxc{n}"})
            steps.append({"tool": "clip_update", "args": {"path": proj, "clipId": f"$sfxc{n}.createdId",
                                                          "patch": {"volume": i.get("volume", 0.6)}}})

    if a.music:
        end = mt(total)
        steps += [
            {"tool": "media_import", "args": {"path": proj, "file": a.music}, "as": "music"},
            {"tool": "track_add", "args": {"path": proj, "bottom": True}, "as": "musiclane"},
            {"tool": "clip_add", "args": {"path": proj, "mediaId": "$music.createdId", "trackId": "$musiclane.createdId",
                                          "start": 0.0}, "as": "musicclip"},
        ]
        if a.music_duration and a.music_duration > end:
            steps.append({"tool": "clip_trim", "args": {"path": proj, "clipId": "$musicclip.createdId", "edge": "end",
                                                        "delta": -round(a.music_duration - end, 3)}})
        steps.append({"tool": "clip_update", "args": {"path": proj, "clipId": "$musicclip.createdId", "patch": {
            "volume": a.music_volume, "fadeIn": a.music_fade_in, "fadeOut": a.music_fade_out}}})

    if a.captions:
        cap = json.loads(a.captions.read_text())
        caps = [{**c, "start": mt(c["start"]), "end": mt(c["end"])} for c in cap["captions"]]
        caps = [c for c in caps if c["end"] - c["start"] >= 0.15]
        args = {"path": proj, "captions": caps}
        for k in ("offsetY", "style"):
            if k in cap:
                args[k] = cap[k]
        steps.append({"tool": "captions_add", "args": args})

    if a.titles:
        for t in json.loads(a.titles.read_text()):
            t = {**t, "start": mt(t["start"]), "duration": round(mt(t["start"] + t["duration"]) - mt(t["start"]), 3)}
            steps.append({"tool": "title_add", "args": {"path": proj, "above": True, **t}})

    steps.append({"tool": "project_save", "args": {"path": proj}})
    for t in [x for x in a.preview.split(",") if x]:
        steps.append({"tool": "preview_frame", "args": {"path": proj, "time": mt(float(t)), "width": w // 2, "height": h // 2,
                                                        "output": f"{loc}/preview_{mt(float(t)):.1f}.png"}})
    if a.export:
        steps += [{"tool": "export_start", "args": {"path": proj, "output": str(Path(a.export).expanduser())}, "as": "ex"},
                  {"tool": "export_wait", "args": {"job": "$ex.job", "timeoutSeconds": 900}}]
    steps.append({"tool": "timeline_read", "args": {"path": proj}})
    a.out.write_text(json.dumps(steps, indent=1))
    print(f"{len(steps)} steps -> {a.out}")


if __name__ == "__main__":
    main()

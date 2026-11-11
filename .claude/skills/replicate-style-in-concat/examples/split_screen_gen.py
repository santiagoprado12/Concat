#!/usr/bin/env python3
"""EXAMPLE generator: the Concat MCP steps for a split-screen reel (two raw takes of one person, each half speaks in turn).

This is the real generator of the 2026-11-07 reel with the client's texts replaced by placeholders. It is reference code to
COPY AND ADAPT, not a tool to run as it is: it expects the files the analysis steps produce (see references/playbook.md):
  /pieces.json   speaking pieces per turn: [{"turn","who","pieces":[{"in","frames","dur"}]}]   (phrases.py + your choice of takes)
  /over.json     piece length overrides in frames, key "t3_0" (cuts placed in the pauses found with audio_peek.py)
  /listen4.json  listening pieces per person and turn (output of the listener search, references/hacks.md section 6)
  /W2.json       caption words with times per piece (align_captions.py)
  /assets/*.png  the image cards;  sounds under /sfx/
What it shows how to do (all verified): the source in/out recipe with speed and reversed pieces, a masked top layer,
per-layer white balance, voice chain on speakers only (listeners muted), title and plates on their own lanes, cards that
rise 10 % while fading in, one-word captions, one soft swish per card, previews, save, export.
Usage: JOB=~/concat-analysis/<job> python3 split_screen_gen.py NAME [--export]  then mcp_run.py --bin <concat> /NAME.steps.json
"""
import json, os, sys

HOME = os.path.expanduser("~")
J = os.environ.get("JOB", f"{HOME}/concat-analysis/job")
NAME = sys.argv[1] if len(sys.argv) > 1 else "reel_v1"
P = f"{J}/proj/{NAME}"
OUT = f"{J}/out/{NAME}.mp4"
FPS = 30
LA, LB = float(os.environ.get('LA', 0)), float(os.environ.get('LB', 0))   # CONTAINER durations of raw A and raw B (ffprobe format=duration), never the video stream's
RAWA, RAWB = f"{J}/audio/rawA_clean.MOV", f"{J}/audio/rawB_clean.MOV"   # voice-cleaned copies (ffmpeg highpass + afftdn), picture untouched
ZOOM = 1.12                     # crops the feet/floor; the mask on the top layer keeps the seam in the middle
ESP, CREAM, MAUVE = "#2B221E", "#F4EFD0", "#8E5E67"


def fr(x):  # snap seconds to the frame grid
    return round(x * FPS) / FPS


pieces = {p["turn"]: p for p in json.load(open(f"{J}/pieces.json"))}
listen = json.load(open(f"{J}/listen4.json"))

# words per piece: {(turn, piece_index): [(word, seconds from the piece start), ...]} from align_captions.py
W = {(k.split('_')[0], int(k.split('_')[1])): [tuple(x) for x in v] for k, v in json.load(open(f'{J}/W2.json')).items()}
# piece length overrides in frames (cuts placed in the pauses found in the audio energy)
OVER = {(k.split("_")[0], int(k.split("_")[1])): v for k, v in json.load(open(f"{J}/over.json")).items()}

order = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10"]
turns = []
t0 = 0
for tn in order:
    pc = pieces[tn]
    items = []
    off = 0
    for i, p in enumerate(pc["pieces"]):
        n = OVER.get((tn, i), p["frames"])
        items.append({"in": p["in"], "n": n, "off": off, "words": W[(tn, i)]})
        off += n
    turns.append({"tn": tn, "who": pc["who"], "start": t0, "n": off, "pieces": items})
    t0 += off
TOTAL = t0  # frames
T = TOTAL / FPS

steps = []
S = steps.append


def step(tool, args, as_=None, **kw):
    d = {"tool": tool, "args": {"path": P, **args}}
    if as_:
        d["as"] = as_
    d.update(kw)
    S(d)


step("project_create", {"location": f"{J}/proj", "name": NAME, "video": {"width": 1080, "height": 1920, "rateNum": 30, "rateDen": 1}})
# project_create takes `location`+`name` and has no `path`: patch it
steps[0]["args"] = {"location": f"{J}/proj", "name": NAME, "video": {"width": 1080, "height": 1920, "rateNum": 30, "rateDen": 1}}

step("media_import", {"file": RAWA}, "mA")
step("media_import", {"file": RAWB}, "mB")
for k, f in (("P01", "P01.png"), ("P02", "P02.png"), ("P03", "P03.png"), ("P04", "P04.png"), ("P05", "P05.png"), ("P06", "P06.jpg"), ("P08", "P08.png"), ("P09", "P09.png"), ("P11", "P11.png")):
    step("media_import", {"file": f"{J}/assets/{f}"}, "m" + k)
step("media_import", {"file": f"{HOME}/concat-analysis/sfx/pack/pop.wav"}, "mPop")
step("media_import", {"file": f"{HOME}/concat-analysis/sfx/pack/swish_light.wav"}, "mSwish")

# lanes: T1 A, T2 B, T3 images, T4 emoji1; new: emoji2, emoji3, title, plate B, plate A, VS ; sound lanes at the bottom
lanes = {}
for nm in ("img2", "title", "plB", "plA", "vs"):
    step("track_add", {}, "ln_" + nm)
    lanes[nm] = f"$ln_{nm}.createdId"
step("track_add", {"bottom": True}, "ln_pop")
step("track_add", {"bottom": True}, "ln_swish")
lanes["pop"] = "$ln_pop.createdId"
lanes["swish"] = "$ln_swish.createdId"
lanes["img"] = "T3"
lanes["emo1"] = "T4"

VOICE = [{"id": "concat.denoise", "params": {"strength": 100}}, {"id": "concat.enhance-voice", "params": {"amount": 100}}, {"id": "concat.loudness", "params": {"target": -16}}]
WB_A = [{"id": "concat.white-balance", "params": {"temperature": 7300, "tint": 0}}, {"id": "concat.exposure", "params": {"stops": 0.12}}]
MASK_B = {"shape": "linear", "x": 0, "y": 0, "rotation": 90, "invert": True, "feather": 0.14}


import subprocess


def rev_file(who, in_s, src):
    os.makedirs(f"{J}/rev", exist_ok=True)
    out = f"{J}/rev/{who}_{in_s:.3f}_{src:.2f}.mp4"
    if not os.path.exists(out):
        raw = os.environ["RAW_A"] if who == "A" else os.environ["RAW_B"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, in_s - 0.12):.4f}", "-t", f"{src + 0.12:.4f}", "-i", raw, "-vf", "reverse,fps=30", "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", out], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip())
    return out, d


def raw_clip(who, name, start_fr, in_s, n_fr, speaker, speed=1.0, rev_src=None):
    """Place a slice of a raw on its lane with the verified source in/out recipe (speed < 1 plays it slower)."""
    media, lane, L = ("$mA.createdId", "T1", LA) if who == "A" else ("$mB.createdId", "T2", LB)
    in_s = fr(in_s)
    if rev_src:
        path, L = rev_file(who, in_s, rev_src)
        step("media_import", {"file": path}, "rv" + name)
        media = f"$rv{name}.createdId"
        in_s = 0.0
    D = n_fr / FPS                      # timeline length
    st = start_fr / FPS
    step("clip_add", {"mediaId": media, "trackId": lane, "start": round(st, 4)}, name)
    if speed != 1.0:
        step("clip_speed", {"clipId": f"${name}.createdId", "speed": speed})
    step("clip_trim", {"clipId": f"${name}.createdId", "edge": "start", "delta": round(in_s / speed, 4)})
    step("clip_trim", {"clipId": f"${name}.createdId", "edge": "end", "delta": -round((L - in_s) / speed - D, 4)})
    step("clips_move", {"moves": [{"clipId": f"${name}.createdId", "start": round(st, 4), "trackId": lane}]})
    patch = {}
    if who == "A":
        patch["videoEffects"] = WB_A
    if speaker:
        patch["filters"] = VOICE
    else:
        patch["muted"] = True
    step("clip_update", {"clipId": f"${name}.createdId", "patch": patch})
    step("clip_transform", {"clipId": f"${name}.createdId", "scale": ZOOM})
    if who == "B":
        step("clip_mask", {"clipId": f"${name}.createdId", "mask": MASK_B})


for t in turns:
    sp, ls = t["who"], ("B" if t["who"] == "A" else "A")
    for i, p in enumerate(t["pieces"]):
        raw_clip(sp, f"s_{t['tn']}_{i}", t["start"] + p["off"], p["in"], p["n"], True)
    lp = listen[ls][t["tn"]]
    diff = t["n"] - sum(q["n"] for q in lp)
    if diff:
        lp[-1]["n"] += diff
        lp[-1]["speed"] = round(lp[-1]["src"] / (lp[-1]["n"] / FPS), 3)
    acc = 0
    for i, p in enumerate(lp):
        raw_clip(ls, f"l_{t['tn']}_{i}", t["start"] + acc, p["start"], p["n"], False, p.get("speed", 1.0), p["src"] if p.get("rev") else None)
        acc += p["n"]
    assert acc == t["n"], (t["tn"], acc, t["n"])

# ---- fixed overlays (whole video)
def still(lane, mid, name, start, dur, scale, ox, oy):
    step("clip_add", {"mediaId": f"${mid}.createdId", "trackId": lane, "start": round(start, 4)}, name)
    step("clip_trim", {"clipId": f"${name}.createdId", "edge": "end", "delta": round(dur - 5.0, 4)})
    step("clip_transform", {"clipId": f"${name}.createdId", "scale": scale, "offsetX": ox, "offsetY": oy})



DM = "Open Sans"
step("title_add", {"start": 0, "duration": round(T, 4), "offsetY": -0.35, "trackId": lanes["title"],
                   "style": {"content": "Title line one\nline two", "fontFamily": DM, "fontSize": 0.040, "fontWeight": 400, "color": ESP, "shadow": False, "lineHeight": 1.05, "align": "center"}}, "title")
plate = {"fontFamily": DM, "fontSize": 0.019, "fontWeight": 400, "shadow": False, "lineHeight": 1.05, "align": "center",
         "backgroundPaddingX": 0.03, "backgroundPaddingY": 0.010, "backgroundRadius": 0.007}
step("title_add", {"start": 0, "duration": round(T, 4), "offsetY": -0.23, "trackId": lanes["plB"],
                   "style": {**plate, "content": "Left label,\nline two", "color": ESP, "background": CREAM}}, "plB")
step("clip_transform", {"clipId": "$plB.createdId", "offsetX": -0.23})
step("title_add", {"start": 0, "duration": round(T, 4), "offsetY": -0.23, "trackId": lanes["plA"],
                   "style": {**plate, "content": "Right label,\nline two", "color": CREAM, "background": MAUVE}}, "plA")
step("clip_transform", {"clipId": "$plA.createdId", "offsetX": 0.27})
step("title_add", {"start": 0, "duration": round(T, 4), "offsetY": -0.23, "trackId": lanes["vs"],
                   "style": {"content": "VS", "fontFamily": DM, "fontSize": 0.016, "fontWeight": 400, "italic": False, "color": ESP, "shadow": False, "background": CREAM, "backgroundPaddingX": 0.014, "backgroundPaddingY": 0.007, "backgroundRadius": 0.012}}, "vs")
step("clip_transform", {"clipId": "$vs.createdId", "offsetX": 0.02})

# ---- image cards (bottom centre; right side for the closing)
def card(mid, name, start_fr, end_fr, scale, ox, oy, lane="img", flip=False):
    st, d = start_fr / FPS, (end_fr - start_fr) / FPS
    still(lanes[lane], mid, name, st, d, scale, ox, oy)
    if flip:
        step("clip_update", {"clipId": f"${name}.createdId", "patch": {"flipH": True}})
    f = min(0.22 / d, 0.9)
    for prop, v0, v1 in (("opacity", 0.0, 1.0), ("offsetY", oy + 0.10, oy)):
        step("keyframe_set", {"clipId": f"${name}.createdId", "property": prop, "at": 0.0, "value": v0})
        step("keyframe_set", {"clipId": f"${name}.createdId", "property": prop, "at": round(f, 4), "value": v1})


t = {x["tn"]: x for x in turns}
p03_end = t["t3"]["start"]                      # end of the first two turns
p04_end = t["t4"]["start"] + t["t4"]["n"]       # end of turn 4
# P03: whole of turns 1-2; P04: turn 3 (mirrored copy with flipH when the same object appears twice)
card("mP03", "cP03", 0, t["t3"]["start"], 0.32, 0.0, 0.22)
card("mP04", "cP04", t["t3"]["start"], t["t4"]["start"], 0.40, -0.20, 0.26)
card("mP04", "cP04b", t["t3"]["start"], t["t4"]["start"], 0.40, 0.20, 0.26, lane="img2", flip=True)


def wtime(tn, i, word, nth=0):
    """Timeline time (s) of a word of a speaking piece, from the caption word list."""
    cnt = 0
    for w_, tt in W[(tn, i)]:
        if w_.strip(".,").lower() == word.lower():
            if cnt == nth:
                return t[tn]["start"] / FPS + t[tn]["pieces"][i]["off"] / FPS + tt
            cnt += 1
    raise KeyError(word)


FIRST_WORD, SECOND_WORD, THIRD_WORD = 'word1', 'word2', 'word3'   # words of turn 4 that start each image (EDIT)


def fr_(x):
    return int(round(x * FPS))


# turn 4: an image per said phrase, anchored to words that are said (wtime), never to timestamps
t4s, t4e = t["t4"]["start"], t["t4"]["start"] + t["t4"]["n"]
a_tape = fr_(wtime("t4", 0, FIRST_WORD) - 0.05)
a_two = fr_(wtime("t4", 0, SECOND_WORD) - 0.05)
a_one = fr_(wtime("t4", 0, THIRD_WORD) - 0.05)
card("mP06", "cP06", a_tape, a_two, 0.30, 0.0, 0.22)
card("mP04", "cP04c", a_two, a_one, 0.40, -0.20, 0.26)
card("mP04", "cP04d", a_two, a_one, 0.40, 0.20, 0.26, lane="img2", flip=True)
card("mP04", "cP04e", a_one, t4e, 0.48, 0.0, 0.26)
CARD_STARTS = [a_tape, a_two, a_one]
# one image per turn: each stays until the next turn starts
card("mP05", "cP05", t["t5"]["start"], t["t6"]["start"], 0.62, 0.0, 0.30)
card("mP08", "cP08", t["t6"]["start"], t["t7"]["start"], 0.55, 0.0, 0.28)
card("mP09", "cP09", t["t7"]["start"], t["t8"]["start"], 0.40, 0.0, 0.22)
card("mP11", "cP11", t["t8"]["start"], t["t9"]["start"], 0.40, 0.0, 0.22)
CARD_STARTS += [t["t5"]["start"], t["t6"]["start"], t["t7"]["start"], t["t8"]["start"]]
# closing, on the right half: first image for the brand's method line, then the tool image
t10 = t["t10"]
p1 = t10["pieces"][0]
p2 = t10["pieces"][1]
method_in = t10["start"] + int(0.3 * FPS)
tool_in = t10["start"] + p2["off"] + int(2.1 * FPS)
card("mP01", "cP01", method_in, tool_in, 0.38, 0.0, 0.285)
card("mP02", "cP02", tool_in, TOTAL, 0.38, 0.0, 0.285)

# ---- captions, one word at a time
caps = []
for tt in turns:
    for p in tt["pieces"]:
        base = (tt["start"] + p["off"]) / FPS
        end_piece = p["n"] / FPS
        ws = [list(x) for x in p["words"]]
        # monotonic with a minimum gap, last word must start at least 0.28 s before the piece end
        for i in range(1, len(ws)):
            ws[i][1] = max(ws[i][1], ws[i - 1][1] + 0.12)
        ws[-1][1] = min(ws[-1][1], end_piece - 0.28)
        for i in range(len(ws) - 2, -1, -1):
            ws[i][1] = min(ws[i][1], ws[i + 1][1] - 0.12)
        for i, (txt, ts) in enumerate(ws):
            s = base + max(ts, 0.0)
            e = base + (ws[i + 1][1] if i + 1 < len(ws) else end_piece - 0.03)
            e = min(e, s + 0.7)
            caps.append({"start": round(s, 3), "end": round(e, 3), "text": txt})
step("captions_add", {"captions": caps, "offsetY": 0.07,
                      "style": {"fontFamily": DM, "fontSize": 0.034, "fontWeight": 400, "color": "#FFFFFF", "shadow": True}})

# ---- sounds (user's palette only, very low)
def snd(mid, lane, name, at, vol, dur):
    step("clip_add", {"mediaId": f"${mid}.createdId", "trackId": lane, "start": round(at, 4)}, name)
    step("clip_update", {"clipId": f"${name}.createdId", "patch": {"volume": vol}})


swishes = [0.0, t["t3"]["start"] / FPS - 0.04, t["t4"]["start"] / FPS - 0.04, method_in / FPS - 0.04, tool_in / FPS - 0.04]
# P03 starts with the title pop; the swish marks P04 in, P04 out, method image in, tool image in
swishes += [c / FPS - 0.04 for c in CARD_STARTS]
for i, at in enumerate(swishes):
    snd("mSwish", lanes["swish"], f"sSw{i}", max(0.0, at), 0.2, 0.2)

# ---- previews, save, export
for tm in (1.0, 8.0, 14.0, 26.0, 36.0, 45.0, 54.0, 62.0, 68.0, T - 1.0):
    step("preview_frame", {"time": round(tm, 2), "output": f"{J}/prev/{NAME}_{int(tm*10):04d}.png", "width": 540, "height": 960})
step("project_save", {})
step("timeline_read", {})
if "--export" in sys.argv:
    os.makedirs(f"{J}/out", exist_ok=True)
    step("export_start", {"output": OUT, "width": 1080, "height": 1920}, "exp")
    step("export_wait", {"job": "$exp.job", "timeoutSeconds": 900})

json.dump(steps, open(f"{J}/{NAME}.steps.json", "w"))
print("turns:", [(x["tn"], x["who"], round(x["start"] / FPS, 2), round(x["n"] / FPS, 2)) for x in turns])
print("total", round(T, 2), "s;", len(steps), "steps; captions", len(caps))

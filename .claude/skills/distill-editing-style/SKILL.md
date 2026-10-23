---
name: distill-editing-style
description: Read the analysis of a reference video (style-report, contact sheets, transition strips, spectrograms, optional raw-to-edited alignment) and write a reusable editing-style profile - pacing, transition vocabulary mapped to real Concat effect ids, title and caption looks, colour treatment, and sound rules such as whoosh-on-cut offsets, impacts on text, music level - each tagged measured, inferred or visual. Use this after analyze-reference-video whenever the user wants to learn, describe, save or copy an editing style, or before replicating one in Concat. Also use it when asked "what style is this" or "what makes this edit feel the way it does".
---

# Distilling an editing style

The output is a profile another session can replicate from without seeing the reference. Its value is being honest about what was measured and what was guessed.

## Inputs

From `analyze-reference-video` (run it first): `style-report.json`, `contact_NN.jpg`, `transitions/*.jpg`, `spectrogram_NN.png`, and `alignment.json` if raw footage was supplied. **Open the images with Read** - the numbers alone do not show typography, framing, grade or what a transition looks like.

## Procedure

1. Read `style-report.md`, then the contact sheets, a sample of transition strips (at least every distinct kind) and the spectrograms around the busiest sound moments.
2. Pacing: average and median shot length, cuts per minute, whether pace accelerates, any rhythm tied to the beat grid (`cuts_within_60ms_of_beat`).
3. Transitions: count how many boundaries are hard cuts versus something else, from the strips. For each other kind pick the closest real Concat id: get the list from the MCP `effects_list` with `kind: "transition"` (or `python3 -I <repo>/.claude/skills/replicate-style-in-concat/scripts/mcp_run.py --bin <concat> --list-tools` then call `effects_list`). **Use ids exactly as listed (`concat.dissolve`, `concat.blur-dissolve`, ...); do not invent one.** If nothing fits, say so and name the nearest.
4. Text: for each title/caption style note content type, position, size relative to frame height, weight, colour, stroke, background plate, animation, and when it appears relative to speech/cuts. Concat's `title_add` style fields are `content, fontFamily, fontSize (fraction of frame height), fontWeight, color, align, background, strokeColor, strokeWidth, shadow, opacity, tracking, lineHeight`.
5. Look: aspect ratio, fps (from `probe`), zoom or crop habits, speed ramps (from alignment `speed`), colour grade in words. Map to a real `filters`/`videoEffects` id from `effects_list` only if one clearly matches; otherwise list it under unknowns.
6. Sound, the part most tools skip. Write each rule as *trigger -> sound -> timing -> level*, from `correlations` and the spectrograms. Examples of the shape: "on 70% of hard cuts longer than 0.6 s: whoosh_swell, peak 0.12 s before the cut, about -9 dB under dialogue"; "impact on every title appearance, on the frame it appears"; "riser during the 2 s before each section change"; "music bed -14 LUFS, ducked about 8 dB under speech". Give the integrated loudness target from `audio.json`.
7. Tag every claim: **measured** (a number from the scripts), **visual** (read off the images), **inferred** (a guess from patterns). Put what could not be established in `unknowns`.

## Output

Write `style.json` and a short `style.md` next to the analysis (under `~/concat-analysis/<name>/`). Suggested `style.json` shape, adapt freely:

```json
{
  "name": "...",
  "source": {"file": "...", "duration_s": 0, "canvas": {"width": 0, "height": 0, "fps": 0}},
  "pacing": {"avg_shot_s": 0, "cuts_per_minute": 0, "notes": "", "confidence": "measured"},
  "transitions": [{"kind": "hard cut", "share": 0.0, "confidence": "measured"},
                  {"kind": "dissolve", "concat_id": "concat.dissolve", "duration_s": 0.3, "share": 0.0, "confidence": "visual"}],
  "text": [{"role": "title", "style": {"fontWeight": 800, "color": "#ffffff", "fontSize": 0.09}, "placement": "...", "confidence": "visual"}],
  "look": {"grade": "...", "filters": [], "confidence": "inferred"},
  "sound": {
    "loudness_lufs": 0,
    "music": {"bpm": 0, "level_note": "", "ducking_db": null},
    "rules": [{"trigger": "hard cut > 0.6 s", "sound": "whoosh_swell", "offset_s": -0.12, "level_db": null, "coverage": 0.0, "confidence": "measured"}]
  },
  "shots": [{"index": 0, "start": 0, "duration": 0, "raw_in": null, "speed": 1, "transition_in": null}],
  "unknowns": []
}
```

`shots` is filled only when `alignment.json` exists; copy `confidence` per shot so the replicator knows which to double-check.

## Rules of thumb

- A style already learned from the user's earlier reels is in `propose-edit-plan/references/house-style.md`; start from it and record only what differs.

- Fewer, truer rules beat many speculative ones. A rule with `coverage` under about 0.3 is a flourish, not a style.
- Do not claim a sound is a specific recording ("the Vine boom"); say "low impact, decay about 1 s".
- If the analysis disagrees with what the frames show, trust the frames and re-run the analysis with different thresholds rather than papering over it.
- When this work leads to a lesson about a tool's limits, record it in `replicate-style-in-concat/references/learnings.md`.

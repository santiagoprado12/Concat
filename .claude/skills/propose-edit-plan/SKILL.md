---
name: propose-edit-plan
description: Before editing a new raw video in Concat, analyze it and publish an editing proposal as a design canvas the user can read and approve - typography and colour specimens, a block-by-block map of the edit (which take, what appears, what sounds), the list of images and videos still needed with placeholder codes, effects and sound, and the open decisions. Use this whenever the user hands over a new raw video (or says "start", "propose an edit", "show me how it would look") and nothing has been built yet, and whenever they want to agree style, assets and length first. It is the first step of the workflow: propose-edit-plan, then analyze-reference-video, distill-editing-style and replicate-style-in-concat.
---

# Proposing an edit before building it

The agreed way of working with this user: **propose on a canvas, get decisions, then build with placeholders, then refine.** Nothing is cut in Concat until the proposal is approved. The proposal is a private design canvas (the Artifact tool with the Design type), written in the user's language.

## 1. Look at the video first

Use `analyze-reference-video`. For one person talking with many retakes (the usual case):

```bash
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name -of compact RAW.mov
uv run <skills>/analyze-reference-video/scripts/analyze.py all RAW.mov --out ~/concat-analysis/<job>/raw --max-strips 0
uv run <skills>/analyze-reference-video/scripts/phrases.py RAW.mov --model <ggml-base.bin> --lang <xx> --out ~/concat-analysis/<job>/speech
```

Read the contact sheet (who, where, framing, an end card from another app in the last seconds), the loudness (`style-report.json`), and the phrase list. From the phrase list work out the script (what lines exist, how many takes of each) and the chosen takes. Say the number of takes, the length of the raw, the length the edit will have, and the loudness against the earlier reels.

## 2. Check what Concat can really do

Never propose an effect, a font or an animation without checking: `effects_list` (via `replicate-style-in-concat/scripts/mcp_run.py`) gives the real ids; the fonts Concat renders are the files in `src/crates/concat-text/fonts` (Hanken Grotesk, Montserrat, DM Serif Display, Inter, Space Grotesk and more); title styling has no animation, so typed text is emulated by `takes_to_plan.py` (one clip per letter). Say plainly what is not possible and how it is solved.

## 3. The canvas: five artboards, 1280 px wide

Start it with the Artifact tool (`quickstart` intent `design`, then publish with the Design `type_url`, `auto_open: after_first_write`), upload two or three small frames (JPEG, about 320x576) as assets for the specimens, then write `project/canvas.json` first and **one artboard at a time**, publishing each. Fonts through one Google Fonts `<link>` (the Concat fonts are on Google Fonts, so the specimens render the same). No emoji, real contrast, copy as literal markup.

1. **Resumen** (`Main`): working title, key numbers (raw length, edit length, number of takes, loudness), three frames with the caption and title style laid over them, how it is built in four steps, and the decisions the user must take (length, music, how to write names, reuse of earlier assets, colour match).
2. **Tipografía y color**: one specimen per role (caption, step title, accent word, label chip) with its Concat values (font, weight, size as a fraction of frame height, colour, shadow, position), the palette with hex codes and where it comes from, and the values as they are typed in Concat. See `references/house-style.md`.
3. **Mapa de la edición**: one row per block (time out, what is said with the chosen takes in raw seconds, what is on screen with placeholder codes, which sounds). Header row, colour-coded kind tags (B-ROLL, CAPTURA, IMAGEN, ICONO). Height about 1960 for ten blocks.
4. **Imágenes y videos que faltan**: one card per placeholder (`P01`...): kind, what exactly to film or capture, duration, who provides it, whether an earlier reel already has it. Totals by kind. How to name the files (`P12-name.png`). Say what happens if something does not arrive: a labelled placeholder with its time slot stays in the timeline.
5. **Efectos y sonido**: image effects (cuts, punch-in, slide-in, typed text, the single soft transition), audio (voice loudness target, effect palette and licence, music or none), and what Concat cannot do with the workaround.

Every claim on the canvas must be true of the installed Concat; where something was only verified by measurement and not by ear, say so.

## 4. After the user answers

Record the decisions (length, music, spelling, assets) in `takes.json`/`overlays.json`, build with `replicate-style-in-concat` (`takes_to_plan.py`, `make_placeholders.py`, `make_icons.py`, `build_steps.py`, `mcp_run.py`), preview frames, export, open the project with `concat --project <folder>` and ask for the fine-tuning. Update `replicate-style-in-concat/references/learnings.md` with whatever was new.

## Things that went wrong before

- Publishing with `edits` is refused when a hook is configured for file edits: edit the file, then publish it without `edits`.
- Two Writes in a row work but the type's instructions say one artboard per publish; follow that.
- A board's height is a guess: over-tall is better than clipped, and the index (`canvas.json`) must be re-sent when a size changes.
- The canvas embeds frames of a real person: it is private by default, say so, and never share it on the user's behalf.
- Brand names heard by the transcriber are guesses: put the spelling to the user as a decision.

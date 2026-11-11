---
name: video-edit-playbook
description: The standard step-by-step process for turning a user's raw video (and optionally a reference, a class or a script) into a finished reel in Concat, from intake to delivery, with the checks (gates) that must pass at each step and the exact commands. Use this FIRST whenever the user hands over raw footage, a reference reel or link, a course lesson about editing, or says "edita esto", "monta el video", "haz el reel", "copia este estilo", "usa lo que aprendiste" - and whenever a video the user reviews comes back with complaints. It ties together fetch-reference-video, fetch-course-lesson-video, analyze-reference-video, distill-editing-style, propose-edit-plan, replicate-style-in-concat and upload-to-drive-via-browser, and points to references/hacks.md for every trick found so far (see the footage, link transcript to sound, find effects in a reference, stretch footage with slow motion/reverse/boomerang, invisible cuts, voice cleaning, colour matching, fast review renders).
---

# Video edit playbook (the standard process)

> **Version: written for Concat 0.2.10.** Check `concat --version` first; if the binary is older, rebuild it (`references/concat-version.md` in `video-edit-playbook` has the commands, what changed since 0.2.8, and the fix for the masks of old projects).

Written after four videos with this user (a list reel, a copy of a collaborator's CapCut edit, a talking-head reel with B-roll and a split-screen two-character reel, 17 review rounds). Following it in order gets similar results with fewer rounds. **Every trick, number and command is in `references/hacks.md`; this page is the order of work and the gates.** Read `propose-edit-plan/references/house-style.md` ("Our style in one page") and `replicate-style-in-concat/references/learnings.md` before step 1.

Claude cannot watch or hear. Everything below exists to turn video and sound into **images and numbers Claude can read**: a grid of frames (`frames_grid.py`), sound levels (`audio_peek.py`), face metrics (`face_gaze.py`), differences between frames (`frame_descriptors.py`), spectrograms. When in doubt, make a picture of it and look.

## Folder layout (always the same)

```
~/concat-analysis/<job>/        never inside the repo (public) and always under home (Concat writes only there)
  raw/            copies or cleaned versions of the raw files (*_clean.MOV = picture untouched, voice cleaned)
  speech/ words/  phrases.py output, one wav + whisper json per chosen piece
  gaze/ desc/     face_gaze.py / frame_descriptors.py output per raw
  assets/         icons, images from the user, emoji PNGs, placeholders
  sfx/            the approved sounds (copy from replicate-style-in-concat/sounds/)
  proj/<name>_vN/ one Concat project per version (never edit a version the user has open)
  out/            exports: <name>_vN_baja.mp4 (review, 540x960) and <name>_alta.mp4 (final)
  steps/ logs/    the generated steps.json per version and the mcp_run logs
```
`S=<repo>/.claude/skills`; scripts run with `uv run` (PEP 723 headers) or `python3 -I`. Python 3.12 for MediaPipe (`uv run --python 3.12`).

## The twelve steps

Each step ends with a **gate**: do not move on until it passes. Say the result to the user in one or two sentences (Spanish, short; they read on a phone).

### 0. Intake (2 minutes)
- Ask nothing you can find out. Note what arrived: raw file(s), reference (link, video, screenshot, screen recording), script/table, extra context, brand.
- Check tools once: `ffmpeg -version`, `uv --version`, `whisper-cli --help`, the Concat binary (**`<repo>/src/target/debug/concat --version` must say 0.2.10 or newer, otherwise rebuild: read `references/concat-version.md` first**; it also lists what changed from 0.2.8 and the masks of old projects), the Whisper model (`~/Library/Application Support/app.concat.editor/whisper-models/ggml-base.bin`; ask before downloading anything).
- **Gate:** you know which of the four situations this is: (a) one raw take of a person with retakes + a reference to copy; (b) raw + the reference's edited version (map it with `align_audio.py`); (c) a screen recording of someone else's finished edit to copy exactly; (d) two or more raw takes to be combined (split screen, before/after).

### 1. Reference in, if there is one
- Link: `fetch-reference-video` (yt-dlp; only that video). Private lesson page: `fetch-course-lesson-video` (their Chrome). Class video: transcribe it (hacks §3) and turn the teacher's instructions into a checklist of editing rules; confirm them with the user before applying.
- Analyse it: `analyze.py all` (cuts, contact sheets, transitions, loudness, spectrograms, sound events), `transitions.py` for soft cuts, `sounds.py` only after asking (Demucs download). **How an element appears** (pop, fade, slide, hard cut) is seen with `frames_grid.py REF --times T:T+1:0.0667` (15 frames per second in one image). Where sounds sit: hacks §3.
- **Gate:** a short list of measured facts about the reference (shots, pacing, text style, grade, sound design or "voice only", music or none), each tagged measured / seen / guessed.

### 2. Understand the raw footage
- `ffprobe` (size, fps, **container duration**, which stream is longer), `analyze.py all RAW --max-strips 0`, `phrases.py` (voiced regions by energy, then each phrase transcribed alone; do not trust one whole-file Whisper run: its times drift by seconds).
- Look: contact sheet, then `frames_grid.py` on the first and last 10 seconds (end cards of another app, the person walking in, a laugh before the first line: hacks §3). Check loudness (raw takes of this user are -19 to -33 LUFS) and noise (hacks §8).
- Write the script as lines and takes: how many takes of each line, which is the last good one, which transcripts are garbled.
- **Gate:** you can say: raw length, number of lines/takes, chosen take per line, edit length, loudness, noise type, and anything missing (a person who must listen, a second angle, B-roll).

### 3. Feasibility before promising
- Count what the plan needs against what exists (hacks §6: the listener capacity formula). If short, put numbers and two or three options on the proposal; never discover it after approval.
- Check Concat: `effects_list`, fonts (`src/crates/concat-text/fonts` plus installed system fonts), what cannot be done (hacks §13).
- **Gate:** every element of the plan is something you verified Concat does, or the proposal says how it is emulated.

### 4. Propose on a canvas, wait for approval
`propose-edit-plan`: five boards (summary and decisions, type and colour, map of the edit, missing images, effects and sound), private. Use `house-style.md` defaults and say where you depart. Put frames of the user's own footage in it. Ask the open decisions as numbered choices. **Nothing is built before "aprobada".** Later changes decided in chat make the canvas stale: update it at the end or say it is out of date.
- **Gate:** written approval or answers to every decision.

### 5. Prepare assets (before building)
- **Voice**: ffmpeg `highpass=f=90` twice + `afftdn=nr=20` on a copy of the raw (picture stream copied, rotation kept, `-map 0:v:0 -map 0:a:0`); find a motor hum with `audio_peek.py tones` first (hacks §8).
- **Fonts**: Open Sans static instances if used (hacks §7); anything else bundled. Ask before downloading.
- **Images**: transparent PNG for objects (the user supplies them later: keep a per-moment list with the time; a labelled placeholder holds the slot), emoji PNGs through CoreText, icons with `make_icons.py`, cards with `make_placeholders.py`.
- **Sounds**: only the eight approved, copied to `sfx/` (see `replicate-style-in-concat/sounds/README.md`).
- **Reversed/boomerang pieces** and slow-motion plans: `make_reversed.py` (hacks §5).
- **Gate:** every file the build will reference exists under home with an absolute path.

### 6. Plan the cuts from words, not from timestamps
- Per chosen piece: transcribe alone with `--prompt` (script keywords, names); write the caption text yourself; `align_captions.py` puts your words on Whisper's times. Cut start = 0.12 s before the first word (never longer dead air), end = after the word dies (`audio_peek.py cuts` > -38 dB means cut too early; extend up to 0.8 s). Cut pauses out; splice a clean repeat over a stumble (70 ms gap).
- Anchor every overlay (titles, cards, sounds) to a **said word** (`takes_to_plan.py` anchors, or the `wtime(turn, piece, word)` helper in `examples/split_screen_gen.py`).
- All times on the frame grid (`round(t*fps)/fps`); all trims from the **container** duration.
- **Gate:** a plan file (`pieces.json`/`takes.json` + words + overlays) that a generator reads; zero hand-typed seconds in the generator.

### 7. Build with a generator through MCP
- One generator script writes `steps.json` (copy `replicate-style-in-concat/examples/split_screen_gen.py` for layered edits or use `build_steps.py` for voice-led reels); `mcp_run.py` runs it. New project folder per version (`<name>_vN`). Mint every lane first (`track_add`), pass `trackId` explicitly, use `title_add above: true` only for the main title. Step names without dots. End with `project_save`, then previews, then exports.
- Voice chain on **every** voice clip, in this order, without being asked: `concat.denoise` 100, `concat.enhance-voice` 100, `concat.loudness` -16. Listening/other clips muted.
- Long runs: `nohup python3 -I mcp_run.py ... > log 2>&1 &` and poll the log for `"state":"done"` (a foreground tool call dies at 10 minutes).
- **Gate:** the run reports 0 failures; `timeline_read` shows the expected number of clips on each lane.

### 8. Verify yourself before the user sees it (the QA list)
Run all of these on the **export**, not on the project:
1. `ffmpeg -i out.mp4 -vf blackdetect=d=0:pic_th=0.9 -an -f null -` -> no black frames at any cut.
2. `audio_peek.py cuts out.mp4 <every cut time>` -> no cut with the last 80 ms above -38 dB; `audio_peek.py silences out.mp4 --thr -45 --min 0.25` -> no pause the user would call long (the user cut one at second 52).
3. Loudness near -16 LUFS, peak under -1 dBFS (`ffmpeg ... ebur128=peak=true`).
4. Read `concat.json` back: every voice clip lists the three filters in order; muted clips muted; no clip overlaps another on its lane.
5. `frames_grid.py out.mp4 --times <the start of every clip>` and a frame every 0.5 s of anything risky: look for a person looking away, reading, leaning, touching face/hair, a seam colour jump, an image over a face or a caption, text unreadable on its background (measure contrast per zone, hacks §7).
6. Proofread every caption against the script (the user notices a missing phrase).
7. Every image appears only where it is said, at the right time (`frames_grid.py` around each card start).
- **Gate:** every item above passes, or the exception is written in the message to the user.

### 9. Review render, small, then iterate
- `export_start` `width 540 height 960 crf 34` (about 1 minute, 3 MB). Send with `SendUserFile`. Say what changed, what was measured, what was only seen, what Claude cannot judge (sound by ear). Offer choices instead of guessing taste: numbered audio samples (hacks §11), A-D picture sheets (`frames_grid.py --images`).
- Feedback arrives as screenshots with a second each: look at 0.1 s steps around that second (`frames_grid.py --times s-1:s+1:0.1`), fix only that, re-run QA. **Lock** every moment the user calls perfect (copy its pieces, do not re-plan it).
- Keep the previous version's project and render; each change is a new `_vN`.
- **Gate:** the user says it is good ("me gusta", "perfecto", "aprobado").

### 10. Final render and delivery
- Full quality only now: `export_start` 1080x1920 (about 5 minutes, 35-40 MB). Same QA list on it. If the user only has a phone, upload it to the Drive folder they name (ask the folder first): `upload-to-drive-via-browser`.
- Open the final project in the window (`concat --project <folder>`; only after the MCP run ended) when the user wants to fine-tune; after they edit, read their saved `concat.json` for what changed instead of asking for numbers.
- **Gate:** the file is where the user said, and you checked it exists (size, name).

### 11. Clean up
- Move earlier versions' projects/renders to the Trash (never `rm`), keep `assets/` and cleaned audio: projects point at media by absolute path. Ask first if the user did not say "borra".

### 12. Write it down (the part that makes the next video better)
- New tricks, numbers and mistakes -> `learnings.md` (dated entry, how it was found, verified or not) and `references/hacks.md` of this skill when it is a reusable trick; the user's new taste -> `house-style.md` and the memory folder. Commit only when asked (`git commit -s`, noreply identity, no personal data, no footage, no transcripts), push only to `origin` and only when asked.

## Messages to the user (Spanish, short)

- After analysis: raw length, number of takes, loudness, what is missing, the capacity numbers if relevant, and the decisions needed as a numbered list.
- With every review render: **what changed** (one line each), **what I measured**, **what I could not check** (the sound, how it moves), and one question at most.
- Never claim you heard or watched something; say "lo medí" or "lo vi en los fotogramas".

## What went wrong before (so it does not happen again)

1. Planning from detectors only: the numbers let glances down, leaning and hair touching through. Always look at the face crops (hacks §6).
2. Promising a format without counting the footage (the split screen needed 35-42 s of clean listening per person and the raws had 15-30).
3. Building from the video stream's duration instead of the container's: a black frame at a cut (hacks §5).
4. Re-planning moments the user had approved. Lock them.
5. Leaving dead air before the first word or cutting before a word died.
6. Captions missing a phrase, or images over a caption or the other person.
7. Synthesized sound effects (rejected twice): use the eight approved ones, very low.
8. Forgetting the voice chain (denoise 100 / enhance-voice 100 / loudness -16) - twice.
9. Downloading, installing or deleting without asking; using `rm` instead of the Trash.
10. Full-quality renders on every iteration (slow, too big for the phone).
11. Trusting a Whisper transcript on a quiet track (it invented words over silence) or its times on a long file.
12. A grade warmer or brighter than the raw; an exact copy of a reference's grade was "very red and bright".

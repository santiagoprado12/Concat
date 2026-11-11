# Hacks catalogue: every trick found so far, with the command

Organised by the problem you have. `S` = `<repo>/.claude/skills`. "Verified" means run against the real app or the real footage; the date and the long story are in `replicate-style-in-concat/references/learnings.md`. Add new tricks here when you find them.

Contents: 1 see what Claude cannot watch · 2 sound as numbers · 3 link the transcript to real time · 4 find effects and edits in a reference · 5 make footage longer, shorter, slower, reversed · 6 a person who must look alive (the listener) · 7 picture, layout and text · 8 voice and sound · 9 colour · 10 driving Concat · 11 working with the user · 12 learning from a class video · 13 what Concat cannot do

---

## 1. See what Claude cannot watch

**Many frames in one image** (`frames_grid.py`): one picture, up to about 60 tiles, each labelled with its time.
```bash
uv run $S/analyze-reference-video/scripts/frames_grid.py VIDEO --times 3:9:0.5 --out grid.jpg           # a frame every 0.5 s
uv run $S/analyze-reference-video/scripts/frames_grid.py VIDEO --times 51.5:54.5:0.1 --tile 200 --out s.jpg   # around a second the user named
uv run $S/analyze-reference-video/scripts/frames_grid.py REF --times 3.0:4.0:0.0667 --out appear.jpg    # 15 fps: does an item pop, fade, slide or cut in?
uv run $S/analyze-reference-video/scripts/frames_grid.py RAW --times 12.3 40.2 57 --crop 0.5:0.17:0.5:0.62 --tile 200 --out faces.jpg  # crop to a face
uv run $S/analyze-reference-video/scripts/frames_grid.py --images a.png b.png c.png d.png --labels A B C D --tile 400 --out options.jpg  # options for the user
```
- Tiles under about 120 px are not readable for faces: crop first, then tile. Keep a sheet under 2000 px wide; use `--per-sheet`.
- To judge a build: one tile at the **start of every clip** (does the person look away? is there a jump?), then a tile every 0.5 s over anything risky.
- For a reference reel: `analyze.py all` already writes contact sheets (`contact_NN.jpg`, one frame per shot) and `transitions/boundary_*.jpg` (six frames around each cut).
- For a clip with a person: the extreme frames per feature (`face_gaze.py --contact`) calibrate the thresholds on that person first.

**A frame of the real composite** (titles, effects, masks included): `preview_frame {path, time, output: <png under home>, width, height}` then Read the PNG. Use it for colour measurements at the seam, for contrast per zone and to compare before/after.

**Spectrogram picture**: `audio_peek.py spec FILE --from A --to B --fmax 4000 --out spec.png` (voice is horizontal stripes, noise a haze, clicks vertical bars, whooshes broadband blobs, a riser a diagonal). `analyze.py all` writes `spectrogram_NN.png` for the whole file.

## 2. Sound as numbers (Claude cannot hear)

`audio_peek.py` decodes any file (mono 48 kHz) and prints text:
```bash
P=$S/analyze-reference-video/scripts/audio_peek.py
uv run $P env     FILE --from 3.9 --to 5.0 --step 0.02   # level every 20 ms: where the voice really starts/ends
uv run $P silences FILE --thr -45 --min 0.25             # every pause: (start, length)
uv run $P cuts    EXPORT 4.90 11.30 21.37                # level of the last 80 ms before each cut: > -38 dB = cut during a word
uv run $P lead    RAW 18.98                              # dead air after a time (seconds of quiet)
uv run $P tail    RAW 23.85                              # dead air before a time
uv run $P tones   FILE --from 30 --to 31                 # steady tones in a pause (motor hum 68/136/204 Hz)
uv run $P spec    FILE --from 20 --to 40 --out spec.png
```
- Reference levels: speech -35 to -10 dBFS; a room pause around -45 to -60; after Concat's `denoise` a pause can be digital silence (-90 or less), so measure pauses at -45 dB, never against "silence".
- Loudness of a whole file: `ffmpeg -i F -af ebur128=peak=true -f null - 2>&1 | tail -12` (integrated LUFS, LRA, true peak). Target -16 LUFS, peak under -1 dBFS. Raw takes of this user: -19 to -33 LUFS.
- **Pause against speech** (how clean a voice is): `volumedetect` on a pause window and on a nearby word of the same file, in windows with no placed sound effect inside (an effect made the export look 20 dB noisier), on two pauses (one window alone swung 8 dB). Gap in dB is the number to report (raw 12 dB, cleaned 32-37 dB).
- Peaks/clipping: `astats`/`volumedetect` max level; the raw "saturated" complaint measured no clipping (peak -1.8 dBFS).

## 3. Link the transcript to real time

Whisper gives wrong words for names and jargon but good times **if each piece is transcribed alone**; one run over minutes drifts by seconds and stacks words on one time ("Sexto" at 195 s when the voice was at 190 s). Whisper `base` also **invents words over silence or a rumble** (it wrote a sentence over 4 s with no voice).

1. **Find the voiced regions by energy** (exact): `phrases.py RAW --model ggml-base.bin --lang es --out speech` -> `vad.json` regions + one transcript per phrase. A phrase = voiced run with pauses under 0.45 s.
2. **Choose the take** of each line: usually the last good one; skip it if it opens with the person reading; a transcript that matches the script cleanly beats a later take Whisper hears as garbled; a very short phrase before a longer one is a false start; a take split by a pause is worse than a continuous one.
3. **Cut the piece alone and transcribe it with the script's words as a prompt**:
   ```bash
   ffmpeg -y -ss IN -t DUR -i RAW -vn -ac 1 -ar 16000 piece.wav
   whisper-cli -m ggml-base.bin -l es -f piece.wav -ojf -of piece --split-on-word --max-len 1 -np --prompt "Names, brand, jargon, key words of the script."
   ```
   The prompt fixed most misheard words and names. `piece.json` -> `transcription[].offsets.from/to` in ms.
4. **Put your own corrected caption text on those times**: `align_captions.py --text "..." --whisper piece.json --duration D` (matched words keep Whisper's time, unmatched ones are spread by syllable count, times strictly increasing, last word at least 0.25 s before the end). It prints "8/12 words matched": under about 70 % the piece needs a second look. Then list every caption for the user to proofread and flag the guessed words.
5. **Verify with sound before trusting a start time**: `audio_peek.py env RAW --from t-0.5 --to t+1 --step 0.02` shows the level jump (about 15 dB over the pause) where the voice really begins; a "silent start" can be a **laugh** (voice-like energy 4.1-4.4 s that the energy detector called the first phrase): crop the face every 0.1 s (`frames_grid.py --crop`) and watch the mouth.
6. **Cut rules**: start 0.12 s before the first word (never over 0.12 s of dead air: the person looks away or "is not ready"), end after the word dies away (level under -38 dB for 3 hops of 20 ms; extend up to 0.8 s where the voice is still on), tail 0.15 s. `tighten_segments.py` does this for a reference's cuts.
7. **A stumble inside a take**: find the hesitation in the energy envelope (`env`) and splice the clean repeat of the sentence ending from a later retake at a 70 ms gap (the picture jump-cuts and the user accepted it). A pause that "feels long" is the tail of one clip + the lead-in of the next + room tone: trim the tail (`silences` finds it; one at second 52 was 0.3 s).
8. **Anchor everything to words** (`takes_to_plan.py` anchors; `wtime(turn, piece, word)` in `examples/split_screen_gen.py`), never to seconds. Images start 0.05 s before their word; rows that follow a pointing finger start 0.1 s after the word (the finger lands 0-0.2 s after the voice starts: a 4-frame strip per word showed the pattern).
9. **A raw with several languages/people or a quiet track**: check the spectrogram or per-100 ms energy before believing any transcript's times; transcribe each voiced burst alone.
10. Whisper model files are the same ones Concat downloads (`~/Library/Application Support/app.concat.editor/whisper-models/`); ask before downloading one.

## 4. Find effects and edits inside a reference

**What the video is made of**: `analyze.py all REF --out ~/concat-analysis/<job>/ref` (cuts, contact sheets, transitions, loudness, SFX events, beat grid, `style-report.md`). `--cut 12` is the hard-cut sensitivity.

**Cuts and soft transitions**: `transitions.py` (TransNet V2, 31 MB, ask before `--download`): found all 15 card ends within 0.02 s; its cut time is the *next* frame after its index `(i+1)/fps`; open the `gradual_NN.jpg` strips to say dissolve, fade, slide or flash. Cuts inside one talking head (same face before and after) are invisible to both detectors: map the voice instead (`align_audio.py`, §below).

**How an element appears**: 15 fps frames in one image (`frames_grid.py REF --times T:T+1:0.0667`). Hard cut vs fade vs slide vs rise-and-fade vs typed text is visible in 15 tiles.

**Sound effects**:
- `analyze.py sfx` lists events (`hit_thump`, `impact_boom`, `click_pop`, `whoosh_swell`, `riser`) and `correlations.sfx_near_cuts` (median offset of the event minus the cut: negative = the sound leads the cut). `on_beat: true` means it is probably the music. **Read `correlations.sfx_verdict` first**; on a voice-only track the detectors fire on the voice itself (251 false "events"): voice-only audio shows clean harmonic stripes and **that means no sound design**, a valid finding.
- `sounds.py` removes the voice with Demucs (`htdemucs`, 84 MB weights + PyTorch, ask first) then names events with YAMNet: finds *when* effects happen well (36 of 46 at the 20 dB floor, chance 23 %) but *what* they are barely (only long whooshes get a name). Describe the rest by shape (`decay_s`, `centroid_hz`) and the spectrogram. Always report found, precision and the random-shift baseline together.
- Effects mixed under speech are not findable by correlation or swell detection (verified: they are really there; the checks fail). A narrow-band detector found a tonal "ding" (three pulses on 1.4, 2.8 and 5.4 kHz harmonics) in a screen recording: look at the spectrogram for stacked horizontal lines at the pill/row times.
- A reference's sounds are usually its editor's licensed library (CapCut): name them by type, then answer with the user's approved palette (`replicate-style-in-concat/sounds/`).
- Place sounds on the **touch**, not the text: the first sound belonged where the finger touches the row (0.76 s), not where the row appears (0.38 s).

**Screen recording of someone's finished edit** (a phone recording of CapCut's preview):
1. Crop the 9:16 preview area; cuts = frame-difference spikes on the person region; an overlay's on/off frame = count of pure-white pixels in its box (a pill, icon and label appear on one frame with no fade).
2. Its audio lags its picture (0.19 s measured). `align_audio.py RAW EDIT` for segment offsets on the audio clock; **`picture_sync.py`** corrects them from the picture (offset constant per segment, 0.17-0.23 s); raw in-point = audio offset + that.
3. Framing and grade by closed loop: `register_frames.py raw.png edit.png ...` (SIFT + RANSAC on the static room) gives scale, rotation (clockwise = Concat's positive), offsetX/Y; render a `preview_frame` with those numbers and register it again (residual under 0.1 degree and 2 px). The grade was a warm shift (white-balance 5150 K); **do not copy the grade as the goal**, ship a little cooler and darker and say what the reference measured.
4. Text layout from measured boxes (line height 0.78 of font size; label centre is the same for one or two lines); fonts Concat lacks are replaced by the closest bundled one, about 1.22x the size to match widths.

**Pairing raw and edited**: varied footage -> `align.py` (picture); talking head -> `align_audio.py` (log-mel, 1 s windows, boundaries to 10 ms, score 0.76-0.92 good, under 0.55 unreliable; picture alignment on a talking head is wrong). B-roll is laid over a voice track that continues: rebuild the voice from segments, cover the `other` shots with whatever belongs there.

**Score your replica**: `analyze.py all out.mp4` then `compare.py ref replica` (cuts found/missing/extra with timing error, pacing, loudness, off-beat effects, `side_by_side.jpg`). Neighbouring placeholders of the same colour hide cuts from the detector.

## 5. Make footage longer, shorter, slower, reversed (the stretching tricks)

Concat has **per-clip speed** (`clip_speed`), no reverse playback and no freeze-extend, so:

| Need | Trick |
| --- | --- |
| A piece too short for the other person's turn | Play it **slower**, but only where the person is still (table in §6). 2 s of calm footage at 0.5x fills 4 s. |
| Still too short | **Boomerang**: forward then the same frames backwards from the pivot frame (cut difference 0 at the join) in one file: `make_reversed.py RAW --in S --len L --out boom.mp4 --boomerang` (`--reverse-first` for backwards then forward). Make the reverse slightly slower than the forward part. Only for pieces whose pose stays within about 0.02 of the pivot: a reversed lean looked like "forward then back" and was rejected. Prefer one or two long pieces over many 1 s pieces. |
| A reversed piece | `make_reversed.py RAW --in S --len L --out rev.mp4`: it starts exactly on the last source frame, has 0.12 s spare frames at the tail, video only, 30 fps. Import it as media; its own `in` is 0 and `L` is its container duration (printed). |
| The same object twice (two chairs) | One transparent PNG placed twice, the second with `clip_update patch {"flipH": true}`. |
| Repeat footage without it being obvious | Same source never in adjacent turns of one person; at most two uses of a frame; soft cuts (difference under about 9); boomerang or slow versions count as different. |
| Shorter | Cut pauses between phrases (keep 0.12 lead / 0.15 tail); speed up only if the user allows; drop the weakest take. |
| Count the capacity before promising | clean seconds / lowest allowed speed vs seconds needed (§6). |

**Trim recipe with speed and offsets** (verified, no black frame at any cut): for a raw `in` seconds long container `L`, wanted timeline start `S`, timeline length `D`, speed `v`:
1. `clip_add {mediaId, trackId, start: S}` 2. `clip_speed {clipId, speed: v}` (before trimming) 3. `clip_trim edge start delta = in / v` 4. `clip_trim edge end delta = -((L - in) / v - D)` 5. `clips_move {moves:[{clipId, start: S, trackId}]}`.
Use the **container** duration `L` (`ffprobe -show_entries format=duration`), not the video stream's: the audio stream can be longer, every trim delta is then 0.0127 s off, a clip ends longer than asked and a frame at the cut lands black. Put every start and duration on the frame grid (`round(t*30)/30`: 3.3667, 6.3667) and check the export with `blackdetect`.

**Speed 1x clip, listener too long vs speaker**: make the listener's pieces add up to exactly the speaker's frame count (`diff` goes to the last piece and its speed is recomputed), see `examples/split_screen_gen.py`.

## 6. A person who must look alive (the listener / reaction footage)

Rules this user set: looking at the camera or at the other person (best at whoever speaks), never reading a script, leaning, touching face or hair, mouthing words; no visible jump at a cut; no obvious repeat; slow motion only where still, never below 0.5x unless nothing else works.

**Pipeline** (full detail and numbers: `learnings.md` 2026-11-07; code: `replicate-style-in-concat/examples/listener_search.py`):
1. **Count first.** Unvoiced seconds of each raw (from `vad.json`), how many survive the filters below, against seconds needed per person. Capacity = clean seconds / lowest allowed speed. Report it with options (repeat with soft cuts + boomerang was chosen).
2. `face_gaze.py RAW --crop X:Y:W:H --out gaze.json --contact contact.jpg` (`uv run --python 3.12`, MediaPipe 0.10.14): yaw, pitch (above 0.40 = reading), eye opening `eo` (under 0.26 = blink/eyes down), mouth opening `mo`, position, every 0.1 s.
3. Mask: not within 0.3 s of voice, pitch under 0.40, eyes open, mouth range under 0.25 over 0.7 s, head within 0.05 of its usual height, no fast motion.
4. **Look at a cropped face every 0.5 s of every candidate** (`frames_grid.py --crop`, 60 per sheet) and write down the good seconds. The numbers alone let glances down, tilts, hair-touching through; a 0.5 s sample still missed 0.3 s glances, so when the user names a second re-inspect at 0.1 s. Close blink gaps of up to 0.4 s only where just the eye test fails; never across frames you removed.
5. **Slow motion only where still**: mean head displacement per 0.1 s (+ max): under 0.0045/0.015 allows 0.4x; 0.008/0.025 0.5x; 0.012/0.04 0.6x; 0.016/0.055 0.75x; 0.022/0.07 0.9x; else 1x.
6. **Cuts**: `frame_descriptors.py RAW --crop ... --out desc.npy` then `--diff desc.npy T1 T2` = mean absolute difference of two grayscale thumbnails of the person: calm frames 0.1 s apart score 1-3, 1 s apart 8-12; cuts the user accepted 4.8-10.6, "jumps" 12 and above. Cap internal cuts at 9; cut where the head is still.
7. **Search** (`examples/listener_search.py`): beam per turn over candidate pieces on a 0.1 s grid, costs as in its docstring, **locked turns** copied from the previous plan, same source never in adjacent turns. Turn order matters; the first automatic plan had a cut every second and was called horrible: prefer 1-2 long pieces per turn.
8. After every plan: strips of each piece (`frames_grid.py`, a tile per second), and a `blackdetect` + `silences` + cuts check on the export.
9. User feedback of this kind ("reading at 1:04", "hand to the face at the end", "leans forward and back at 15 s") -> add that second range to `FLAG` and re-run only the turns they named.

## 7. Picture, layout and text

- **Split screen** (verified): raw A on `T1`, raw B on `T2` (drawn above), mask on B `{"shape":"linear","x":0,"y":0,"rotation":90,"invert":true,"feather":0.14}` via `clip_mask` (check `--list-tools`: newer Concat has `clip_masks` with a stack of masks). Which half it keeps depends on `rotation` and `invert`: render a `preview_frame` and look. Scaling both layers (`clip_transform scale 1.12`) keeps the seam in the middle and crops feet/floor.
- **Locked-off camera?** SIFT+RANSAC on the static top band of one frame of each raw: scale 1.0009 and 2 px shift = no alignment needed. Check once.
- **Lanes**: higher number draws above. Footage `T1`, other picture layers `T2`; mint all lanes first (`track_add`; `bottom: true` for sound lanes; ids come back in `createdId`, lowercase, e.g. `t4`); pass `trackId` explicitly to `title_add`; `above: true` takes the first free lane above everything over its span **including lanes you minted for icons** (images added afterwards were pushed to other times).
- **Titles**: `title_add {start, duration, style: {content, fontFamily, fontSize (fraction of frame height; 0.04 title, 0.034 captions, 0.019 plates), fontWeight, color, shadow, lineHeight, align, background (#rrggbbaa), backgroundPaddingX/Y/Radius, strokeWidth/strokeColor}, offsetY}`; sideways with `clip_transform {offsetX}` (the tool only takes offsetY); `\n` makes two lines; `tracking` 0.06 breaks chips across three lines (leave 0).
- **Captions**: `captions_add {captions:[{start,end,text}], offsetY, style}` one word per entry, `shadow: true`, no background, centred where they cover nobody (offsetY +0.07 on a split seam; lower third +0.28 on a talking head). Text over a bright wall: espresso `#2B221E`; over dark: white.
- **Typed text**: Concat has no typewriter animation: `takes_to_plan.py` makes one clip per letter (every 0.06 s). **Rise and fade-in cards** are keyframes: `keyframe_set property opacity 0->1` and `offsetY oy+0.10 -> oy` over 0.22 s (`at` is a fraction of the clip 0..1), hard cut out. A 7 % punch-in is `scale` keyframes.
- **Image cards**: bottom and centred (offsetY +0.22 to +0.30, scale 0.30-0.62 by aspect), never over a face or a caption; transparent PNG for objects; `clip_transform` scale of a PNG padded to a square is its long side as a fraction of the width (0.115 for an emoji).
- **Emoji**: Apple Color Emoji 256 px, square-padded; sequences with zero-width joiners (woman in lotus position with skin tone) do not render in PIL without raqm: draw them with CoreText (a swift `NSAttributedString` in "Apple Color Emoji") then pad. The user ended up removing floating emojis from reels; ask.
- **Contrast per zone before choosing text colour**: linearise the frame, compute WCAG contrast of the colour against the pixels of each text zone (title, plates, caption rows) at several exposures (see the `legi.py` idea in learnings: white text failed 3:1 on 91 % of a title zone over a bright ceiling; -0.7 EV brought it to 42 %). A dark outline (`strokeWidth` 0.0025) helps on white text; 0.004 made a serif title blobby; the user rejected black outlines on the title.
- **Fonts**: Concat renders bundled fonts (`src/crates/concat-text/fonts`) and installed system fonts by family name (they do not travel with the project). A **variable** font ignores weights: make static instances (`uv run --with fonttools python -m fontTools.varLib.instancer F.ttf wght=600 wdth=100 --update-name-table -o F-600.ttf`), install them in `~/Library/Fonts`, remove the variable file, and move the title render cache (`<app data>/titles/*`) to the Trash: it keeps showing the old look. Open Sans static files are in `replicate-style-in-concat/fonts/`. A paid font (True Fate): never download from "free font" pages; find the closest installed one (Bodoni 72 was) and say so.
- **Zoom and crop**: scale 1.1-1.16 hides feet and clutter; rotation of 1 degree if the horizon is off.
- **Placeholders** for footage not supplied: `make_placeholders.py` labelled cards on `T2` with the right time slot; give neighbours different colours.
- **Seam colour**: §9.

## 8. Voice and sound

**Always, on every clip that carries a voice, without being asked**: `concat.denoise` strength 100, `concat.enhance-voice` amount 100, `concat.loudness` target -16, **in that order** (loudness before enhance, or a second denoise at default strength, sounds different; the user's ears were fine with this chain and the pause-to-voice gap narrowed from 43 to 26 dB, "la voz perfecta"). Listener clips are muted. Read `concat.json` back and check each voice clip has the three, especially after the user has worked in the window (they once ended up with three different chains).

**Clean the raw first** (ffmpeg on a copy; picture copied):
`ffmpeg -i RAW -map 0:v:0 -map 0:a:0 -c:v copy -af "highpass=f=90,highpass=f=90,afftdn=nr=20" RAW_clean.MOV` (use `highpass=f=100` x2 and `nr=18:nf=-45:tn=1` for a low rumble; `140` for a motor hum). Find the noise first: rumble nearly as loud as the voice, or tonal peaks (`audio_peek.py tones`: 68 Hz + harmonics 136, 204, 272 was a motor; a 100 Hz high-pass leaves 136). Concat has no high-pass/EQ; its denoise/enhance remove hiss above 2 kHz (about 20 dB) but a rumble only 3-4 dB.

**Echo / "far away" voice**: WPE dereverberation (`nara_wpe`, single channel, taps 10, delay 3, 3 iterations, STFT 1536/384 at 48 kHz, via `uv run --with nara_wpe --with numpy --with scipy`), then presence EQ (+3 dB at 3 kHz, +2 dB at 6.5 kHz). Enhance Voice dulls the highs by 4-5 dB against the mids and does nothing for room echo. **Concat's audio filters are level-dependent**: feed Concat a file at the original level (rescale WPE's output to the input's RMS) or its denoiser stops gating noise (pause 44 dB under the voice became 23 dB). Order: ffmpeg high-pass + afftdn, then WPE at original level, then EQ, then Concat's chain. Stacking more is not better (denoise 60 + enhance 80 measured worse than enhance 40). The user could not tell WPE strengths apart: use the gentlest.

**Sound effects**: only the eight approved (`replicate-style-in-concat/sounds/README.md` for each one's use and level), very low under the voice (dB: drop 002 -9.5, confirmation 001 -15, confirmation 002 -17; soft swish 0.2 on card entrances). Synthesized pops were rejected twice; dry pops "molestan". Concat's own sound library is empty (manifest 404). To let the user audition: `add_to_library.py` writes sounds into their Audio > Mine shelf (shown after the project is reopened). Place with `clip_add` on an audio lane at `event + offset` (negative if the sound leads), `clip_update {volume, fadeIn, fadeOut}`. `track_add {bottom:true}` for audio lanes; keep effects on lanes of their own, spread greedily so none overlap.

**Music**: none by default. If asked: a CC0 ambient piece at gain 0.10 (about 20 dB under the voice), 1.5 s fade in, 2.5 s fade out, duck with `keyframe_set property volume`.

**Check the mix on the export** (§2): -16 LUFS, peak under -1, pauses, last 80 ms of each cut. You cannot hear: say so, and offer numbered audio samples (§11).

## 9. Colour

- **Direction of taste**: neutral to cool, slightly dark; never warmer or brighter than the raw without asking. An exact copy of a reference grade was "very red and bright"; the user then added exposure -0.5 and temperature 11000 K (cool end) on top, ending cooler than the raw (red/blue 1.49 -> 1.18; raw 1.26) and 22 % darker.
- **Match two shots of one room** (split screen seam, cuts between takes): render `preview_frame` PNGs at several `concat.white-balance` temperatures (6500, 7500, 8500, 9500) on the warmer layer, average the wall in a window left and right of the seam (x 0.40-0.47 and 0.53-0.60 of the width; top band and middle band), print `R-L` per channel and pick the temperature where it is closest to 0 (7300 K + `concat.exposure` +0.12 here). Calibrate in the **same MCP session** that builds the project and `project_save` first: a new session opening an unsaved project sees it empty (black previews).
- **Offer examples**: the same instant at four exposures (A -1.0, B -0.7, C -0.4, D 0 EV) in one image with `frames_grid.py --images` and let the user choose; record the choice in `house-style.md`.
- 6500 K is as shot; lower is warmer.

## 10. Driving Concat

- `mcp_run.py --bin <concat> steps.json`: JSON list of `{tool, args, as}`; `"$name.createdId"` passes ids; **names must not contain dots** (`$mx1_5.05.createdId` reads as name plus path); `export_start` returns `job` not `createdId` (`$exp.job`); `timeline_read` needs `project_open` first in a fresh session; `project_create` takes `location` + `name` (no `path`) and refuses an existing project folder (new `_vN` per version); `project_set_video` changes size/fps; writes only under home (previews, exports, projects); reads anywhere.
- One generator = one steps file = reproducible; the 77 s split-screen reel was about 300-400 steps with 0 failures over 17 versions. Keep the generator's inputs as JSON plan files so a fix is a data change.
- **Review render**: `export_start {output, width: 540, height: 960, crf: 34}` about 1 minute, 3 MB. Final: 1080x1920 about 5 minutes, 35-40 MB. Foreground calls die at 10 minutes: `nohup ... &`, poll the log for `"state":"done"`.
- **Project open in the window** locks the folder (`concat.lock`): the MCP cannot open it; close the window or use another folder. Open for the user with `concat --project <folder>` in the background (bin thumbnails are generated on first open, harmless "Error loading image ... .thumb.jpg" lines).
- `edit_apply {command:{op:"batch", commands:[...]}}` = many ops as one undo step.
- After the user edits in the window, **read their saved `concat.json`** (grade, volumes, times, filter order) instead of asking for numbers.
- A font installed on the Mac but not bundled renders by name in preview and export, but not on another machine.

## 11. Working with the user

- Spanish, short, on a phone. Send every video/audio with `SendUserFile` (30 MB limit: make a lighter copy; for audio use m4a).
- **Offer choices instead of guessing taste**: numbered audio samples (a voice says the number, then the sound twice; same loudness; macOS `say` for the number, ffmpeg to join), A-D picture sheets, 3-5 voice-chain variants of the same phrase at the same volume. Apply the choice everywhere and record it.
- **Feedback arrives as screenshots with a second each**: look at 0.1 s steps around it, fix only that. Ask which parts are approved; keep them locked.
- Judge the voice by their ear: "voz perfecta" came from a chain the numbers rated worse; "sigue rara" came after measurements said it was fine. Report measurements as measurements.
- Ask before: downloading (say source, file, size), installing, uploading, deleting, registering MCP servers, changing sharing. Use the Trash. Free/CC0 only.
- When the user says an earlier version is the good one, clean up the others (Trash) but keep assets and cleaned audio.
- The proposal canvas is private; frames of a real person are on it; never change its sharing.

## 12. Learning editing instructions from a class video

1. `fetch-course-lesson-video` (their Chrome, yt-dlp on the real m3u8/mp4 found in the page), ask before downloading.
2. Transcribe the whole class (`ffmpeg -vn -ac 1 -ar 16000`, `whisper-cli` with `--prompt` of the topic; long files drift, use it for content not for timing) and take frames every 10-20 s (`frames_grid.py --times 0:1320:20`) to see the slides/screen demos.
3. Write the instructions as a checklist (structure, hooks, pacing, text rules, sound rules, length), each tagged taught / demonstrated / inferred; ask the user which rules are theirs before putting them in `house-style.md`.

## 13. What Concat cannot do (say it, then use the workaround)

| Cannot | Workaround |
| --- | --- |
| Play backwards | `make_reversed.py` file, imported as media |
| Animate text (typewriter, pop) | one clip per letter; rise+fade with keyframes on opacity/offsetY; scale keyframes |
| Reach its own sound library | user's palette in `sounds/`; `add_to_library.py` |
| Transcribe, detect beats/scenes, analyse audio via MCP | whisper-cli, `analyze.py`, `audio_peek.py` outside it |
| High-pass / EQ | ffmpeg on a copy of the raw before import |
| Carry a system font with the project | ask; the project falls back on another machine |
| Relative media paths | keep `assets/` and cleaned audio where they are; templates are the exception |
| Open a project the window has open | another folder or close the window |
| Judge how it sounds | numbers + numbered audio samples for the user's ears |
| True Fate / CapCut fonts and sounds | closest installed font; approved CC0 palette |

---
name: replicate-style-in-concat
description: Rebuild an edit in Concat through its MCP server - lay the user's raw footage on the timeline as the reference's shots (source in/out, speed), add transitions, titles and captions, place sound effects and music with timing and level, then preview, export and score the result against the reference. Use this whenever the user wants Claude to edit a video in Concat, copy a reference video's editing onto unedited footage, apply a saved style profile, place sound effects on a timeline, or test how far Concat can be driven by an agent - even if they only say "edit this like that" or "make it look like the reference". Also covers copying a finished edit that exists only as a screen recording, the user's approved sound palette and how to give them sounds to audition, and the checks that catch a black frame at a cut. Contains verified recipes for the MCP tools and a running list of what Concat can and cannot do.
---

# Replicating an edit in Concat

> **Version: written for Concat 0.2.10.** Check `concat --version` first; if the binary is older, rebuild it (`../video-edit-playbook/references/concat-version.md` has the commands, what changed since 0.2.8, and the fix for the masks of old projects).


**The standard step-by-step process (with gates and every trick) is `video-edit-playbook`: start there.** Order of work: `propose-edit-plan` (canvas the user approves) -> `analyze-reference-video` -> `distill-editing-style` -> this skill. Companion skills: `analyze-reference-video` (turns videos into evidence), `distill-editing-style` (turns evidence into a profile). **Read `references/learnings.md` before starting and add to it after every session** - it holds what has been verified against the real app and is the main way this skill improves.

## Connect to Concat

Concat has a built-in MCP server (`concat --mcp`, see `docs/MCP.md`). Two ways to drive it:

1. **Registered MCP tools** (`project_create`, `clip_add`, ...) if the client has the server configured. Registering changes the user's Claude config, so ask first. Command: `claude mcp add concat -- <repo>/src/target/debug/concat --mcp` (debug build from `cargo run -p concat` / `cargo build -p concat`; an installed app lives at `/Applications/Concat.app/Contents/MacOS/concat`).
2. **`scripts/mcp_run.py`**, no registration needed: it starts `concat --mcp headless` and runs a JSON list of tool calls in one session, passing ids between steps (`"$name.createdId"`). Use this for deterministic runs and to replay a recipe.
   ```bash
   python3 -I <repo>/.claude/skills/replicate-style-in-concat/scripts/mcp_run.py \
     --bin <repo>/src/target/debug/concat steps.json
   python3 -I .../mcp_run.py --bin ... --list-tools        # tool names + descriptions
   python3 -I .../mcp_run.py --bin ... --tools tools.json  # full JSON schemas
   ```
   A session is one process: edits live in memory until `project_save`, so end every steps file with `project_save`.

Constraints that bite:
- **Files are written only under the user's home folder** (projects, exports, preview PNGs). Reading media from anywhere works. Use `~/concat-analysis/<job>/`.
- **Headless cannot open a project that the Concat window has open** (lock). Close it in the window or use another project folder.
- `project_create` needs the `location` folder to exist; the project path used by later calls is `location/name`. Defaults to 1920x1080 at 30 fps; `project_set_video` changes it.
- Tools return the whole project summary every time, which is noisy; `mcp_run.py` compacts it.

## Lane convention (verified)

New projects have lanes `T1..T4`. **A higher lane number is drawn above a lower one**, even though `timeline_read` lists lanes "top to bottom". A title on `T1` is hidden behind video on `T2`. Convention to use: footage on `T1`, other picture layers (B-roll, placeholders) on `T2`, and **pass `above: true` to `title_add`**: it puts the title on the first free lane above everything occupied over its span (minting a lane if needed). `captions_add` does this by itself. Without `above`, `title_add` takes the first free lane from the bottom, which can be *behind* the footage. After adding, check the `track` in the result and confirm with `preview_frame`. Add lanes with `track_add` (`bottom: true` for under everything).

## Recipes (all verified in the app)

**Import** - `media_import {path: <project>, file: <absolute path>}` returns `createdId` (`m1`). Importing a path twice changes nothing.

**Put a stretch of the raw footage on the timeline** (source in/out) - `clip_add` always places the *whole* file, so trim it. For a shot that should appear at timeline `S` for `D` seconds using raw `[in, in+D]`:
1. `clip_add {mediaId, trackId: "T1", start: S}` -> clip id
2. `clip_trim {clipId, edge: "start", delta: in}` (the picture does not slide: the clip now starts at `S+in` and its `sourceStart` is `in`)
3. `clip_trim {clipId, edge: "end", delta: -(media_len - in - D)}`
4. `clips_move {moves: [{clipId, start: S, trackId: "T1"}]}`

`timeline_read` then shows `start: S`, `duration: D`, `sourceStart: in`. Add shots left to right so a newly added full-length clip never lands on a neighbour. Step 1 can collide with an existing clip on the lane; add at `S` only when the lane is free from `S` onward, otherwise use a scratch lane and move.

**Speed** - `clip_speed {clipId, speed}` keeps the same stretch of source, so the clip's length changes (2x = half as long). Set speed first, then trim by the *timeline* length you want.

**Transitions** - `clip_update {clipId, patch: {"transitionIn": {"id": "concat.dissolve", "duration": 0.3}}}` on the clip that comes *in*. List ids with `effects_list {kind: "transition"}`.

**Titles** - `title_add {path, start, duration, style: {content, fontSize, fontWeight, color, ...}, offsetY?, above?}`. `fontSize` is a fraction of frame height (0.09 default). Fonts the machine lacks fall back silently. `captions_add {captions: [...], style, offsetY}` places many in one undoable step.

**Sound effects** - `media_import` the audio file, `clip_add` it on an audio lane at `start = event_time + offset` (negative for sounds that lead the cut: a whoosh whose peak is 0.12 s before the cut starts about 0.6 s before it if the swell takes ~0.6 s to peak). Then `clip_update {patch: {"volume": 0.6, "fadeIn": 0.02, "fadeOut": 0.1}}`. Volume is a gain (1 = unchanged). Give effects their own lane(s): `track_add {bottom: true}` returns the lane id in `createdId`.
- Concat's own sound library is **not published yet** (manifest 404, re-check it), so effects come from the user's folder or from open sets. **Use only the user's approved palette** in `references/sfx-sources.md` (eight sounds, with the levels they settled on) unless they ask for others; synthesized stand-ins were rejected. That file also lists the CC0 sets, download commands and placement rules; `scripts/make_sfx_pack.py` turns them into a named palette, and `scripts/add_to_library.py` puts sounds in the user's own library (Audio page, Mine shelf) so they can audition and choose. Ask before downloading. `scripts/make_sfx.py` synthesizes crude stand-ins only when there is nothing else; say so.
- `build_steps.py --sfx sfx.json` lays a list of `{file, start, volume, lane}` on lanes of their own.
- Music: place on a lane, then duck under speech with `keyframe_set {clipId, property: "volume", at: <fraction of clip 0..1>, value}`.

**Layers and looks** - `effect_layer_add {effectId, start, duration}` puts an effect over everything beneath; strength is the layer's opacity via `clip_update`. Per-clip: `clip_update patch.videoEffects / filters` = `[{id, params}]`. Audio clean-up (denoise, loudness, radio, ...) are `kind: "audio"` packages used the same way through `filters`. Check `effects_list` for each id and param range.

**Check, save, export**
- `preview_frame {path, time, output: <png under home>, width, height}` renders the real composite (titles and effects included). Look at it with Read.
- `project_save {path}` then `export_start {path, output: <mp4 under home>, width?, height?, crf?}` -> `job`, then `export_wait {job, timeoutSeconds}`.
- **Review renders small, final render large.** Every iteration the user will look at: `width 540, height 960, crf 34` (about 1 minute, 3 MB, fits a phone upload). Full quality (1080x1920, 5 minutes, 35-40 MB) only after the user approves. A foreground call is limited to 10 minutes: run long sessions with `nohup ... &` and poll the log for `"state":"done"`.
- **Reverse playback and per-clip speed:** Concat cannot play backwards; pre-render the reversed piece with ffmpeg (`reverse`) and import it. With `clip_speed v`, trim the start by `in / v`. See `references/learnings.md` (2026-11-07).
- `edit_apply {command: {"op": "batch", "commands": [...]}}` runs many ops atomically as one undo step; ops include `addClip, splitClips, trimClip, moveClips, setClipSpeed, updateClip, setClipKey, addTextClip, detachAudio, freezeFrame, ...` (see `references/learnings.md` for any used so far).

## Workflow for "copy this edit onto my raw footage"

1. `analyze-reference-video` on the edited and raw videos, then the right aligner (`align.py` for varied footage, `align_audio.py` for a talking head or when the voice survives). `distill-editing-style` for the profile.
2. Write `steps.json`. For a voice-led reel `scripts/build_steps.py` does it from `audio_alignment.json`: one raw clip per aligned segment on `T1` (recipe above), placeholder images on `T2`, `captions_add`, `title_add above`, save, previews, export. Inputs it takes: `captions.json` (`{offsetY, style, captions: [{start,end,text}]}`), `titles.json`, `placeholders.json`, `sfx.json`; with `--remap` and a `tighten_segments.py` output as `--alignment`, every time in those files (written against the reference) moves with the tightened cuts.
2b. **Tighten the cuts** (`analyze-reference-video/scripts/tighten_segments.py`) before building: a reference's jump cuts often sit inside a pause, so clips open on a person who is looking away or has not started speaking. It trims long silence before the voice, gives the first syllable a 0.08 s lead-in, and shortens long tails. Compare a strip of segment-start frames before and after (verified: before, 2 of 7 sampled starts looked away; after, all 7 looked at the camera).
3. **Footage that the user has not supplied** (B-roll, screenshots, icons): do not invent it and do not reuse pieces of the reference, whose pictures carry its burned-in captions. `scripts/make_placeholders.py` renders a labelled image per slot (kind, what goes there, the time slot) and `build_steps.py` lays them on `T2` at the right times, so the user can replace each clip in the window and the timing stays.
4. Run `python3 -I scripts/mcp_run.py --bin <concat> steps.json`, open the preview frames with Read, fix, re-run (use a new project name or delete the folder; `project_create` refuses an existing project). Close any process that has the project open first (lock).
5. Export, run `analyze.py all` on the export and `compare.py` against the reference.
6. **Open the project for the user**: `<concat> --project <project folder>` (the same binary; in the desktop app session run it in the background). The MCP run must have ended, because the lock refuses a project open elsewhere. The app creates the bin thumbnails itself, so it logs harmless "Error loading image ... .thumb.jpg" lines on first open.
7. Report plainly: what matches, what is approximate, what Concat could not do, and which captions or words were guesses. Then update `references/learnings.md` and, if a recipe changed, this file.

## Workflow for "raw takes only, no edited reference"

1. `analyze-reference-video/scripts/phrases.py` -> exact phrase times and text; choose one take per line.
2. Write `takes.json` (phrases with their caption chunks) and `overlays.json` (what appears when each line is said: typed step titles, accent words, label chips, placeholder cards, icons, punch-ins, effects), anchoring everything to **words that are said**, not to timestamps. See the docstring of `scripts/takes_to_plan.py`. It lays the cuts (`lead` 0.12 s before the voice, `tail` 0.15 s after, pauses cut out), spreads each phrase's captions over its voiced time, resolves the anchors, and writes `alignment.json`, `captions.json`, `titles.json`, `placeholders*.json`, `icons.json`, `punches.json`, `sfx.json` and `plan.md`.
3. `make_placeholders.py` (labelled cards for footage not supplied), `make_icons.py` (check, cross, bookmark, comment as transparent PNGs), then `build_steps.py` with the plan files plus `--voice-target -16` (each voice clip gets `concat.loudness`), `--music FILE --music-duration N --music-volume 0.1` (trimmed, faded in and out, about 20 dB under the voice) and `--punches`. Run with `mcp_run.py`, preview a few frames, fix, export.
4. What the builder does that you would otherwise do by hand: typed titles as clips that grow one letter every 0.06 s, placeholders that rise 10 % and fade in over 0.22 s (opacity and offsetY keyframes), a 7 % zoom on emphasised words (scale keyframes on the clip that holds the word), a `transitionIn` on a card (`"transition": {"id": "concat.dissolve", "duration": 0.4}`), effects greedily spread over audio lanes so none overlap.
5. Measured on the first run (5-minute raw, 21 takes chosen): 64.5 s, 25 clips, 442 steps, 0 failures; exported loudness -16.1 LUFS with the music in, peak -0.6 dBFS.

## Workflow for "two raw takes of one person, shown side by side" (split screen)

1. Check the camera did not move (SIFT/RANSAC on the static top band of one frame of each raw), then lay raw A on `T1`, raw B on `T2` with a linear mask (`clip_masks` in 0.2.10; `clip_mask` in 0.2.8) on the vertical centre line (feather about 0.14) and cool the warmer layer until the wall matches at the seam; render previews and look.
2. Per raw: `phrases.py` for the spoken lines, choose the last good take of each line, transcribe each chosen piece alone with `whisper-cli --prompt`, align your own corrected caption text to its timings (`difflib`), end every cut after the word dies away (check the level in the last 80 ms of each cut in the export), splice a clean repeat when a take stumbles.
3. **Plan the silent half before promising anything:** count the clean listening seconds against the seconds needed per person (see `references/learnings.md`, 2026-11-07, "The person who listens") with `analyze-reference-video/scripts/face_gaze.py` and `frame_descriptors.py`, look at a frame every 0.5 s of the candidates, slow only still pieces, join with boomerangs and cuts under a difference of about 9, lock the turns the user approves. If the rules cannot all be met, say it with the numbers and offer two or three sacrifices.
4. Overlays (title, plates, one-word captions, image cards on their own lanes), the approved soft swish at each card, no music, voice chain, a small review render, then the full render after approval and, if asked, delivery through `.claude/skills/upload-to-drive-via-browser`. The numbers of the approved layout are in `propose-edit-plan/references/house-style.md`.

## Workflow for "copy this finished edit" when you only have a screen recording of it

1. Crop the preview area out of the recording (9:16 inside a taller frame) and find the cuts (frame difference on the person region) and every overlay's on/off frame (white pixels in a pill's box, or a frame diff on its region). `analyze-reference-video/scripts/align_audio.py` gives raw segment offsets on the *audio* clock.
2. `register_frames.py` on 2 or 3 matching raw/edit frames: scale, rotation, offsetX/Y for `clip_transform` and the colour gains. `picture_sync.py`: the picture-based correction to the raw in-points (the recording's audio lags by about 0.2 s).
3. Build with a generator (copy the idea of the one in `learnings.md`: one lane per overlay kind, explicit `trackId`, frame-grid times, container duration for `clip_trim`), render `preview_frame` at a few times and compare side by side with the reference crops; adjust sizes by measured widths (a font that is not bundled needs a different size to match the width).
4. Export, run `blackdetect` and read `concat.json` back; send the video, then apply the user's taste (they usually cool and darken the grade and lower the sounds) and write the final numbers into `house-style.md`.
5. After the user edits in the window, read their saved `concat.json` for what changed (grade, volumes, times, filter order) instead of asking them for numbers.

## Always on every voice clip

Enable **noise cancellation and voice enhancement** on every clip that carries a voice, without waiting to be asked: `clip_update {clipId, patch: {"filters": [{"id": "concat.denoise", "params": {"strength": 100}}, {"id": "concat.enhance-voice", "params": {"amount": 100}}, {"id": "concat.loudness", "params": {"target": -16}}]}}`, in that order (loudness before enhance changes the sound). `build_steps.py` does it by default; a generator you write yourself must do it too. Before exporting, read `concat.json` back and check each voice clip lists the three filters; the user reminded us twice (once after hearing background noise in an export that already had them: the filters were present, and the noise was probably room echo or the maximum enhancement, so a reminder is a reason to re-check the saved project and the raw's noise floor, not only to re-apply).

## Scripts and examples in this skill

- `scripts/mcp_run.py` runs a steps file (`{"tool":"sleep","args":{"seconds":60}}` waits; `--mode window` needs the user to turn on Settings > Automation); `scripts/migrate_v1_masks.py` re-masks a project saved by 0.2.8; `build_steps.py` builds a voice-led reel from an alignment (0.2.10: `motion` and `words` entries instead of keyframes and extra clips); `takes_to_plan.py` plans from said words; `make_placeholders.py`, `make_icons.py`, `make_sfx_pack.py`, `add_to_library.py` (put sounds in the user's Audio library).
- `scripts/make_reversed.py` pre-renders a reversed or boomerang piece (Concat cannot play backwards): the trick that makes a short calm piece last twice as long.
- `examples/split_screen_gen.py` is the real generator of the split-screen reel with the client's texts replaced by placeholders (source in/out with speed and reversed pieces, masked top layer, white balance per layer, voice chain on speakers only, plates, rise-and-fade cards, one-word captions, soft swishes, previews, save, export). **Copy and adapt it** for any layered edit; its docstring lists the plan files it reads.
- `examples/listener_search.py` is the beam search for listening footage (see `video-edit-playbook/references/hacks.md` section 6); also reference code to adapt, thresholds were tuned to one person.
- Recipes here were first verified on 0.2.8 and are now written for 0.2.10: masks are `clip_masks` (a list), titles can animate with `clip_update patch.motion`, projects saved by 0.2.8 lose their masks until `scripts/migrate_v1_masks.py` re-applies them. All in `../video-edit-playbook/references/concat-version.md`.

## Honest limits to state to the user

- Concat's MCP has no audio analysis, no beat or scene detection, no sound-library access and no transcription; the analysis happens outside it.
- Visual effects have to be matched by name from `effects_list`; custom looks may only be approximated.
- Claude cannot hear the result: sound is checked with the loudness/event analysis and spectrograms, not by listening. Ask the user to listen for anything the scores cannot judge. They have also been right where the numbers said otherwise (voice chains, sound levels).
- Pick settings the user has already approved (`house-style.md`, `sfx-sources.md`) before inventing new ones.

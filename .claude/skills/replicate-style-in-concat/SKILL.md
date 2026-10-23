---
name: replicate-style-in-concat
description: Rebuild an edit in Concat through its MCP server - lay the user's raw footage on the timeline as the reference's shots (source in/out, speed), add transitions, titles and captions, place sound effects and music with timing and level, then preview, export and score the result against the reference. Use this whenever the user wants Claude to edit a video in Concat, copy a reference video's editing onto unedited footage, apply a saved style profile, place sound effects on a timeline, or test how far Concat can be driven by an agent - even if they only say "edit this like that" or "make it look like the reference". Contains verified recipes for the MCP tools and a running list of what Concat can and cannot do.
---

# Replicating an edit in Concat

Companion skills: `analyze-reference-video` (turns videos into evidence), `distill-editing-style` (turns evidence into a profile). **Read `references/learnings.md` before starting and add to it after every session** - it holds what has been verified against the real app and is the main way this skill improves.

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

New projects have lanes `T1..T4`. **A higher lane number is drawn above a lower one**, even though `timeline_read` lists lanes "top to bottom". A title on `T1` is hidden behind video on `T2`. Convention to use: footage on `T1`, titles on `T2` and up, sound effects and music on the lanes above those (audio does not need to be last). After `title_add`, check the `track` in the result and move it with `clips_move` if it is below the footage, then confirm with `preview_frame`. Add lanes with `track_add` (`bottom: true` for under everything).

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

**Sound effects** - `media_import` the audio file, `clip_add` it on an audio lane at `start = event_time + offset` (offset is negative for sounds that lead the cut, e.g. a whoosh whose peak is 0.12 s before the cut starts about 0.6 s before it, since the swell takes ~0.6 s to peak). Then `clip_update {patch: {"volume": 0.6, "fadeIn": 0.02, "fadeOut": 0.1}}`. Volume is a gain (1 = unchanged).
- Concat's own sound library is **not published yet** (its manifest URL returns 404), so effects come from the user's folder. Ask for it. If none exist, `python3 -I scripts/make_sfx.py ~/concat-analysis/<job>/sfx` synthesizes whooshes, an impact, a riser, clicks and a ding as stand-ins, and say that they are synthetic.
- Music: place on a lane, then duck under speech with `keyframe_set {clipId, property: "volume", at: <fraction of clip 0..1>, value}`.

**Layers and looks** - `effect_layer_add {effectId, start, duration}` puts an effect over everything beneath; strength is the layer's opacity via `clip_update`. Per-clip: `clip_update patch.videoEffects / filters` = `[{id, params}]`. Audio clean-up (denoise, loudness, radio, ...) are `kind: "audio"` packages used the same way through `filters`. Check `effects_list` for each id and param range.

**Check, save, export**
- `preview_frame {path, time, output: <png under home>, width, height}` renders the real composite (titles and effects included). Look at it with Read.
- `project_save {path}` then `export_start {path, output: <mp4 under home>, width?, height?, crf?}` -> `job`, then `export_wait {job, timeoutSeconds}`.
- `edit_apply {command: {"op": "batch", "commands": [...]}}` runs many ops atomically as one undo step; ops include `addClip, splitClips, trimClip, moveClips, setClipSpeed, updateClip, setClipKey, addTextClip, detachAudio, freezeFrame, ...` (see `references/learnings.md` for any used so far).

## Workflow for "copy this edit onto my raw footage"

1. `analyze-reference-video` on the edited and raw videos, then `align.py` for the shot map. `distill-editing-style` for the profile.
2. Write `steps.json`: project, imports, shots (recipe above, from `alignment.json`), transitions, titles, SFX, music, save, preview of 3-5 key moments, export.
3. Run it, open the preview frames, fix, re-run (recreate the project folder or use a new name; `project_create` refuses an existing project).
4. Export, run `analyze.py all` on the export and `compare.py` against the reference.
5. Report plainly: what matches, what is approximate, what Concat could not do. Then update `references/learnings.md` and, if a recipe changed, this file.

## Honest limits to state to the user

- Concat's MCP has no audio analysis, no beat or scene detection, no sound-library access and no transcription; the analysis happens outside it.
- Visual effects have to be matched by name from `effects_list`; custom looks may only be approximated.
- Claude cannot hear the result: sound is checked with the loudness/event analysis and spectrograms, not by listening. Ask the user to listen for anything the scores cannot judge.

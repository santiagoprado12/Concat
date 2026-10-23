# Learnings: driving Concat from an agent

Newest first. Each entry says how it was found. Verified = run against the real app (Concat 0.2.8, macOS, debug build, headless MCP).

## 2026-10-23 (third): a 5-minute raw take of one person, no reference video

- **Raw shape:** one fixed shot, 301.9 s, 44 spoken takes for about 21 lines (each line 2 to 5 times), a CapCut end card in the last 2 s. Finished edit: 64.5 s from 21 chosen takes, 25 clips.
- **Whisper word timestamps drift on long files** (several seconds, many words on one time). Energy-based phrase detection plus a per-phrase transcript fixed it: `phrases.py`.
- **The old per-take loop is replaced by `takes_to_plan.py`**: describe the edit by what is said and let anchors place everything; 0 manual timestamps.
- **Verified in the app:** keyframes on `scale`, `opacity` and `offsetY` work through `keyframe_set`; `clip_update` with `filters: [{"id": "concat.loudness", "params": {"target": -16}}]` normalises a clip (export measured -16.1 LUFS); `clip_update` with `fadeIn`/`fadeOut`/`volume` shapes the music; `clip_transform` places and scales an overlay icon; `title_add` with `fontFamily` "Montserrat" and "DM Serif Display" renders in those fonts; a title `background` with `backgroundPaddingX/Y/Radius` makes a label chip.
- **Gotcha:** `tracking` is not a small em fraction: 0.06 spread the letters of a chip across three lines. Leave it at 0 (or well under 0.02).
- **Gotcha:** two title clips on the same screen position for 0.6 s looked like one garbled title. The typed title of the next line must start after the previous one ends; shorten `dur`.
- **Gotcha:** an overlay icon placed at the face height (`offsetY` -0.10) covers the speaker; keep icons in the top band (-0.28 to -0.30) or just above the caption (+0.17).
- **Music:** a 43 MB CC0 ambient piece at gain 0.10; the export's LRA fell to 2 LU and the integrated loudness stayed -16.1. See `sfx-sources.md`.

## 2026-10-23 (later): natural starts and sound effects

- **Complaint:** some clips opened on her looking away or not ready to speak. The replica was frame-identical to the reference at every cut, so the cause was the reference's cut points, which sit inside pauses (measured lead-in before the voice: mean 0.20 s, up to 0.95 s; six segments under 0.04 s, which clips the first syllable). Fix: `tighten_segments.py` (see `analyze-reference-video`).
- **Effects:** two CC0 sets (see `sfx-sources.md`), a palette with `make_sfx_pack.py`, 21 effects placed with `build_steps.py --sfx` on two audio lanes. 201 steps, 0 failures. The raw swishes (0.07-0.2 s) had to be slowed and echoed to work as a slide.
- **Verified:** a lane created with `track_add bottom: true` gets a lowercase id (`t4`); use the returned `createdId`, not a guessed `T5`.
- **Verified:** correlating a noisy effect against the final mix, and the swell detector, both failed to find effects mixed under speech (they are really there: an isolated project with one effect shows it at the right second). Do not use those checks for effects under a voice.

## 2026-10-23: first real pair (a 4-minute talking-head recording and its 57-second vertical reel)

- **What the pair was:** the raw file was one continuous take of a person talking (plus a trailing editor end card); the edit was jump cuts of that take with B-roll, app screenshots and image cards laid over the continuing voice, phrase-by-phrase captions, and a few typed titles. The B-roll was **not** in the raw file, so the replica rebuilds the voice track and the captions exactly and puts labelled placeholders where the other footage goes.
- **Result of the run (verified):** 24 aligned voice segments, 14 placeholders, 70 captions, 3 titles, all built by one 154-step `mcp_run.py` session with 0 failures; export 1080x1920 at 30 fps, 1702 frames = the reference's duration. `compare.py` found 19 of 25 reference cuts, with timing error median 0 and worst 0.13 s. The misses were cuts between adjacent placeholders of the same colour (give neighbours different colours if cut detection matters) and a picture-only cut inside one take.
- **Picture alignment failed on a talking head** (17 of 26 shots `low`, wrong sources), **audio alignment worked** (scores 0.76-0.92, boundaries to about 10 ms). Added `align_audio.py`; see `analyze-reference-video`.
- **The SFX detector fired on the voice** (251 events on a voice-only track, strongest ones were phrase starts after digital silence). Added `in_speech` / `after_silence` flags, a strength floor and a `sfx_verdict`. Real finding for that reel: no music bed, no placed sound effects; the sound design was the voice only.
- **Whisper `base` (ggml, Spanish)** gave usable word timings but wrong words for names and jargon. Correct against the burned-in captions of the reference; keep a list of guesses for the user to review.
- **Caption style that matched the reference:** `captions_add` with `offsetY 0.28` (lower third), `style {color: "#F4EFD0", fontWeight: 600, fontSize: 0.034, strokeWidth: 0, shadow: true}`; typed titles at `offsetY -0.28`, weight 800, size 0.045. Concat has no typewriter animation, so typed titles are static text.
- **Correction:** `title_add` with `above: true` is the right way to get a title over the footage (the schema says it takes the first free lane above everything occupied over the span). The earlier note that it "did not move the title to a visible lane" was a misreading: the title it created without `above` landed on `T1`, behind the footage.
- **Verified:** `concat --project <folder>` opens a project directly in the window; the folder must not be open in another process.
- **Verified:** media imported through the headless MCP has no bin thumbnails until the window opens the project; the window logs missing `.thumb.jpg` files once and creates them.
- **Not available / not done:** icons (a check mark, a bookmark) and small picture-in-picture overlays were left out; a text typing animation; the reference's picture-only cuts.

## 2026-10-23: first session, synthetic footage

- **Verified:** the whole path works end to end: `project_create` -> `media_import` -> `clip_add` / `clip_trim` / `clips_move` -> `clip_update` (volume, fadeOut, transitionIn) -> `title_add` -> `project_save` -> `preview_frame` -> `export_start` / `export_wait`. A 3 s 640x360 export finished in seconds.
- **Verified:** the source in/out recipe in `SKILL.md` gives exact `sourceStart`, `start`, `duration`.
- **Verified gotcha:** a title that `title_add` puts on `T1` is hidden behind footage on `T2`; the same style on `T4` shows. Higher lane number draws above. `above: true` fixes it (see the later entry). Always check the `track` and a `preview_frame`.
- **Verified gotcha:** `preview_frame` `output` and `export_start` `output` must be under the home folder; elsewhere the call is refused with "is outside where this API writes".
- **Verified:** `media_import` can read files from anywhere (even `/private/tmp`); only writes are restricted.
- **Verified:** the tool list has 42 tools in 0.2.8 (the docs/agent notes say 45; trust `--list-tools`).
- **Verified:** Concat's sound library manifest (`https://raw.githubusercontent.com/concatapp/assets/main/audio/manifest.json`) returns 404, so there is no built-in SFX to place. User-supplied files or `make_sfx.py` stand-ins are needed.
- **Detector behaviour (synthetic):** cuts found within 0.04 s; high-pass noise swells found as `whoosh_swell` with the peak about 0.13 s before a cut that the generator had at 0.10 s; a 55 Hz decaying sine impact is found only by the low-band detector (the percussive stem drops it); a 120 BPM tick gave 117.5 BPM.
- **Alignment (synthetic):** flat-colour footage cannot be localized within a repeated colour (low confidence is expected there); real footage with texture should do far better. Untested on real footage yet.
- **Not yet tried:** speed ramps, masks, keyframed transforms, captions_add, multiple timelines, ducking via `keyframe_set` volume, `edit_apply` batches, the window (non-headless) mode, import of vertical footage with a different project size.

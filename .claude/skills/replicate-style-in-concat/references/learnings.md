# Learnings: driving Concat from an agent

Newest first. Each entry says how it was found. Verified = run against the real app (Concat 0.2.8, macOS, debug build, headless MCP).

## 2026-10-23: first session, synthetic footage

- **Verified:** the whole path works end to end: `project_create` -> `media_import` -> `clip_add` / `clip_trim` / `clips_move` -> `clip_update` (volume, fadeOut, transitionIn) -> `title_add` -> `project_save` -> `preview_frame` -> `export_start` / `export_wait`. A 3 s 640x360 export finished in seconds.
- **Verified:** the source in/out recipe in `SKILL.md` gives exact `sourceStart`, `start`, `duration`.
- **Verified gotcha:** a title that `title_add` puts on `T1` is hidden behind footage on `T2`; the same style on `T4` shows. Higher lane number draws above. `above: true` did not move it to a visible lane in the test (it still landed on `T4` only because `T1`-`T3` were taken). Always check the `track` and a `preview_frame`.
- **Verified gotcha:** `preview_frame` `output` and `export_start` `output` must be under the home folder; elsewhere the call is refused with "is outside where this API writes".
- **Verified:** `media_import` can read files from anywhere (even `/private/tmp`); only writes are restricted.
- **Verified:** the tool list has 42 tools in 0.2.8 (the docs/agent notes say 45; trust `--list-tools`).
- **Verified:** Concat's sound library manifest (`https://raw.githubusercontent.com/concatapp/assets/main/audio/manifest.json`) returns 404, so there is no built-in SFX to place. User-supplied files or `make_sfx.py` stand-ins are needed.
- **Detector behaviour (synthetic):** cuts found within 0.04 s; high-pass noise swells found as `whoosh_swell` with the peak about 0.13 s before a cut that the generator had at 0.10 s; a 55 Hz decaying sine impact is found only by the low-band detector (the percussive stem drops it); a 120 BPM tick gave 117.5 BPM.
- **Alignment (synthetic):** flat-colour footage cannot be localized within a repeated colour (low confidence is expected there); real footage with texture should do far better. Untested on real footage yet.
- **Not yet tried:** speed ramps, masks, keyframed transforms, captions_add, multiple timelines, ducking via `keyframe_set` volume, `edit_apply` batches, the window (non-headless) mode, import of vertical footage with a different project size.

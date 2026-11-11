# Which Concat version these skills are written for, and how to rebuild it

**These skills, recipes and scripts are written for Concat 0.2.10** (upstream tag `v0.2.10`, merged into this fork on
2026-11-11). Everything dated before that in `learnings.md` was verified on **0.2.8**; where the two differ, this page
says so. The binary the MCP server runs is `src/target/debug/concat` (or the one the user's MCP config points to),
and **it is not rebuilt by `git pull`**: a binary older than the docs gives "tool not found" (`clip_masks`,
`mask_key_set`, `title_style_words`, `timeline_linkage`) or silently different pictures.

## 1. Check before any video job (10 seconds)

```bash
cd <repo>/src && ./target/debug/concat --version                 # must print: concat 0.2.10  (or newer)
python3 -I <skills>/replicate-style-in-concat/scripts/mcp_run.py --bin ./target/debug/concat --list-tools | cut -d: -f1 | grep -c .   # 46 in 0.2.10 (42 in 0.2.8)
python3 -I <skills>/replicate-style-in-concat/scripts/mcp_run.py --bin ./target/debug/concat --list-tools | grep -E "^(clip_masks|clip_mask):" | cut -c1-30   # clip_masks = new, clip_mask = old
```

(`--list-tools` belongs to `mcp_run.py`, not to the binary. If the MCP server is registered in the client, `concat_version`
returns the same number: `"concat":"0.2.10"`.)

If it prints 0.2.8 or 0.2.9, or lists `clip_mask`, **rebuild** (below) and tell the user it takes a while.
`concat --version` prints `concat 0.2.8` on the old one.

## 2. Rebuild

The toolchain is pinned (`src/rust-toolchain.toml`, 1.93.1). If `cargo` is not found in the shell (it is not on the PATH
in a non-login shell), use the toolchain folder directly:

```bash
export PATH="$HOME/.rustup/toolchains/1.93.1-aarch64-apple-darwin/bin:$PATH"   # Apple silicon; `rustup toolchain list` shows the name
cd <repo>/src && cargo build -p concat -p concat-cli          # first build after a big upstream merge: about 10 minutes
```

Run it in the background and wait for it; do not poll. FFmpeg 7+ dev libraries, cmake and a C++ compiler must exist
(`brew install ffmpeg cmake`). Ask the user before installing anything. Keep a copy of the old binary
(`cp target/debug/concat /somewhere/concat-old`) if you want to compare; a rebuild overwrites it.
After pulling upstream again: `git fetch upstream`, merge into a branch, rebuild, re-run section 1, then re-test the
split-screen mask (section 4) before trusting any recipe.

## 3. What changed between 0.2.8 and 0.2.10 for these recipes (verified on 0.2.10 unless marked)

| Topic | 0.2.8 | 0.2.10 |
|---|---|---|
| Mask | `clip_mask {clipId, mask:{shape,x,y,width,height,rotation,roundness,feather,invert}}`; `mask: null` removes it; keys with `keyframe_set` on `maskX`, `maskY`... | `clip_masks {clipId, masks:[{source:{kind:"shape",shape,width,height,roundness}, mode:"add"\|"subtract"\|"intersect"\|"none", x, y, rotation, scale, feather, expand, opacity, invert, id?}]}`, top first; `masks: []` removes all; animate with `mask_key_set` (`id` of the mask + number name). `clip_update patch.masks` does the same. |
| Split-screen mask on the upper raw | `clip_mask` `{"shape":"linear","x":0,"y":0,"rotation":90,"invert":true,"feather":0.14}` | `clip_masks` `[{"source":{"kind":"shape","shape":"linear","width":0.66,"height":0.66,"roundness":0},"mode":"add","x":0,"y":0,"rotation":90,"feather":0.14,"invert":true}]` (same picture, checked pixel by pixel against the 0.2.8 numbers) |
| Entrance / exit / loop animation of a title, caption, shape, picture or clip | not possible (typed text = one clip per letter; rise+fade = opacity and offsetY keyframes) | `clip_update {clipId, patch:{motion:{in:{kind,seconds}, out:{kind,seconds}, loop:{kind,seconds,amount}}}}`; entrances/exits `fade, slide-left, slide-right, slide-up, slide-down, zoom-in, zoom-out, pop, drop, rise, spin, flip, swing, squash`; loops `pulse, heartbeat, float, wiggle, sway, jitter, flicker, breathe, spin`. Checked: `in rise 0.5 s` + `out fade 0.4 s` on a title gives the rise-and-fade of the house style in one call. Still no letter-by-letter typing. |
| Words of a title in another colour/weight/size | not possible | `title_style_words`, `title_clear_word_styles`; `captions_add style.runs` |
| Voice isolation (DeepFilterNet 3 inside the app) | not there | `edit_apply {command:{op:"setClipVoice", clipId, voice:{kind:"speech"\|"vocals", voice:1.0, background:0.0}}}` (null removes). The call is accepted; **its sound has not been compared with the house voice chain yet** (ffmpeg highpass+afftdn, then `concat.denoise 100`, `concat.enhance-voice 100`, `concat.loudness -16`). Keep the house chain until someone compares them. |
| Speed | `clip_speed` | `clip_speed` gained `ripple` (clips after it move by the change). A speed curve exists in the window; not driven from the MCP yet. |
| Sound layers, linkage | - | `effect_layer_add {sound:true}`, `timeline_linkage` (not tried) |
| Project file | format version 1 | format version 2 (see 4) |
| New effects | - | Shake, Impact, Beat Shake, Prism Shake on the "Shake & Motion" shelf; `effects_list` has the ids |
| CLI previews | - | `concat-cli preview ... --moment` (an effect at any instant) and `--progress` (a transition at any point) |

## 4. Projects made with 0.2.8 or earlier LOSE THEIR MASKS in 0.2.10 (found 2026-11-11)

Opening a version-1 project (a copy of `sala_v17`, the split-screen reel with 17 masked clips) in 0.2.10 gives no error, but
the app **no longer reads the old `mask` field**: every masked clip is drawn without its mask, so in the split-screen
the second person's half was empty, in previews and in the export (checked on a 76.7 s export). Everything else
(titles, pictures, cuts, voice, loudness -16.5 LUFS, duration 76.667 s) came out right.

Fix, verified (preview pixel-identical to the same edit made with `clip_masks` by hand):

```bash
python3 -I <skills>/replicate-style-in-concat/scripts/migrate_v1_masks.py <project copy> --steps steps.json
python3 -I <skills>/replicate-style-in-concat/scripts/mcp_run.py --bin <repo>/src/target/debug/concat steps.json
```

It opens the project, calls `clip_masks` on every clip that had a `mask` and saves. Do it on a **copy**: saving writes format
version 2, which an older Concat cannot open. Editing `concat.json` by hand (adding `masks`, with or without
`"version": 2`) did NOT work: the picture stayed wrong. Old mask keyframes are not carried over; the script lists those clips.
New projects built from scratch with the recipes do not need this.

Other upstream changes seen while merging that matter to the shared machine: the painted-title cache folder
(`~/Library/Application Support/app.concat.editor/titles`) is shared by all versions, and after the 0.2.10 build used
it the 0.2.8 binary failed to export a project ("titles/<hash>.png: No such file"). Do not run two versions on one
project at the same time; once the new build is chosen, stay on it.

## 5. Not tried yet on 0.2.10

Voice isolation against the house chain (sound only measured by loudness so far), speed curves, `mask_key_set`
animation, the new Shake effects, `timeline_linkage`, `concat-cli preview --moment`. When one is tried, add the result
to the table above and to `learnings.md`.

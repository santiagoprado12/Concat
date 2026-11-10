# The user's approved sound effects (8 files, 207 KB)

The only effects the user has approved for their videos (2026-11-03, "por ahora solo esta lista para todo"). They chose them after auditioning about 200. **Use only these, never others unasked** (no synthesized pops, no "dry" clicks: they said those do not work or annoy them). All are CC0 (public domain), so they live in the repo; everything else in `sfx-sources.md` stays out of it.

How to use them: `media_import` the file, `clip_add` it on its own audio lane (`track_add bottom: true`, one lane per sound so none overlap) at the first frame of what appears, then `clip_update {patch: {"volume": V}}`. Start low: the user lowered every sound they heard, and the levels below are what they settled on or heard without complaint. Concat's own sound shelf is empty; `scripts/add_to_library.py` can put these into the user's library (Audio page, Mine shelf) under the names in the table.

## Used in delivered videos (use these first)

| File | Library name | Length | What it sounds like | Use it for | Level | Where it was used |
| --- | --- | --- | --- | --- | --- | --- |
| `pack-swish-ligero.wav` | Pack - Swish ligero | 0.08 s | very short soft air swish | **A card, image or screenshot entering the picture** (an image card, an ebook cover, a screenshot); also the first image of a reel. The user asked for exactly this sound on the very first image after hearing it on the cover | 0.20 | split-screen reel "Renovando mi sala": every card entrance, 7 to 11 per reel; earlier reels as the exit swish (0.4) |
| `kenney-drop-002.wav` | Kenney - drop 002 | 0.20 s | soft low drop, the heaviest of the set | **First item of a list that builds up** (the first row, "a day") | 0.335 (-9.5 dB) | list reel "Rutina realista", first row of each round; placed on the finger touching the row, not on the text |
| `kenney-confirmation-001.wav` | Kenney - confirmation 001 | 0.29 s | short soft two-note ding | **Second item of the same list** ("a week") | 0.178 (-15 dB) | same reel |
| `kenney-confirmation-002.wav` | Kenney - confirmation 002 | 0.56 s | longer, softer ding | **Third item of the same list** ("a month") | 0.141 (-17 dB) | same reel |
| `pack-pop.wav` | Pack - Pop | 0.11 s | small round pluck | **A title or label appearing** at the start of a video | 0.25 to 0.35 | two reels; in the split-screen reel it was replaced by the swish ligero when the user asked for the same sound as the first card |

## Approved, not placed in a delivered video yet

| File | Library name | Length | Use it for | Level to start at |
| --- | --- | --- | --- | --- |
| `pack-swish-corto.wav` | Pack - Swish corto | 0.19 s | a hard cut to B-roll or a new scene (put it 0.04 s before the cut), a list clearing | 0.40, then lower to taste |
| `kenney-confirmation-003.wav` | Kenney - confirmation 003 | 0.32 s | alternate for the second or third list item when the same ding repeats | match the loudness of the row it replaces |
| `kenney-drop-003.wav` | Kenney - drop 003 | 0.20 s | alternate for the first list item | match drop 002 (0.335) |

## Situations at a glance

| Situation | Sound |
| --- | --- |
| Image, cover or screenshot appears | pack-swish-ligero (0.20) |
| First, second, third row of a list | drop 002 (0.335), confirmation 001 (0.178), confirmation 002 (0.141) |
| Title or label appears | pack-pop (0.25 to 0.35), or the swish ligero if the first thing on screen is an image |
| Cut to another scene | pack-swish-corto (0.40), not yet used |
| Music | none by default; if asked, a CC0 ambient piece at gain 0.10 (see `sfx-sources.md`) |

## Placement rules

- On the first frame of the thing that appears. If a hand or finger touches it, put the sound on the touch (the user moved the first list sound 0.38 s later, onto the finger).
- Every sound well under the voice (voice at -16 LUFS); never overlapping another effect on the same lane; skip a sound if it lands on an important word.
- The user decides by ear: ask which sounds to lower or remove after the first render.

## Sources and licences

- `kenney-*.wav`: Kenney "Interface Sounds" 1.0, CC0 (`KENNEY-LICENSE.txt`), original files `drop_002`, `drop_003`, `confirmation_001` to `003`.
- `pack-swish-*.wav`: from the "Swishes Sound Pack" by artisticdude on OpenGameArt, CC0 (swish-7 high-passed at 180 Hz for corto, swish-12 at 250 Hz for ligero; built by `scripts/make_sfx_pack.py`).
- `pack-pop.wav`: Kenney `pluck_001`, CC0, through the same script.

# Sound effect sources (open licences)

Concat's own sound library is not published (`https://raw.githubusercontent.com/concatapp/assets/main/audio/manifest.json` returned 404 on 2026-10-23 and again on 2026-11-03). These two sets are CC0, small, and were verified to download and convert. **Ask the user before downloading**; keep each archive in its own new folder under `~/concat-analysis/sfx/` and never commit audio to the repo, **except the eight approved sounds, which are kept in `../sounds/` with their usage guide** (`sounds/README.md`).

| Set | Author / source | Licence | Size | Use |
| --- | --- | --- | --- | --- |
| Swishes Sound Pack: `https://opengameart.org/sites/default/files/swishes.zip` (13 wavs, 0.07-0.2 s) | artisticdude, OpenGameArt (`https://opengameart.org/content/swishes-sound-pack`) | CC0 | 385 KB | Whoosh and slide sounds. Too short alone: `make_sfx_pack.py` slows one to about 0.36 s |
| Kenney Interface Sounds: `https://github.com/Calinou/kenney-interface-sounds/archive/refs/heads/master.zip` (100 wavs; files under `addons/kenney_interface_sounds/`) | Kenney (kenney.nl), packaged by Calinou | CC0 | 1.7 MB | Pops, ticks, clicks, "appear" sounds |

```bash
D=~/concat-analysis/sfx; mkdir -p $D/swishes_zip $D/kenney_zip
curl -fL -sS --max-filesize 20000000 -o $D/swishes_zip/swishes.zip https://opengameart.org/sites/default/files/swishes.zip
curl -fL -sS --max-filesize 80000000 -o $D/kenney_zip/kenney.zip https://github.com/Calinou/kenney-interface-sounds/archive/refs/heads/master.zip
unzip -q $D/swishes_zip/swishes.zip -d $D/swishes && unzip -q $D/kenney_zip/kenney.zip -d $D/kenney   # "__MACOSX" noise is harmless
python3 -I make_sfx_pack.py --swishes $D/swishes/swishes --kenney $D/kenney/kenney-interface-sounds-master/addons/kenney_interface_sounds --out $D/pack
```

Palette written to `$D/pack`: `slide_in` (0.36 s), `slide_out` (its reverse), `swish_short` (0.19 s), `swish_light` (0.08 s), `pop`, `tick`, `appear`, `click`; each peaks at -6 dBFS before the clip volume is applied.

Not CC0, so not used: Mixkit (its own licence), itch.io whoosh packs (CC-BY or paid), Motion Array (commercial licence). No impact or boom set is included; Kenney's separate Impact Sounds pack (CC0) would cover it, not tried yet.

## Placement rules that worked

- Card or screenshot sliding in over the picture: `slide_in` starting 0.08 s before the clip, volume 0.7; `swish_light` near its end, volume 0.4.
- Full-frame B-roll cut: `swish_short` 0.04 s before the cut, volume 0.45 (about half the voice level, so the voice stays clear).
- Title appearing: `pop` on its first frame, volume 0.5.
- Put effects on their own audio lanes (`track_add bottom: true`, one lane per kind) so they never overlap on a lane. Verified: a single clip at 1.0 s lands at 1.0 s in the export (the isolated test is a 3 s grey clip plus one effect, checked on a spectrogram).
- A noisy effect mixed under speech cannot be verified by correlation or by the swell detector (both returned nothing useful); verify by exporting a project with only the effect, as above, and by `timeline_read`.

## Background music (CC0)

`The Budding of Consciousness` by Yoiyami on OpenGameArt (`https://opengameart.org/content/the-budding-of-consciousness-%E2%80%93-cc0-ambient-minimalist-theme-yoiyami-blue-series-%E2%80%93-no4`), CC0, `the_budding_of_consciousness.wav`, 43 MB, 224 s, 48 kHz stereo, -18.3 LUFS, a gentle ambient piece with no vocals. Ask before downloading (43 MB):

```bash
D=~/concat-analysis/music/yoiyami_zip; mkdir -p $D
curl -fL -sS --max-filesize 90000000 -o $D/the_budding_of_consciousness.wav https://opengameart.org/sites/default/files/the_budding_of_consciousness.wav
```

Use it at a clip gain of 0.10 (about -20 dB, so roughly -38 LUFS under a voice at -16) with a 1.5 s fade in and 2.5 s fade out; `build_steps.py --music` does the trim and the fades. Not verified by ear. `freepd.com`, often cited as public-domain music, answered as "closed" when fetched, and Kevin MacLeod's tracks need attribution (CC-BY), so neither was used.

## The user's approved palette (use only these until told otherwise)

After auditioning about 200 sounds in the Audio page, the user allowed eight for everything (2026-11-03). They live in their library under these names (`add_to_library.py` puts them there; Kenney files are `confirmation_001.wav`, `drop_002.wav` ... in the set below):

| Library name | Use it for | Level the user settled on |
| --- | --- | --- |
| Kenney - drop 002 | first row of a list (a day) | volume 0.335 (-9.5 dB) |
| Kenney - confirmation 001 | second row (a week) | 0.178 (-15 dB) |
| Kenney - confirmation 002 | third row (a month) | 0.141 (-17 dB) |
| Kenney - confirmation 003, Kenney - drop 003 | alternates for the same cues | not placed yet; match the loudness of the row they replace |
| Pack - Pop, Pack - Swish corto, Pack - Swish ligero | a title/label appearing, a cut to B-roll, a list clearing | start at 0.35 (pop) and 0.4 (swishes), then lower to taste (the user lowered every sound they heard) |

Placement: on the first frame of the thing that appears, except where a hand or finger touches it: then on the touch (the user moved the first one 0.38 s later, onto the finger). One audio lane per sound (`track_add bottom: true`). Set clip volume in dB-derived gains; the user's final values are well under the voice, so start low. Not wanted: synthesized pops (sine sweeps, kalimba, bubble), "dry" clicks; the rest of the library stays available for the user to try, but never place from it unasked.

More CC0 sets found and used (2026-11-03), each fetched after the user said yes; keep each in its own folder under `~/concat-analysis/sfx/`:

| Set | Source | Licence | Notes |
| --- | --- | --- | --- |
| Pop sounds (10 `.ogg`, `pop1`..`pop10`) | OpenGameArt `https://opengameart.org/content/pop-sounds` by cogitollc; files at `https://opengameart.org/sites/default/files/pop<N>.ogg` | CC0 | short, dry |
| Pop sounds (9 `.wav`) | OpenGameArt `https://opengameart.org/content/pop-sounds-0` by EZduzziteh; `.../files/pop<N>.wav` | CC0 | bubble-like |
| Kenney UI Audio (50 `.wav`) | `https://github.com/Calinou/kenney-ui-audio/archive/refs/heads/master.zip` (`addons/kenney_ui_audio/`), original at `https://kenney.nl/assets/ui-audio` | CC0 | clicks, switches |
| Kenney Interface Sounds (100 `.wav`) | see the table above; the `confirmation_*` and `drop_*` files are the approved ones | CC0 | |

Not tried: OpenGameArt "3 pop sounds" and "UI Sounds", Kenney Digital Audio (licence not confirmed on Kenney's page), a 35-file "mouth pops" pack on Gumroad (licence unseen). OpenGameArt answers a plain `curl` with a browser user agent, but `WebFetch` gets a 403 from it, so list the file links with `curl -A "Mozilla/5.0" ... | grep -o 'https://opengameart.org/sites/default/files/[^"]*'`.

Softening a dry pop (offered, not chosen): `ffmpeg -i pop.wav -ac 1 -af "lowpass=f=4200,aecho=0.8:0.55:35|75:0.28|0.14,alimiter=limit=0.5:level=disabled"`, then normalise the peak. Do not put `afade` with `st=0` in the chain: it silences the whole file.

## Putting sounds where the user can audition them

Concat's built-in shelf is empty (manifest 404). `scripts/add_to_library.py` copies sounds into the user's own library folder and writes `library.json` the way the app does, so they show on the Audio page's Mine shelf with a waveform (reopen the project to refresh). Name them `Set - name` so the shelf sorts by set. Example: `uv run --python 3.12 scripts/add_to_library.py --dir <kenney folder> --prefix "Kenney - "`.

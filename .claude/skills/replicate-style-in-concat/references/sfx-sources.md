# Sound effect sources (open licences)

Concat's own sound library is not published (`https://raw.githubusercontent.com/concatapp/assets/main/audio/manifest.json` returned 404 on 2026-10-23). These two sets are CC0, small, and were verified to download and convert. **Ask the user before downloading**; keep each archive in its own new folder under `~/concat-analysis/sfx/` and never commit audio to the repo.

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

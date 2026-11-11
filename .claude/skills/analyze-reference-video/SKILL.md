---
name: analyze-reference-video
description: Turn a video into data and images Claude can actually read - cut times, transition strips, one frame per shot, loudness, spectrograms, a timeline of sound effects (hits, whooshes, risers), the music beat grid, and how sound lines up with cuts. Use this whenever the user hands over a reference or "edited" video and wants to understand or copy its editing style, asks how a video is cut or paced, wants to know where its sound effects and music sit, wants to find which parts of raw footage ended up in an edited video, or wants to check how close a replica in Concat is to its reference - even if they never say "analyze". Also use it when the reference is a phone screen recording of an editor's preview (CapCut and the like): it recovers the cuts, the zoom/rotation/offset and the colour grade the editor applied, and the true picture-to-raw sync. Claude cannot watch or listen to a video directly; this skill is how it gets evidence.
---

# Analyzing a reference video

**Claude cannot watch or hear a video.** It can read images (frames, contact sheets, spectrograms) and data (JSON, text). This skill converts a video into exactly that. Everything it says about audio comes from detectors, not from listening, so treat sound labels as informed guesses and confirm the important ones on the spectrogram and against the frame at that moment.

Nothing is downloaded and nothing leaves the machine. Needs `ffmpeg`/`ffprobe` on PATH and `uv` (scripts declare their own dependencies and run on Python 3.10-3.12; `uv` fetches them).

## Run it

Given a link (Instagram, TikTok, YouTube) instead of a file, first use `fetch-reference-video` to download it, then continue here with the path it prints.

```bash
S=<repo>/.claude/skills/analyze-reference-video/scripts
uv run $S/analyze.py all  /path/to/video.mp4 --out ~/concat-analysis/<name>/ref
```

- Put output **under the home folder, never inside the repo**. Concat's MCP server only writes under the home folder, and analysis output is large.
- One step at a time: `probe | shots | frames | audio | sfx | report`. Re-run `report` after changing anything.
- `--cut 12` is the hard-cut sensitivity (frame-difference score 0-100). Lower it for soft footage with missed cuts, raise it for flashy footage with false cuts. `--gradual 3` controls dissolve detection.
- Long videos: `--max-shots`, `--max-strips`, `--spec-seconds` keep the number of images readable.

## Everyday helpers (use them all the time)

- `frames_grid.py` - many frames (or existing pictures) in ONE labelled image: a frame every 0.1-0.5 s around a second the user named, 15 fps to see how an element appears, a face crop per candidate second, A/B/C/D options for the user.
- `audio_peek.py` - sound as text: `env` (level every 20 ms), `silences`, `cuts` (level before each cut: still loud = cut during a word), `lead`/`tail` (dead air), `spec` (spectrogram picture), `tones` (a hum to filter).
- `align_captions.py` - your corrected caption words on Whisper's times for one piece.
- The full order of work and every trick: `video-edit-playbook` (`references/hacks.md`).

## What it writes and how to read it

| File | What it is | How to use it |
| --- | --- | --- |
| `style-report.md` | Short human summary | Read first |
| `style-report.json` | Everything merged: pacing, boundaries, loudness, SFX events, music, correlations | Source of truth for numbers |
| `contact_NN.jpg` | One frame from the middle of each shot, labelled `#shot time` | **Read the images.** Shot content, framing, text styles, colour grade |
| `transitions/boundary_*.jpg` | Six frames around each cut, labelled with offset seconds | **Read the images.** Decide hard cut vs dissolve vs whip vs zoom vs flash; a `gradual` kind is already a likely dissolve |
| `spectrogram_NN.png` | Log-frequency spectrogram, 30 s per image | **Read the images.** Vertical bars are hits and clicks, broadband blobs are whooshes, a diagonal sweep is a riser, a low smear is a boom |
| `audio.json` | Integrated loudness, LRA, true peak, 100 ms loudness curve, silences | Mix level targets |
| `sfx.json` | Raw event list and beat grid | Detail behind the report |

## Reading the sound results

- Event labels: `hit_thump` (low, short; often a kick or a placed thud), `impact_boom` (low and long), `click_pop` (short and bright), `whoosh_swell` (broadband noise bump, 0.2-1.8 s), `riser` (long rising noise), `ambience_or_swell` (long bump; maybe room tone).
- `on_beat: true` means the event sits within 50 ms of the music's beat grid, so it is probably part of the music. **An impact or whoosh that is `on_beat: false` is the strong candidate for a placed effect.**
- `correlations.sfx_near_cuts`: per label, the median offset of the event **minus the cut time**. Negative means the sound leads the cut (a whoosh that peaks 0.12 s before the cut is the classic look). Swells also give `median_end_offset_s`. The peak detector runs about 30 ms late on swells.
- `fraction_of_cuts_with_sfx`, `cuts_within_60ms_of_beat`: cuts that carry an effect, cuts that land on the beat. These are the numbers that define a style.
- Speech and loud music mask effects: expect missed whooshes under dialogue. If a spectrogram shows a clear bar or blob the list does not, the picture wins.
- **On a track that is mostly a voice the detectors fire on the voice itself** (plosives, breaths, the first syllable after a gap): the first real run reported 251 "events" in a voice-only reel. So each event carries `in_speech` (voiced speech around it) and `after_silence` (starts within 0.15 s of a silence); `style-report.json` keeps all of them but the correlations use only the `events_plausibly_placed` (outside speech, not after silence, 20 dB or more; swells are exempt from the speech test). **Read `correlations.sfx_verdict` first**: it says "no consistent effect-on-cut pattern" when no label has at least 3 events with a spread under 80 ms around the cuts. Then look at the spectrogram: voice-only audio shows clean harmonic stripes and nothing else, and that means *no sound design*, which is a valid finding to report.
- There is no speech transcript in these scripts; see "Transcript, with word timings" below. For voice-heavy tracks run `sounds.py` (below) before trusting any of the above.

## Better transitions: TransNet V2 (`transitions.py`)

`analyze.py shots` uses a frame-difference threshold, so it needs tuning (`--cut`, `--gradual`) and reads a fast slide or a dissolve between similar shots poorly. `transitions.py` runs TransNet V2, a small learned shot-boundary detector (31 MB ONNX, MIT, CPU, a few seconds per minute of video):

```bash
uv run $S/transitions.py VIDEO --out ~/concat-analysis/<name>/ref --shots ~/concat-analysis/<name>/ref/shots.json [--download]
```

It writes `transitions.json` (`cuts` with time and score; `graduals` with start, end, duration and peak) and `transitions/gradual_NN.jpg`, six frames across each gradual transition. **Open the strips**: the model says "something gradual happens here", the picture says whether it is a dissolve, a fade, a wipe/slide or a flash. With `--shots` it also reports `agreement` with the frame-difference detector: `cuts_only_transnet` (often the *end* of a slide or zoom that the other detector calls nothing) and `scdet_only`.

Verified on a 64 s reel with 15 cards whose times were known: every card's end was found as a cut within 0.02 s (one frame at 30 fps), and the 11 cards that slide in came out as gradual transitions of 0.13-0.4 s starting within 0.11 s of the real start; all 21 boundaries of the frame-difference detector were also in its list. Jump cuts inside one talking head are not seen by either (same face before and after): use `align_audio.py` for those. The model is fetched only with `--download`; ask first.

## Sound effects without the voice in the way (`sounds.py`)

On a track where someone talks, most of what the detectors in `sfx` report is the voice. `sounds.py` removes it first:

```bash
uv run $S/sounds.py VIDEO --out ~/concat-analysis/<name>/ref [--download]
uv run $S/analyze.py report VIDEO --out ~/concat-analysis/<name>/ref     # now uses sfx_stem.json
```

It separates voice from the rest with Demucs (`htdemucs`; `uv` fetches PyTorch and 84 MB of weights once, about 0.4 s of CPU per second of audio), runs the same event detector on the voiceless stem, then cuts a window around every event and asks YAMNet (AudioSet, 16 MB, Apache-2.0) whether it sounds like a whoosh. `sfx_stem.json` has the `sfx.json` schema plus `yamnet_whoosh`, `yamnet_top`, `name` and `name_confidence`; `style-report.json` uses it automatically when present. Demucs applies a random time shift, so two separations of the same file differ slightly (112 to 121 events on the test reel); the stem is cached and reused, delete `stems/` to redo it. The stems are kept in `stems/` (`no_vocals.wav` is worth listening to for the user; `vocals.wav` is deleted unless `--keep-vocals`).

What it is good for, measured on a 64 s reel with a music bed and 46 hand-placed effects:
- **When effects happen.** At the 20 dB floor the report applies: 36 of 46 found (chance 23 %, 95th percentile 46 %) and 42 of 45 events were effects. At 15 dB: 42 of 46 found (chance 30 %, p95 61 %) with 58 of 78 events being effects. The mixed-track run had 68 of its 123 events from the voice.
- **What they are: barely.** Only some long whooshes score above the floor on the YAMNet "Whoosh" class (4 of 11 slide-ins, none of the 49 non-effect events); pops, ticks, light swishes and short swishes were never named. Treat `name_confidence: "low"` as "an effect of unknown kind" and describe it by its shape (`label`, `decay_s`, `centroid_hz`) and the spectrogram, not by a name. `medium` means YAMNet heard a whoosh there (score 0.03 or more; no false ones in the test reel, about a third of the real ones found); the shape label can still say `impact_boom`, because a slide's low end triggers the bass detector.
- **Leaks.** Demucs does not separate perfectly: dings and pops can survive in the voice stem and some voice in the other. A reference with loud music still gives beats and bass booms (`impact_boom` from the low-band detector) that are not effects; `on_beat` helps there.

## Pairing raw footage with the edited cut

When the user supplies both the unedited footage and the edited video, first look at the raw contact sheet: **is the raw one long take of a person talking, or varied footage?** That decides the method.

**Picture-based, `align.py`** - for varied footage (many different shots):

```bash
uv run $S/analyze.py shots EDITED.mp4 --out ~/concat-analysis/<name>/ref      # if not already done
uv run $S/align.py RAW.mp4 EDITED.mp4 --out ~/concat-analysis/<name>/ref
```

`alignment.json` gives, for every edited shot, the raw `raw_in`/`raw_out`, the playback `speed`, and a `confidence`. It matches 16x9 grey thumbnails, so flat colours, heavy crops, zooms and colour grades lower confidence. Check `medium`/`low` shots by eye against the contact sheet of both videos before trusting them. **It cannot work on a talking head**: every frame looks the same, so almost every shot comes back `low` (verified: 17 of 26 low, and the "matches" were wrong).

**Audio-based, `align_audio.py`** - for a talking head, or whenever the voice survives the edit (it almost always does):

```bash
uv run $S/align_audio.py RAW.mp4 EDITED.mp4 --out ~/concat-analysis/<name>/ref --shots ~/concat-analysis/<name>/ref/shots.json
```

It compares log-mel features of the edited audio with the raw audio in 1 s windows, merges runs that sit at the same raw offset into **segments** (`edited [a,b] <- raw [a+d, b+d]`) and refines each boundary to about 10 ms. `audio_alignment.json` lists the segments with a `score` (0.76-0.92 on real speech; below about 0.55 is unreliable) and, with `--shots`, tags every edited shot `talking_head` (the picture matches the raw picture at the aligned time, diff under about 14) or `other` (B-roll, a screenshot, an overlay: diff over about 35). Verified on a 4-minute raw and a 57 s edit: 24 segments covered the whole edit and the picture test separated the two kinds cleanly.

The audio cuts and the picture cuts of an edit are **independent**: B-roll is laid over a voice track that keeps going. Rebuild the voice from the segments, then cover the `other` shots with whatever footage belongs there.

## A phone screen recording of the editor's preview as the reference

Sometimes the "edited video" is a screen recording of CapCut or another editor playing the result. Crop the 9:16 preview, then: `align_audio.py` for raw segment offsets (the recording's audio lags its picture, about 0.2 s, and cuts inside a pause are arbitrary), `picture_sync.py` to correct them from the picture, and `register_frames.py` for the zoom, rotation, offset and colour change the editor applied. All three are verified against Concat renders; the numbers and the closed-loop check are in `replicate-style-in-concat/references/learnings.md` (2026-11-03, last entry).

```bash
uv run $S/register_frames.py raw_a.png edit_a.png raw_b.png edit_b.png
uv run $S/picture_sync.py --edit REC.mov --raw RAW.mov --crop 828:1472:0:175 --scale 1.16 --offset-y -0.046 --segment 0.5:3.3:4.64:1.2
```

## Raw footage with retakes (no reference video)

One person talking for minutes, each line recorded 2 to 5 times. **Do not trust Whisper's word timestamps here**: on a 5-minute file they drifted by up to 5 s and many words shared a single time (verified: "Sexto" was reported at 195 s, the voice was at 190 s). Use `phrases.py` instead:

```bash
uv run $S/phrases.py RAW.mov --model <ggml-base.bin> --lang es --out ~/concat-analysis/<name>/speech
```

It finds the voiced regions by energy (exact), groups them into phrases (pause over 0.45 s), cuts each phrase out and transcribes it alone, so every phrase has exact times and its own text. `vad.json` feeds `takes_to_plan.py`. Pick the take of each line from that list: usually the last complete one; a transcript that matches the intended sentence cleanly beats a later take that Whisper hears as garbled; a very short phrase right before a longer one is a false start; a take split in two by a pause (`Séptimo` ... `cuando vayas...`) is worse than one continuous region. Whisper still misreads names and jargon: write the correct caption text yourself and keep a list of the guesses. You cannot hear the takes, so tell the user which were chosen by transcript and ask them to spot-check.

## Tidying the cut points

`tighten_segments.py RAW audio_alignment.json --out tight.json` measures, per segment, the silence before the voice and after it (voice = within 14 dB of the speaking level). It trims head silence over 0.12 s down to a 0.08 s lead-in, extends the head earlier by up to 0.08 s when the voice starts within 40 ms of the cut (so the first syllable is not clipped), and shortens tails over 0.25 s to 0.15 s. Output is the same shape as `audio_alignment.json` plus a `timemap` that moves anything timed against the reference (captions, titles, placeholders, effects) onto the new cuts. On the first real pair the replica went from 56.7 s to 53.1 s and the awkward "not ready yet" starts disappeared. This changes the edit relative to the reference on purpose; say so.

## Transcript, with word timings

Concat's own transcriber is not reachable from the MCP or the CLI, so use whisper.cpp with the **same ggml model file Concat uses** (so one download serves both). `brew install whisper-cpp` gives `whisper-cli`. Model files live in Concat's data folder (`~/Library/Application Support/app.concat.editor/whisper-models/ggml-<id>.bin`; ids, sizes and SHA-256 are in `src/crates/concat-speech/src/transcribe.rs`). Ask before downloading one. Then:

```bash
ffmpeg -i EDITED.mp4 -vn -ac 1 -ar 16000 edited16k.wav
whisper-cli -m <ggml-base.bin> -l es -f edited16k.wav -ojf -of edited --split-on-word --max-len 1 -np
```

Add `--prompt "<script keywords, product and brand names>"` when you know the script: it fixed most misheard names and words in Spanish. Transcribe each chosen take **alone** (cut with ffmpeg first) so every phrase has exact times. `edited.json` -> `transcription[].offsets.from/to` (ms) per word. The `base` model mishears names, brands and jargon ("moodboard" came out as "mútbol"); **correct the words against the captions burned into the reference frames**, keep Whisper's timings, and list any guess you could not verify.

## Where a person looks, and how visible a cut would be (`face_gaze.py`, `frame_descriptors.py`)

Needed when a person must look attentive while someone else speaks (a listener in a split-screen reel, a reaction cutaway), or when you must join two pieces of footage of the same person without a visible jump. Run with `uv run --python 3.12` (MediaPipe 0.10.14 wheels; newer ones dropped the face mesh API):

```bash
uv run --python 3.12 $S/face_gaze.py RAW.mov --crop 0.5:0.17:0.5:0.62 --out gaze.json --contact contact.jpg
uv run $S/frame_descriptors.py RAW.mov --crop 0.5:0.17:0.5:0.62 --out desc.npy
uv run $S/frame_descriptors.py --diff desc.npy 51.2 53.0          # visible difference of a cut, 0-255
```

- `gaze.json` has, every 0.1 s, head turn (`yaw`), looking down (`pitch`, above 0.40 is reading), eye opening (`eo`, under 0.26 is a blink or eyes down), mouth opening (`mo`), and nose position. Use it to shortlist; **then look at a cropped face every 0.5 s of the shortlist**, because the numbers let glances down, tilts and a hand at the hair through. `--contact` writes the extreme frames of each feature so you can calibrate the thresholds on that person first.
- `frame_descriptors.py` compares grayscale thumbnails of one region: calm frames 0.1 s apart score 1 to 3, 1 s apart 8 to 12; cuts a person accepted measured 4.8 to 10.6 and "jumps" 12 and above. Cap internal cuts around 9 and cut where the head is still.
- The full pipeline, the slow-motion table by stillness and the boomerang trick are in `replicate-style-in-concat/references/learnings.md` (2026-11-07).

## Scoring a replica against its reference

```bash
uv run $S/analyze.py all ~/concat-analysis/<name>/out.mp4 --out ~/concat-analysis/<name>/replica
uv run $S/compare.py ~/concat-analysis/<name>/ref ~/concat-analysis/<name>/replica \
    --ref-video REF.mp4 --result-video ~/concat-analysis/<name>/out.mp4
```

`compare.md` reports cuts found/missing/extra with timing error, pacing, loudness difference, music tempo and off-beat effects matched by kind and time. `side_by_side.jpg` puts reference frames above replica frames at matched cuts. Use it to drive iteration, and say plainly what it cannot judge (grade, typography taste, how effects *sound*).

## Checking the tools themselves

`uv run $S/selftest.py --work ~/concat-analysis/_selftest` builds a 10 s video with known cuts, whooshes, an impact and a 120 BPM tick, then asserts the analysis finds them. Run it after changing `analyze.py`.

## Known limits

- Dissolves are detected from sustained frame change; very slow fades and cross-dissolves between similar shots can be missed. Fast whip pans can read as two cuts.
- Cuts hidden under a flash or glitch effect can show as one boundary with a high score.
- Event timing resolution is about 12 ms (hop 512 at 22.05 kHz); labels are heuristic.
- Not implemented: effects separated from music (Demucs only splits voice from the rest; a zero-shot audio model such as CLAP could name effects better but weighs about 600 MB and was not tried), on-screen text OCR (read it from the contact sheets and a few full-size frames), per-effect identification (which Concat transition it is: see `distill-editing-style`), typewriter or other text animation detection (look at a few frames in a row).
- Cuts that change the picture but not the voice (a punch-in on the same take) are found by `shots` but are not in the audio alignment; check the shot list against the segments.

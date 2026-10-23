---
name: analyze-reference-video
description: Turn a video into data and images Claude can actually read - cut times, transition strips, one frame per shot, loudness, spectrograms, a timeline of sound effects (hits, whooshes, risers), the music beat grid, and how sound lines up with cuts. Use this whenever the user hands over a reference or "edited" video and wants to understand or copy its editing style, asks how a video is cut or paced, wants to know where its sound effects and music sit, wants to find which parts of raw footage ended up in an edited video, or wants to check how close a replica in Concat is to its reference - even if they never say "analyze". Claude cannot watch or listen to a video directly; this skill is how it gets evidence.
---

# Analyzing a reference video

**Claude cannot watch or hear a video.** It can read images (frames, contact sheets, spectrograms) and data (JSON, text). This skill converts a video into exactly that. Everything it says about audio comes from detectors, not from listening, so treat sound labels as informed guesses and confirm the important ones on the spectrogram and against the frame at that moment.

Nothing is downloaded and nothing leaves the machine. Needs `ffmpeg`/`ffprobe` on PATH and `uv` (scripts declare their own dependencies and run on Python 3.10-3.12; `uv` fetches them).

## Run it

```bash
S=<repo>/.claude/skills/analyze-reference-video/scripts
uv run $S/analyze.py all  /path/to/video.mp4 --out ~/concat-analysis/<name>/ref
```

- Put output **under the home folder, never inside the repo**. Concat's MCP server only writes under the home folder, and analysis output is large.
- One step at a time: `probe | shots | frames | audio | sfx | report`. Re-run `report` after changing anything.
- `--cut 12` is the hard-cut sensitivity (frame-difference score 0-100). Lower it for soft footage with missed cuts, raise it for flashy footage with false cuts. `--gradual 3` controls dissolve detection.
- Long videos: `--max-shots`, `--max-strips`, `--spec-seconds` keep the number of images readable.

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
- Speech and loud music mask effects: expect missed whooshes under dialogue. If a spectrogram shows a clear bar or blob the list does not, the picture wins. There is no transcript or speech activity here; if the style depends on what is said, add a transcript another way and say so.

## Pairing raw footage with the edited cut

When the user supplies both the unedited footage and the edited video:

```bash
uv run $S/analyze.py shots EDITED.mp4 --out ~/concat-analysis/<name>/ref      # if not already done
uv run $S/align.py RAW.mp4 EDITED.mp4 --out ~/concat-analysis/<name>/ref
```

`alignment.json` gives, for every edited shot, the raw `raw_in`/`raw_out`, the playback `speed`, and a `confidence`. It matches 16x9 grey thumbnails, so flat colours, heavy crops, zooms and colour grades lower confidence. Check `medium`/`low` shots by eye against the contact sheet of both videos before trusting them. Footage that repeats (a static camera, a loop) can match the wrong occurrence; the `margin` field says how clearly the best match beat the runner-up.

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
- Not implemented: source separation (voice / music / effects stems), speech transcription, on-screen text OCR (read it from the contact sheets), per-effect identification (which Concat transition it is: see `distill-editing-style`).

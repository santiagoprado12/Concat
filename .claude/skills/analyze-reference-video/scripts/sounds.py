#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "librosa", "onnxruntime", "pillow"]
# ///
"""Find the sound effects in a video without the voice getting in the way.

  uv run sounds.py VIDEO --out DIR [--download] [--keep-vocals]

1. Separates the voice from everything else with Demucs (htdemucs, two stems). Needs `uv` to fetch demucs and
   PyTorch once (about 140 MB of wheels plus 84 MB of weights, both cached afterwards); about 0.45 s of CPU per
   second of audio.
2. Runs the event detector of analyze.py (hits, booms, whoosh/riser swells) on the voiceless stem.
3. Cuts a window around every event, runs YAMNet on it (AudioSet, 521 classes) and records whether the window
   sounds like a whoosh.

Writes DIR/sfx_stem.json (same schema as sfx.json, so `analyze.py report` picks it up) and DIR/stems/*.wav.

What this can and cannot say (measured on a 64 s reel with a music bed whose 46 effects were placed by hand):
- *When*: events of 15 dB or more found 42 of the 46 effects (91 %; chance, with the effects shifted at random,
  30 %, 95th percentile 61 %), but only 58 of the 78 events were effects. At the 20 dB that `analyze.py report`
  keeps: 36 of 46 found (78 %; chance 23 %, p95 46 %) and 42 of 45 events were effects. On the mixed track the
  voice produced 68 of 123 events that were not effects; on the stem the 20 dB list has 3 of 45.
- *What*: YAMNet barely names them. Its "Whoosh" score stays below 0.12 even on real whooshes: 4 of 11 slide-ins
  scored 0.03 or more and none of the 49 non-effect events did; pops, ticks, light swishes and short swishes never
  did. So `name_confidence` is "medium" only when the score is 0.03 or more (no false ones in that reel, about a
  third of the real ones), otherwise "low" and the name is just the shape label; `yamnet_top` is a hint.
- Demucs leaks a little: dings and pops can survive in the voice stem, and some voice in the other stem.
The models (YAMNet 16 MB, Apache-2.0) are fetched only with --download; ask the user first.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from models import ensure

HERE = Path(__file__).resolve().parent
WHOOSH = "Whoosh, swoosh, swish"
WHOOSH_MIN = 0.03  # YAMNet "Whoosh" score above everything a non-effect event reached (max 0.02) in the test reel
PRE, POST = 0.10, 0.60  # window around an event, seconds


def separate(video: Path, out: Path, device: str) -> tuple[Path, Path]:
    """Run Demucs through uv in its own environment (Python 3.12 has torch wheels) and return (vocals, rest)."""
    stems = out / "stems"
    voc, rest = stems / "vocals.wav", stems / "no_vocals.wav"
    if rest.exists():  # vocals.wav is deleted after a run, so the voiceless stem alone marks a finished separation
        return voc, rest
    stems.mkdir(parents=True, exist_ok=True)
    mix = stems / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", "44100", str(mix)],
                   check=True)
    if not mix.exists() or mix.stat().st_size < 1000:
        sys.exit("the video has no audio track")
    cmd = ["uv", "run", "--python", "3.12", "--with", "demucs", "--with", "soundfile", "python", "-m", "demucs",
           "--two-stems", "vocals", "-d", device, "-n", "htdemucs", "-o", str(stems / "demucs"), str(mix)]
    print("separating voice (first run downloads PyTorch and 84 MB of weights)...")
    subprocess.run(cmd, check=True)
    made = stems / "demucs" / "htdemucs" / "mix"
    (made / "vocals.wav").replace(voc)
    (made / "no_vocals.wav").replace(rest)
    mix.unlink(missing_ok=True)
    return voc, rest


def load_16k(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def tag_events(events: list[dict], y: np.ndarray, model: Path, classes: Path) -> None:
    import onnxruntime as ort
    names = [r[2] for r in csv.reader(open(classes))][1:]
    w = names.index(WHOOSH)
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    for e in events:
        t0 = e.get("start", e["time"]) - PRE
        t1 = max(e.get("end", e["time"]), e["time"]) + POST
        a, b = int(max(t0, 0) * 16000), int(t1 * 16000)
        crop = y[a:b]
        crop = np.concatenate([crop, np.zeros(max(16000 - len(crop), 0), np.float32)])
        scores = sess.run(None, {inp: crop})[0].max(axis=0)
        top = np.argsort(scores)[::-1][:3]
        e["yamnet_whoosh"] = round(float(scores[w]), 2)
        e["yamnet_top"] = [[names[j], round(float(scores[j]), 2)] for j in top if scores[j] >= 0.05]
        if e["yamnet_whoosh"] >= WHOOSH_MIN:
            e["name"], e["name_confidence"] = "whoosh/swish", "medium"
        else:
            e["name"], e["name_confidence"] = e["label"], "low"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="analysis directory (the one analyze.py writes to)")
    ap.add_argument("--device", default="cpu", help="demucs device: cpu, mps or cuda")
    ap.add_argument("--min-event-db", type=float, default=8.0)
    ap.add_argument("--download", action="store_true", help="fetch the YAMNet model if missing (ask the user first)")
    ap.add_argument("--no-yamnet", action="store_true", help="skip the naming step (no model needed)")
    ap.add_argument("--keep-vocals", action="store_true", help="keep stems/vocals.wav (deleted by default: it is big)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    video = a.video.expanduser().resolve()
    if not video.exists():
        sys.exit(f"no such file: {video}")
    if not a.no_yamnet:
        model, classes = ensure("yamnet", a.download), ensure("yamnet_classes", a.download)  # fail before the slow part

    voc, rest = separate(video, a.out, a.device)

    # reuse the event detector of analyze.py on the voiceless stem, in a scratch directory
    sys.path.insert(0, str(HERE))
    import analyze
    work = a.out / "stems" / "work"
    work.mkdir(exist_ok=True)
    wav = work / "audio.wav"
    wav.unlink(missing_ok=True)
    wav.symlink_to(rest)
    data = analyze.cmd_sfx(video, work, a.min_event_db)
    events = data.get("events", [])
    for e in events:  # the voice is gone, so the speech filters of the mixed-track analysis do not apply
        e["in_speech"], e["after_silence"] = False, False

    if not a.no_yamnet:
        tag_events(events, load_16k(rest), model, classes)
    data.update({"source": "no_vocals stem (Demucs htdemucs)",
                 "caveat": ("Events come from the voiceless stem, so the voice no longer triggers them. Timing is "
                            "reliable; names are not: only name_confidence 'medium' means YAMNet also heard a "
                            "whoosh. Confirm on the spectrogram and by what the frame shows at that moment.")})
    (a.out / "sfx_stem.json").write_text(json.dumps(
        data, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    if not a.keep_vocals:
        voc.unlink(missing_ok=True)
    named = sum(1 for e in events if e.get("name_confidence") == "medium")
    print(f"{len(events)} events on the voiceless stem, {named} recognised as whoosh/swish "
          f"-> {a.out / 'sfx_stem.json'}")


if __name__ == "__main__":
    main()

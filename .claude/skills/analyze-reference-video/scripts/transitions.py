#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "onnxruntime", "pillow"]
# ///
"""Find hard cuts and gradual transitions (dissolves, fades, wipes) with TransNet V2.

  uv run transitions.py VIDEO --out DIR [--thr 0.5] [--shots DIR/shots.json] [--download]

Every frame is scaled to 48x27 RGB; windows of 100 frames slide by 50 with 25 frames of context on each side (the
upstream recipe). `cuts` are peaks of the single-frame head, `graduals` are runs of 3 or more frames where the
many-hot head is above --thr and that are not just a cut. With --shots (the output of `analyze.py shots`) every
gradual is also cross-checked against the frame-difference detector, and a strip of frames is written per gradual
so the kind (dissolve, fade, wipe, flash) can be read off the picture.

Writes DIR/transitions.json and DIR/transitions/gradual_NN.jpg. The model (31 MB, MIT) is fetched only with --download.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from models import ensure


def frame_rate(video: Path) -> float:
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "stream=r_frame_rate", "-of", "json", str(video)],
                                   capture_output=True, text=True).stdout)
    n, d = pr["streams"][0]["r_frame_rate"].split("/")
    return float(n) / float(d)


def predict(video: Path, model: Path) -> tuple[np.ndarray, np.ndarray, float]:
    import onnxruntime as ort
    fps = frame_rate(video)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf", "scale=48:27:flags=bilinear",
                          "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 27, 48, 3)
    total = len(frames)
    if total == 0:
        raise SystemExit("no video frames decoded")
    pad_end = 25 + (50 - total % 50 if total % 50 else 50)
    padded = np.concatenate([np.repeat(frames[:1], 25, 0), frames, np.repeat(frames[-1:], pad_end, 0)])
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    one, many = [], []
    for s in range(0, len(padded) - 100 + 1, 50):
        o1, o2 = sess.run(None, {name: padded[s:s + 100][None].astype(np.float32)})
        one.append(o1[0, 25:75, 0])
        many.append(o2[0, 25:75, 0])
    return np.concatenate(one)[:total], np.concatenate(many)[:total], fps


def find(one: np.ndarray, many: np.ndarray, fps: float, thr: float) -> tuple[list[dict], list[dict]]:
    total = len(one)
    cuts = []
    for i in range(total):
        if one[i] > thr and (i == 0 or one[i] >= one[i - 1]) and (i == total - 1 or one[i] >= one[i + 1]):
            # the model marks the last frame of the outgoing shot; the new shot starts on the next frame
            cuts.append({"time": round((i + 1) / fps, 3), "frame": i + 1, "score": round(float(one[i]), 2)})
    cut_frames = [c["frame"] for c in cuts]
    grads, i = [], 0
    while i < total:
        if many[i] <= thr:
            i += 1
            continue
        j = i
        while j < total and many[j] > thr:
            j += 1
        just_a_cut = (j - i) <= 3 and any(i - 1 <= k <= j for k in cut_frames)
        if j - i >= 3 and not just_a_cut:
            grads.append({"start": round(i / fps, 3), "end": round(j / fps, 3), "frames": j - i,
                          "duration_s": round((j - i) / fps, 2), "peak": round(float(many[i:j].max()), 2)})
        i = j
    return cuts, grads


def strip(video: Path, start: float, end: float, dest: Path, width: int = 240) -> None:
    from PIL import Image
    pad = max(0.1, (end - start) * 0.15)
    t0, t1 = max(0.0, start - pad), end + pad
    tiles = []
    for k in range(6):
        t = t0 + (t1 - t0) * k / 5
        tmp = dest.with_suffix(f".{k}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={width}:-2", str(tmp)], check=False)
        if tmp.exists():
            tiles.append((Image.open(tmp).convert("RGB"), t))
    if not tiles:
        return
    w, h = tiles[0][0].size
    sheet = Image.new("RGB", (w * len(tiles), h), "black")
    for k, (im, _) in enumerate(tiles):
        sheet.paste(im, (k * w, 0))
    sheet.save(dest, quality=82)
    for k in range(6):
        dest.with_suffix(f".{k}.jpg").unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="output directory (outside the repo)")
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--shots", type=Path, help="shots.json from analyze.py shots, to cross-check")
    ap.add_argument("--model", type=Path, help="transnetv2.onnx (default: ~/concat-analysis/models)")
    ap.add_argument("--download", action="store_true", help="fetch the model if missing (ask the user first)")
    ap.add_argument("--max-strips", type=int, default=24)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    video = a.video.expanduser().resolve()
    one, many, fps = predict(video, ensure("transnetv2", a.download, a.model))
    cuts, grads = find(one, many, fps, a.thr)

    result: dict = {"model": "TransNet V2", "fps": fps, "frames": len(one), "threshold": a.thr,
                    "cuts": cuts, "graduals": grads,
                    "caveat": ("A learned detector, not ground truth: dissolves of similar shots, whip pans and "
                               "flashes can be reported as a cut or missed. Read the strips for the kind.")}
    if a.shots and a.shots.exists():
        ref = json.loads(a.shots.read_text())
        ref_t = [b["time"] for b in ref.get("boundaries", [])]
        for c in cuts:
            c["also_in_scdet"] = any(abs(c["time"] - t) <= 0.1 for t in ref_t)
        for g in grads:
            g["scdet_boundaries_inside"] = sum(1 for t in ref_t if g["start"] - 0.1 <= t <= g["end"] + 0.1)
        result["agreement"] = {
            "cuts_confirmed_by_scdet": sum(1 for c in cuts if c.get("also_in_scdet")),
            "cuts_only_transnet": [c["time"] for c in cuts if not c.get("also_in_scdet")],
            "scdet_only": [t for t in ref_t if not any(abs(t - c["time"]) <= 0.1 for c in cuts)
                           and not any(g["start"] - 0.1 <= t <= g["end"] + 0.1 for g in grads)],
        }
    sdir = a.out / "transitions"
    sdir.mkdir(exist_ok=True)
    for n, g in enumerate(grads[:a.max_strips], 1):
        dest = sdir / f"gradual_{n:02d}.jpg"
        strip(video, g["start"], g["end"], dest)
        g["strip"] = str(dest)
    (a.out / "transitions.json").write_text(json.dumps(result, indent=1))
    print(f"{len(one)} frames @ {fps:.2f} fps: {len(cuts)} cuts, {len(grads)} gradual transitions "
          f"-> {a.out / 'transitions.json'}")
    if "agreement" in result:
        print(json.dumps(result["agreement"]))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["mediapipe==0.10.14", "opencv-python-headless", "numpy"]
# ///
"""Head pose, eye opening and mouth opening of one person over time, from a video.

  uv run --python 3.12 face_gaze.py VIDEO --out gaze.json [--crop X:Y:W:H] [--fps 10]

Why it exists: when a person has to look "attentive" while someone else talks (a listener in a
split-screen reel, a reaction cutaway) you must find the seconds of raw footage where they look at the
camera or at the other person, and not down at a script or phone, leaning, or touching their face.
Eyeballing 4 minutes of footage is slow; these numbers shortlist it, and you then LOOK at one cropped
frame every 0.5 s of the shortlist (the numbers alone were not enough: see learnings.md, 2026-11-07).

--crop is X:Y:W:H as fractions of the (already rotated) frame, to keep one person in view; default is
the whole frame. One face per sample (the first one MediaPipe finds in the crop).

Output: a list of {t, ok, yaw, pitch, eo, mo, cx, cy} per sample (ok false when no face):
  yaw    nose offset from the eye midpoint over the eye distance: 0 facing the camera, + toward the
         image's right, - toward its left (head turned; about +-0.3 is a clear turn)
  pitch  nose-to-eye-line over eye-to-chin: about 0.33-0.37 level, above 0.40 looking down (reading)
  eo     eye opening over eye width: under about 0.26 is a blink or eyes down
  mo     lip gap over mouth width: above about 0.10 is a mouth open (talking, laughing)
  cx, cy nose position as a fraction of the crop (a big change in cy is a lean or a bow)
Thresholds are for a person standing about 2 m from a phone camera; check them on a few frames first
(`--contact` writes a contact sheet of the extremes of each feature so you can calibrate).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def probe_size(video: Path) -> tuple[int, int]:
    """Frame size AFTER rotation metadata is applied (ffmpeg autorotates when it decodes)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    w, h = s["width"], s["height"]
    rot = next((abs(int(d["rotation"])) for d in s.get("side_data_list", []) if "rotation" in d), 0)
    return (h, w) if rot in (90, 270) else (w, h)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--crop", default="0:0:1:1", help="X:Y:W:H as fractions of the frame")
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--contact", type=Path, help="write a contact sheet of feature extremes (needs pillow)")
    a = ap.parse_args()

    import mediapipe as mp  # imported late so --help works without the wheel

    fw, fh = probe_size(a.video)
    x, y, w, h = (float(v) for v in a.crop.split(":"))
    cw, ch = int(fw * w) // 2 * 2, int(fh * h) // 2 * 2
    cx0, cy0 = int(fw * x), int(fh * y)
    cmd = ["ffmpeg", "-v", "error", "-i", str(a.video), "-vf", f"fps={a.fps},crop={cw}:{ch}:{cx0}:{cy0}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True,
                                           min_detection_confidence=0.5, min_tracking_confidence=0.5)
    rows, frames, i = [], [], 0
    while True:
        buf = proc.stdout.read(cw * ch * 3)
        if len(buf) < cw * ch * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(ch, cw, 3)
        t = round(i / a.fps, 3)
        i += 1
        res = mesh.process(img)
        if a.contact:
            frames.append(img[::4, ::4].copy())
        if not res.multi_face_landmarks:
            rows.append({"t": t, "ok": False})
            continue
        L = res.multi_face_landmarks[0].landmark

        def P(n):
            return L[n].x * cw, L[n].y * ch

        nose, ro, lo, ri, li, chin = P(1), P(33), P(263), P(133), P(362), P(152)
        ru, rl, lu, ll = P(159), P(145), P(386), P(374)
        mu, ml, mr, mL = P(13), P(14), P(61), P(291)
        eye_dist = max(lo[0] - ro[0], 1e-3)
        mid = ((ro[0] + lo[0]) / 2, (ro[1] + lo[1]) / 2)
        eo = np.mean([(rl[1] - ru[1]) / max(ri[0] - ro[0], 1e-3), (ll[1] - lu[1]) / max(lo[0] - li[0], 1e-3)])
        rows.append({"t": t, "ok": True,
                     "yaw": round(float((nose[0] - mid[0]) / eye_dist), 3),
                     "pitch": round(float((nose[1] - mid[1]) / max(chin[1] - mid[1], 1)), 3),
                     "eo": round(float(eo), 3),
                     "mo": round(float((ml[1] - mu[1]) / max(mL[0] - mr[0], 1e-3)), 3),
                     "cx": round(float(nose[0] / cw), 3), "cy": round(float(nose[1] / ch), 3)})
    a.out.write_text(json.dumps(rows))
    print(f"{len(rows)} samples, face found in {sum(r['ok'] for r in rows)}", file=sys.stderr)

    if a.contact:
        from PIL import Image, ImageDraw
        ok = [(k, r) for k, r in enumerate(rows) if r["ok"]]
        tiles = []
        for key in ("yaw", "pitch", "eo", "mo"):
            order = sorted(ok, key=lambda kr: kr[1][key])
            tiles += [(f"{key} low", order[0]), (f"{key} low", order[len(order) // 20]),
                      (f"{key} high", order[-1 - len(order) // 20]), (f"{key} high", order[-1])]
        th, tw = frames[0].shape[:2]
        sheet = Image.new("RGB", (tw * 4, (th + 12) * 4), "white")
        d = ImageDraw.Draw(sheet)
        for n, (label, (k, r)) in enumerate(tiles):
            X, Y = (n % 4) * tw, (n // 4) * (th + 12)
            sheet.paste(Image.fromarray(frames[k]), (X, Y + 12))
            d.text((X + 2, Y), f"{label} t={r['t']:.1f}", fill="black")
        sheet.save(a.contact)


if __name__ == "__main__":
    main()

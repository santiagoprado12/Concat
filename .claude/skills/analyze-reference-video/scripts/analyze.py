#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["numpy", "librosa", "pillow"]
# ///
"""Turn a video into things Claude can read: JSON data, contact sheets, spectrograms.

Claude cannot watch or hear a video. This script extracts what it can inspect:
cut times, transition strips, one frame per shot, a loudness curve, a spectrogram,
and a timeline of detected sound events (hits, whooshes, risers) plus the music beat grid.

Usage:
  uv run analyze.py all VIDEO --out DIR          # everything below, then the report
  uv run analyze.py probe|shots|frames|audio|sfx|report VIDEO --out DIR

Requires ffmpeg and ffprobe on PATH. No model is downloaded and nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
HOP = 512


# --------------------------------------------------------------------------- helpers

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def need(tool: str) -> None:
    if run(["which", tool], check=False).returncode != 0:
        sys.exit(f"{tool} not found on PATH (macOS: brew install ffmpeg)")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False,
                               default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(f"wrote {path}")


# --------------------------------------------------------------------------- probe

def cmd_probe(video: Path, out: Path) -> dict:
    need("ffprobe")
    p = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)])
    raw = json.loads(p.stdout)
    v = next((s for s in raw["streams"] if s["codec_type"] == "video"), {})
    a = [s for s in raw["streams"] if s["codec_type"] == "audio"]
    num, _, den = v.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    info = {
        "file": str(video),
        "duration": float(raw["format"].get("duration", 0)),
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": round(fps, 3),
        "video_codec": v.get("codec_name"),
        "audio_tracks": [{"codec": s.get("codec_name"), "channels": s.get("channels"),
                          "sample_rate": s.get("sample_rate")} for s in a],
        "has_audio": bool(a),
    }
    write_json(out / "probe.json", info)
    return info


# --------------------------------------------------------------------------- shots

def scene_scores(video: Path) -> list[tuple[float, float]]:
    """(time, score) for every frame. scdet scores are 0-100 mean frame difference."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an",
           "-vf", "scale=320:-2,scdet=threshold=100,metadata=mode=print:file=-",
           "-f", "null", "-"]
    p = run(cmd)
    out: list[tuple[float, float]] = []
    t = None
    for line in p.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.match(r"lavfi\.scd\.score=([\d.]+)", line)
        if m and t is not None:
            out.append((t, float(m.group(1))))
    return out


def cmd_shots(video: Path, out: Path, cut: float, soft: float) -> dict:
    need("ffmpeg")
    info = read_json(out / "probe.json") or cmd_probe(video, out)
    scores = scene_scores(video)
    dur = info["duration"]
    boundaries: list[dict] = []
    i = 0
    while i < len(scores):
        t, s = scores[i]
        if s >= cut:
            boundaries.append({"time": round(t, 3), "score": round(s, 1), "kind": "cut"})
            i += 1
            continue
        if s >= soft:
            j = i
            total = 0.0
            while j < len(scores) and scores[j][1] >= soft and scores[j][1] < cut:
                total += scores[j][1]
                j += 1
            if j - i >= 4 and total >= cut * 1.5:
                mid = (scores[i][0] + scores[j - 1][0]) / 2
                boundaries.append({"time": round(mid, 3), "score": round(total, 1),
                                   "kind": "gradual",
                                   "span": round(scores[j - 1][0] - scores[i][0], 3)})
            i = j
            continue
        i += 1
    edges = [0.0] + [b["time"] for b in boundaries] + [dur]
    shots = [{"index": k, "start": round(edges[k], 3), "end": round(edges[k + 1], 3),
              "duration": round(edges[k + 1] - edges[k], 3)} for k in range(len(edges) - 1)]
    durs = np.array([s["duration"] for s in shots])
    stats = {
        "shots": len(shots),
        "avg_shot_length": round(float(durs.mean()), 3),
        "median_shot_length": round(float(np.median(durs)), 3),
        "shortest": round(float(durs.min()), 3),
        "longest": round(float(durs.max()), 3),
        "cuts_per_minute": round(len(boundaries) / (dur / 60), 1) if dur else 0,
    }
    data = {"thresholds": {"cut": cut, "gradual_frame": soft}, "boundaries": boundaries,
            "shots": shots, "stats": stats}
    write_json(out / "shots.json", data)
    print(json.dumps(stats))
    return data


# --------------------------------------------------------------------------- frames

def grab(video: Path, t: float, dest: Path, width: int) -> bool:
    r = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(t, 0):.3f}", "-i", str(video),
             "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)], check=False)
    return r.returncode == 0 and dest.exists()


def sheet(images: list[tuple[Path, str]], dest: Path, cols: int) -> None:
    from PIL import Image, ImageDraw
    tiles = []
    for path, label in images:
        im = Image.open(path).convert("RGB")
        ImageDraw.Draw(im).rectangle([0, 0, 8 * len(label) + 6, 14], fill=(0, 0, 0))
        ImageDraw.Draw(im).text((3, 1), label, fill=(255, 255, 0))
        tiles.append(im)
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    canvas = Image.new("RGB", (cols * w, rows * h), (20, 20, 20))
    for k, im in enumerate(tiles):
        canvas.paste(im.resize((w, h)), ((k % cols) * w, (k // cols) * h))
    canvas.save(dest, quality=88)


def cmd_frames(video: Path, out: Path, width: int, max_shots: int, max_strips: int) -> None:
    need("ffmpeg")
    data = read_json(out / "shots.json")
    if not data:
        data = cmd_shots(video, out, 12.0, 3.0)
    fdir = out / "frames"
    fdir.mkdir(exist_ok=True)
    shots = data["shots"]
    step = max(1, math.ceil(len(shots) / max_shots))
    picks = shots[::step]
    items: list[tuple[Path, str]] = []
    for s in picks:
        mid = (s["start"] + s["end"]) / 2
        p = fdir / f"shot_{s['index']:03d}.jpg"
        if grab(video, mid, p, width):
            items.append((p, f"#{s['index']} {s['start']:.1f}s"))
    per_sheet = 12
    for n in range(0, len(items), per_sheet):
        sheet(items[n:n + per_sheet], out / f"contact_{n // per_sheet + 1:02d}.jpg", 4)
    print(f"{len(items)} shot frames in {math.ceil(len(items) / per_sheet)} contact sheet(s)")

    # transition strips: 6 frames around each boundary, to be classified by eye
    tdir = out / "transitions"
    tdir.mkdir(exist_ok=True)
    fps = (read_json(out / "probe.json") or {}).get("fps") or 25
    gap = 1 / fps
    strips = data["boundaries"][:max_strips]
    for k, b in enumerate(strips):
        span = max(b.get("span", 0), 0.0)
        times = [b["time"] + (n - 2.5) * (gap + span / 3) for n in range(6)]
        parts = []
        for n, t in enumerate(times):
            p = tdir / f"_{k:03d}_{n}.jpg"
            if grab(video, t, p, width // 2):
                parts.append((p, f"{t - b['time']:+.2f}s"))
        if parts:
            sheet(parts, tdir / f"boundary_{k:03d}_{b['time']:.2f}s_{b['kind']}.jpg", 6)
        for p, _ in parts:
            p.unlink(missing_ok=True)
    print(f"{len(strips)} transition strips in {tdir}")


# --------------------------------------------------------------------------- audio

def cmd_audio(video: Path, out: Path, silence_db: float, spec_chunk: float) -> dict:
    need("ffmpeg")
    info = read_json(out / "probe.json") or cmd_probe(video, out)
    if not info["has_audio"]:
        data = {"has_audio": False}
        write_json(out / "audio.json", data)
        return data
    wav = out / "audio.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(SR), str(wav)])

    # loudness (EBU R128): momentary curve + integrated summary
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav),
             "-af", "ebur128=peak=true", "-f", "null", "-"], check=False)
    curve = []
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:\S+\s+LUFS\s+M:\s*(-?[\d.inf]+)", p.stderr):
        try:
            curve.append([float(m.group(1)), float(m.group(2))])
        except ValueError:
            pass
    summ = {}
    tail = p.stderr.split("Summary:")[-1]
    for key, pat in (("integrated_lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+([\d.]+) LU"),
                     ("true_peak_db", r"Peak:\s+(-?[\d.]+) dBFS")):
        m = re.search(pat, tail)
        if m:
            summ[key] = float(m.group(1))

    # silence
    s = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav),
             "-af", f"silencedetect=noise={silence_db}dB:d=0.3", "-f", "null", "-"], check=False)
    silences, start = [], None
    for line in s.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(float(m.group(1)), 0)
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            silences.append([round(start, 3), round(float(m.group(1)), 3)])
            start = None

    # spectrograms, chunked so detail survives (Read downsizes big images)
    dur = info["duration"]
    n = max(1, math.ceil(dur / spec_chunk))
    for k in range(min(n, 12)):
        t0 = k * spec_chunk
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(spec_chunk), "-i", str(wav),
             "-lavfi", "showspectrumpic=s=1400x420:legend=1:scale=log:fscale=log",
             str(out / f"spectrogram_{k + 1:02d}.png")], check=False)
    data = {"has_audio": True, **summ, "loudness_curve_100ms": curve[::1], "silences": silences,
            "spectrogram_chunk_seconds": spec_chunk}
    write_json(out / "audio.json", data)
    print(json.dumps(summ), f"{len(silences)} silent span(s)")
    return data


# --------------------------------------------------------------------------- sfx

def band_env(S: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    idx = (freqs >= lo) & (freqs < hi)
    return np.sqrt((S[idx] ** 2).mean(axis=0) + 1e-12)


def to_db(x: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.maximum(x, 1e-9))


def label_hit(low_ratio: float, centroid: float, decay: float) -> str:
    if decay < 0.12 and centroid > 2500:
        return "click_pop"
    if low_ratio > 0.45 and decay >= 0.15:
        return "impact_boom"
    if low_ratio > 0.25:
        return "hit_thump"
    return "transient"


def cmd_sfx(video: Path, out: Path, min_db: float) -> dict:
    import librosa
    wav = out / "audio.wav"
    if not wav.exists():
        cmd_audio(video, out, -35.0, 30.0)
    if not wav.exists():
        write_json(out / "sfx.json", {"has_audio": False})
        return {}
    y, _ = librosa.load(str(wav), sr=SR, mono=True)
    dur = len(y) / SR
    # percussive part keeps sustained speech/music out of the transient detector
    harm, perc = librosa.effects.hpss(y)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    Sp = np.abs(librosa.stft(perc, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    times = librosa.frames_to_time(np.arange(S.shape[1]), sr=SR, hop_length=HOP)
    events: list[dict] = []

    # 1) hits: sharp onsets on the percussive stem
    oenv = librosa.onset.onset_strength(S=librosa.amplitude_to_db(Sp), sr=SR, hop_length=HOP)
    on = librosa.onset.onset_detect(onset_envelope=oenv, sr=SR, hop_length=HOP,
                                    backtrack=False, delta=0.25, wait=4)
    total = np.sqrt((Sp ** 2).sum(axis=0) + 1e-12)
    total_db = to_db(total)
    floor = np.median(total_db)
    for f in on:
        a, b = f, min(f + int(0.8 * SR / HOP), len(total_db))
        peak = a + int(np.argmax(total_db[a:b]))
        peak_db = float(total_db[peak])
        if peak_db - floor < min_db:
            continue
        seg = Sp[:, peak]
        low = float((seg[freqs < 200] ** 2).sum() / ((seg ** 2).sum() + 1e-12))
        cent = float((freqs * seg).sum() / (seg.sum() + 1e-12))
        tail = np.where(total_db[peak:b] < peak_db - 20)[0]
        decay = float(tail[0] * HOP / SR) if len(tail) else float((b - peak) * HOP / SR)
        events.append({"time": round(float(times[f]), 3), "label": label_hit(low, cent, decay),
                       "strength_db": round(peak_db - floor, 1), "centroid_hz": round(cent),
                       "low_ratio": round(low, 2), "decay_s": round(decay, 2)})

    # 1b) low-frequency jumps: booms and kicks are mostly sine-like and land in the harmonic stem
    lo = to_db(band_env(S, freqs, 25, 160))
    pre_a, pre_b = int(0.20 * SR / HOP), max(1, int(0.04 * SR / HOP))
    last = -999
    for f in range(pre_a + 1, len(lo) - 1):
        base = float(lo[f - pre_a:f - pre_b].min())
        if lo[f] - base < 12 or lo[f] < lo[f - 1] or lo[f] < lo[f + 1] or f - last < int(0.08 * SR / HOP):
            continue
        last = f
        b = min(f + int(1.5 * SR / HOP), len(lo))
        tail = np.where(lo[f:b] < lo[f] - 20)[0]
        decay = float(tail[0] * HOP / SR) if len(tail) else float((b - f) * HOP / SR)
        events.append({"time": round(float(times[f]), 3),
                       "label": "impact_boom" if decay >= 0.25 else "hit_thump",
                       "strength_db": round(float(lo[f] - base), 1), "centroid_hz": 0,
                       "low_ratio": 1.0, "decay_s": round(decay, 2), "detector": "low_band"})
    events.sort(key=lambda e: e["time"])
    merged: list[dict] = []
    for e in events:  # the same sound found by two detectors: keep the stronger, prefer the low-band label
        if merged and abs(e["time"] - merged[-1]["time"]) < 0.08:
            if e.get("detector") == "low_band" or e["strength_db"] > merged[-1]["strength_db"]:
                merged[-1] = e
            continue
        merged.append(e)
    events = merged

    # 2) swells: whooshes and risers are noise-like bumps with no sharp onset
    hf = to_db(band_env(S, freqs, 2500, 10000))
    k = max(1, int(0.08 * SR / HOP))
    hf_s = np.convolve(hf, np.ones(k) / k, mode="same")
    bg = np.convolve(hf_s, np.ones(int(3 * SR / HOP)) / int(3 * SR / HOP), mode="same")
    flat = librosa.feature.spectral_flatness(S=S)[0]
    excess = hf_s - np.minimum(bg, np.median(hf_s) + 6)
    above = excess > 5
    f0 = 0
    while f0 < len(above):
        if not above[f0]:
            f0 += 1
            continue
        f1 = f0
        while f1 < len(above) and above[f1]:
            f1 += 1
        width = (f1 - f0) * HOP / SR
        if 0.2 <= width <= 6.0 and float(np.mean(flat[f0:f1])) > 0.02:
            pk = f0 + int(np.argmax(hf_s[f0:f1]))
            rise = (pk - f0) * HOP / SR
            fall = (f1 - pk) * HOP / SR
            label = "riser" if width > 1.2 and rise > 2.5 * fall else (
                "whoosh_swell" if width <= 1.8 else "ambience_or_swell")
            events.append({"time": round(float(times[pk]), 3), "label": label,
                           "start": round(float(times[f0]), 3), "end": round(float(times[f1 - 1]), 3),
                           "strength_db": round(float(excess[pk]), 1), "rise_s": round(rise, 2),
                           "fall_s": round(fall, 2), "flatness": round(float(np.mean(flat[f0:f1])), 3)})
        f0 = f1

    events.sort(key=lambda e: e["time"])
    # 3) music grid
    tempo, beats = librosa.beat.beat_track(y=harm + perc, sr=SR, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_t = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)
    ibi = np.diff(beat_t)
    regular = float(1 - (ibi.std() / ibi.mean())) if len(ibi) > 3 and ibi.mean() > 0 else 0.0
    data = {
        "has_audio": True,
        "caveat": ("Heuristic detectors on the mixed track. Speech and music mask effects; labels are guesses. "
                   "Confirm important events on the spectrogram image and by what the frame shows at that time."),
        "events": events,
        "music": {"bpm": round(tempo, 1), "beat_regularity": round(max(regular, 0), 2),
                  "beats": [round(float(b), 3) for b in beat_t]},
        "duration": round(dur, 2),
    }
    write_json(out / "sfx.json", data)
    from collections import Counter
    print(dict(Counter(e["label"] for e in events)), f"bpm~{tempo:.0f}")
    return data


# --------------------------------------------------------------------------- report

def nearest(t: float, ref: list[float]) -> tuple[float, float]:
    if not ref:
        return (math.inf, math.nan)
    d = min(ref, key=lambda r: abs(r - t))
    return (abs(d - t), t - d)


def cmd_report(out: Path) -> dict:
    probe, shots = read_json(out / "probe.json"), read_json(out / "shots.json")
    audio, sfx = read_json(out / "audio.json"), read_json(out / "sfx.json")
    cuts = [b["time"] for b in shots.get("boundaries", [])]
    events = sfx.get("events", [])
    corr: dict = {}
    if cuts and events:
        # event time minus cut time, for events within 0.6 s of a cut
        # offsets are event minus cut: negative = the sound leads the cut. Swells also report their end.
        by_label: dict[str, list[float]] = {}
        ends: dict[str, list[float]] = {}
        for e in events:
            dist, off = nearest(e["time"], cuts)
            if dist <= 0.6:
                by_label.setdefault(e["label"], []).append(off)
                if "end" in e:
                    ends.setdefault(e["label"], []).append(e["end"] - min(cuts, key=lambda c: abs(c - e["time"])))
        corr["sfx_near_cuts"] = {
            lbl: {"count": len(v), "median_offset_s": round(float(np.median(v)), 3),
                  "spread_s": round(float(np.std(v)), 3),
                  **({"median_end_offset_s": round(float(np.median(ends[lbl])), 3)} if lbl in ends else {})}
            for lbl, v in by_label.items()}
        covered = sum(1 for c in cuts if any(abs(e["time"] - c) <= 0.6 or
                                             (e.get("start", 9e9) - 0.2 <= c <= e.get("end", -1) + 0.2)
                                             for e in events))
        corr["fraction_of_cuts_with_sfx"] = round(covered / len(cuts), 2)
    beats = sfx.get("music", {}).get("beats", [])
    for e in events:  # an impact that is not on the beat grid is far more likely to be a placed effect
        e["on_beat"] = bool(beats) and nearest(e["time"], beats)[0] <= 0.05
    if cuts and beats:
        d = [nearest(c, beats)[0] for c in cuts]
        corr["cuts_within_60ms_of_beat"] = round(sum(1 for x in d if x <= 0.06) / len(d), 2)
        corr["median_cut_to_beat_s"] = round(float(np.median(d)), 3)
    report = {"probe": probe, "pacing": shots.get("stats", {}), "boundaries": shots.get("boundaries", []),
              "loudness": {k: audio.get(k) for k in ("integrated_lufs", "lra", "true_peak_db")},
              "silences": audio.get("silences", []),
              "sfx_events": events, "music": {k: v for k, v in sfx.get("music", {}).items() if k != "beats"},
              "correlations": corr, "caveat": sfx.get("caveat", "")}
    write_json(out / "style-report.json", report)
    lines = [f"# Style report: {Path(probe.get('file', '?')).name}", "",
             f"{probe.get('width')}x{probe.get('height')} @ {probe.get('fps')} fps, {probe.get('duration'):.1f}s", "",
             "## Pacing", json.dumps(report["pacing"]), "", "## Loudness", json.dumps(report["loudness"]), "",
             "## Music", json.dumps(report["music"]), "", "## SFX / cut correlations", json.dumps(corr, indent=1), "",
             f"## SFX events ({len(events)})"]
    for e in events[:80]:
        lines.append(f"- {e['time']:.2f}s {e['label']} ({e.get('strength_db')} dB)")
    if len(events) > 80:
        lines.append(f"- ... {len(events) - 80} more in style-report.json")
    (out / "style-report.md").write_text("\n".join(lines))
    print(f"wrote {out / 'style-report.md'}")
    return report


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["all", "probe", "shots", "frames", "audio", "sfx", "report"])
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="output directory (outside the repo)")
    ap.add_argument("--cut", type=float, default=12.0, help="scdet score that counts as a hard cut")
    ap.add_argument("--gradual", type=float, default=3.0, help="per-frame score that starts a gradual change")
    ap.add_argument("--width", type=int, default=360, help="frame width in contact sheets")
    ap.add_argument("--max-shots", type=int, default=96)
    ap.add_argument("--max-strips", type=int, default=40)
    ap.add_argument("--silence-db", type=float, default=-35.0)
    ap.add_argument("--spec-seconds", type=float, default=30.0)
    ap.add_argument("--min-event-db", type=float, default=8.0, help="how far above the noise floor a hit must be")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    video = a.video.expanduser().resolve()
    if not video.exists():
        sys.exit(f"no such file: {video}")
    steps = {
        "probe": lambda: cmd_probe(video, a.out),
        "shots": lambda: cmd_shots(video, a.out, a.cut, a.gradual),
        "frames": lambda: cmd_frames(video, a.out, a.width, a.max_shots, a.max_strips),
        "audio": lambda: cmd_audio(video, a.out, a.silence_db, a.spec_seconds),
        "sfx": lambda: cmd_sfx(video, a.out, a.min_event_db),
        "report": lambda: cmd_report(a.out),
    }
    order = ["probe", "shots", "frames", "audio", "sfx", "report"] if a.command == "all" else [a.command]
    for name in order:
        print(f"== {name}")
        steps[name]()


if __name__ == "__main__":
    main()

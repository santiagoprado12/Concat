#!/usr/bin/env python3
"""Download a reference video from a link (Instagram, TikTok, YouTube) with yt-dlp, for study only.

  python3 fetch.py URL [URL ...] [--out ~/concat-analysis/refs] [--cookies-from-browser chrome]

For every link it writes, under --out:
  <id>/video.mp4     the video with its sound (merged by ffmpeg)
  <id>/source.json   link, author, caption, hashtags, duration, size, likes, whether it has audio

and prints one line per video: the path to give to `analyze-reference-video`.

Needs `yt-dlp` and `ffmpeg` on PATH (macOS: brew install yt-dlp ffmpeg). Standard library only. Nothing is sent
anywhere but the site's own servers. Cookies are never used unless --cookies-from-browser is passed on purpose.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HOSTS = ("instagram.com", "tiktok.com", "youtube.com", "youtu.be")


def fail(msg: str) -> None:
    sys.exit(f"error: {msg}")


def check_url(url: str, allow_any: bool) -> None:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https") or not host:
        fail(f"not a web link: {url}")
    if not allow_any and not any(host == h or host.endswith("." + h) for h in HOSTS):
        fail(f"{host} is not one of {', '.join(HOSTS)}; pass --any-site if the user asked for it")


def fetch(url: str, out: Path, cookies: str | None) -> list[Path]:
    cmd = ["yt-dlp", "--no-warnings", "--write-info-json", "--no-write-comments",
           "--merge-output-format", "mp4", "-o", str(out / "%(id)s" / "video.%(ext)s"),
           "--print", "after_move:filepath"]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["yt-dlp failed"])[-1]
        hint = ""
        if re.search(r"login|log in|cookies|rate-limit|not available|private", err, re.I):
            hint = (" - the site wants a signed-in session. Ask the user for the file itself (save it from the app or "
                    "screen-record it), or ask before retrying with --cookies-from-browser")
        if re.search(r"no video|There is no video", err, re.I):
            hint = " - the post has no video (a photo or an image carousel)"
        fail(f"{url}: {err}{hint}")
    return [Path(line) for line in r.stdout.splitlines() if line.endswith(".mp4")]


def summarise(video: Path, url: str) -> dict:
    info_path = video.with_suffix(".info.json")
    info = json.loads(info_path.read_text()) if info_path.exists() else {}
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(video)], capture_output=True, text=True).stdout or "{}")
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    caption = info.get("description") or ""
    meta = {
        "url": url,
        "id": info.get("id") or video.parent.name,
        "site": info.get("extractor"),
        "author": info.get("uploader") or info.get("channel"),
        "caption": caption,
        "hashtags": re.findall(r"#\w+", caption),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "posted": (datetime.fromtimestamp(info["timestamp"], timezone.utc).date().isoformat()
                   if info.get("timestamp") else None),
        "music": info.get("track") or None,
        "duration_s": round(float(probe.get("format", {}).get("duration", 0)), 2),
        "size_mb": round(int(probe.get("format", {}).get("size", 0)) / 1e6, 1),
        "width": v.get("width"), "height": v.get("height"),
        "fps": round(int(num) / int(den), 2) if int(den or 1) else None,
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "downloaded": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "use": "study of editing style only; do not republish",
    }
    (video.parent / "source.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    info_path.unlink(missing_ok=True)  # the raw yt-dlp dump is large and holds more than the study needs
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", type=Path, default=Path.home() / "concat-analysis" / "refs",
                    help="where to put them (must be under the home folder, never inside a repo)")
    ap.add_argument("--cookies-from-browser", metavar="BROWSER",
                    help="use the user's signed-in session; only with the user's explicit OK")
    ap.add_argument("--any-site", action="store_true", help="allow a host outside the default list")
    a = ap.parse_args()
    for tool in ("yt-dlp", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fail(f"{tool} not found on PATH (macOS: brew install yt-dlp ffmpeg)")
    out = a.out.expanduser().resolve()
    if Path.home().resolve() not in out.parents:
        fail("--out must be inside the home folder")
    if (out / ".git").exists() or any((p / ".git").exists() for p in out.parents):
        fail("--out is inside a git repository; reference videos must not be committed")
    for url in a.urls:
        check_url(url, a.any_site)
    for url in a.urls:
        for video in fetch(url, out, a.cookies_from_browser):
            m = summarise(video, url)
            print(f"{video}  |  {m['duration_s']}s {m['width']}x{m['height']} "
                  f"{'with' if m['has_audio'] else 'NO'} audio  |  {m['author']}")


if __name__ == "__main__":
    main()

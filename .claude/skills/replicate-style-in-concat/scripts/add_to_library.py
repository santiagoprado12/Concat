# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Jareer Abdullah and Concat contributors
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Put sound files into the user's own Concat sound library (the Audio page's "Mine" shelf).

Concat's own "Concat" shelf is empty until `concatapp/assets` gets an `audio/` folder, so sounds the
user should be able to audition and drag onto the timeline go here instead. It writes what the app
writes (`crates/concat-host/src/sounds.rs`): a copy of each file in `<data>/audio/` and an entry in
`library.json` with the name, file, duration and 64 envelope bars (peaks 0..1, hundredths).

    uv run --python 3.12 add_to_library.py "Pack - Pop=~/sfx/pack/pop.wav" "Kenney - drop 002=~/sfx/drop_002.wav"
    uv run --python 3.12 add_to_library.py --dir DIR_OF_WAVS --prefix "Kenney - "      # every sound in a folder
    uv run --python 3.12 add_to_library.py --library /tmp/lib ...                      # another library folder (tests)

Names already in the library are skipped, so it can be run again. A window that has the project open
reads the library when the project opens: close and reopen it to see new sounds.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

EXTENSIONS = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg", ".opus", ".aif", ".aiff"}


def default_library() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library/Application Support/app.concat.editor/audio"
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", home)) / "app.concat.editor" / "audio"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "app.concat.editor" / "audio"


def envelope(path: Path):
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"],
        capture_output=True,
    ).stdout
    x = np.abs(np.frombuffer(raw, np.float32))
    if not len(x):
        return 0.0, []
    bars = [round(float(min(1.0, c.max() if len(c) else 0.0)), 2) for c in np.array_split(x, 64)]
    return len(x) / 22050, bars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items", nargs="*", help='"Name=path" pairs')
    ap.add_argument("--dir", help="add every sound file in this folder")
    ap.add_argument("--prefix", default="", help="prefix for names taken from --dir file names")
    ap.add_argument("--library", help="library folder (default: the app's)")
    args = ap.parse_args()

    lib = Path(args.library).expanduser() if args.library else default_library()
    lib.mkdir(parents=True, exist_ok=True)
    index_path = lib / "library.json"
    sounds = json.loads(index_path.read_text())["sounds"] if index_path.exists() else []
    have = {s["name"] for s in sounds}

    todo = []
    for item in args.items:
        name, _, path = item.partition("=")
        todo.append((name.strip(), Path(path).expanduser()))
    if args.dir:
        for f in sorted(Path(args.dir).expanduser().iterdir()):
            if f.suffix.lower() in EXTENSIONS:
                todo.append((args.prefix + f.stem.replace("_", " "), f))

    # newest first on the shelf: the first of this batch gets the latest timestamp
    stamp = int(time.time()) + len(todo)
    added = []
    for n, (name, path) in enumerate(todo):
        if name in have or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        file = name + path.suffix.lower()
        shutil.copy(path, lib / file)
        duration, bars = envelope(lib / file)
        added.append({
            "id": hashlib.sha1(file.encode()).hexdigest()[:12],
            "name": name,
            "file": file,
            "duration": round(duration, 4),
            "category": "",
            "bars": bars,
            "added": stamp - n,
        })
    index_path.write_text(json.dumps({"sounds": added + sounds}, ensure_ascii=False, indent=2))
    print(f"{len(added)} added, {len(added) + len(sounds)} in {lib}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

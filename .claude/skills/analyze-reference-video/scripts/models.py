"""Where the optional ONNX models live and how to fetch them (shared by transitions.py and sounds.py).

Models are kept outside the repo, under ~/concat-analysis/models/. Nothing is downloaded unless the caller passes
--download, so ask the user before using it. Every file is checked against a SHA-256.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path.home() / "concat-analysis" / "models"

# name -> (relative path, url, sha256, size in MB, licence)
MODELS = {
    "transnetv2": ("transnetv2/transnetv2.onnx",
                   "https://huggingface.co/edgetools/transnetv2/resolve/main/transnetv2.onnx",
                   "c4d54a682bace32f25136ef83ca2c9d403e8f8193775efeb995172a0d95a8e0c", 31, "MIT"),
    "yamnet": ("yamnet/yamnet.onnx",
               "https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet.onnx",
               "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e", 16, "Apache-2.0"),
    "yamnet_classes": ("yamnet/yamnet_class_map.csv",
                       "https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet_class_map.csv",
                       "cdf24d193e196d9e95912a2667051ae203e92a2ba09449218ccb40ef787c6df2", 0, "Apache-2.0"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure(name: str, download: bool = False, override: Path | None = None) -> Path:
    """Return the path of a model, fetching it only when `download` is true."""
    if override:
        if not override.exists():
            sys.exit(f"no such model file: {override}")
        return override
    rel, url, digest, mb, lic = MODELS[name]
    path = ROOT / rel
    if path.exists() and sha256(path) == digest:
        return path
    if not download:
        sys.exit(f"{name} model missing at {path}\n"
                 f"  ({mb} MB, {lic}). Ask the user, then re-run with --download, or fetch it yourself:\n"
                 f"  curl -L --create-dirs -o '{path}' '{url}'")
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {name} ({mb} MB) from {url}")
    urllib.request.urlretrieve(url, path)
    if sha256(path) != digest:
        path.unlink()
        sys.exit(f"{name}: checksum mismatch after download, file removed")
    return path

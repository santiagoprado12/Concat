# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
"""Re-apply the old single `mask` of every clip of a project saved by Concat 0.2.8 or earlier, with `clip_masks` (0.2.10+).

  python3 migrate_v1_masks.py PROJECT_FOLDER --steps STEPS.json     # writes the MCP steps, changes nothing
  python3 -I mcp_run.py --bin <concat 0.2.10 binary> STEPS.json     # opens, re-masks every clip, saves

Why: from 0.2.10 a clip has `masks` (a list) and the app no longer reads the old `mask` field. A v1 project opens
without any error but every clip that was masked is drawn WITHOUT its mask: in the split-screen reel (sala_v17, 17
masked clips) the second person's half came out empty, in previews and in the export. Found 2026-11-11.

What does NOT work (tried): rewriting concat.json by hand to put `masks` in each clip, with or without `version: 2`.
The app still drew the half empty. Calling `clip_masks` through the API on the open project does work, and
`project_save` then keeps it.

Run it on a COPY of the project (the file is rewritten as format version 2 and an older Concat cannot open it
afterwards), with the window and any MCP session closed (the folder is locked while open).
Keyframes on the old mask (maskX, maskY, ... through `keyframe_set`) are not carried over: the script lists the
clips that have any, and you re-key them with `mask_key_set`.
"""
import json
import sys
from pathlib import Path


def masks_args(m: dict) -> list:
    return [{
        "source": {"kind": "shape", "shape": m.get("shape", "circle"),
                   "width": m.get("width", 0.66), "height": m.get("height", 0.66),
                   "roundness": m.get("roundness", 0.0)},
        "mode": "add", "x": m.get("x", 0.0), "y": m.get("y", 0.0), "rotation": m.get("rotation", 0.0),
        "feather": m.get("feather", 0.0), "invert": bool(m.get("invert", False)),
    }]


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[2] != "--steps":
        sys.exit(__doc__)
    folder = Path(sys.argv[1]).resolve()
    doc = json.loads((folder / "concat.json").read_text())
    clips = doc["clips"]
    items = clips if isinstance(clips, list) else list(clips.values())
    todo = [c for c in items if c.get("mask")]
    keyed = [c["id"] for c in todo if any(str(k.get("property", k) if isinstance(k, dict) else k).startswith("mask")
                                           for k in (c.get("keys") or []))]
    steps = [{"tool": "project_open", "args": {"path": str(folder)}}]
    for c in todo:
        steps.append({"tool": "clip_masks", "args": {"path": str(folder), "clipId": c["id"], "masks": masks_args(c["mask"])}})
    steps.append({"tool": "project_save", "args": {"path": str(folder)}})
    Path(sys.argv[3]).write_text(json.dumps(steps, indent=1))
    print(f"{len(todo)} clips with the old `mask` (format version {doc.get('version')}); steps written to {sys.argv[3]}")
    if keyed:
        print("old mask keyframes not converted on:", ", ".join(keyed))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a list of Concat MCP tool calls in ONE headless session, without registering the MCP server.

  python3 -I mcp_run.py --bin PATH_TO_CONCAT STEPS.json [--tools OUT.json]
  python3 -I mcp_run.py --bin PATH_TO_CONCAT --list-tools

STEPS.json is a list of {"tool": "clip_add", "args": {...}, "as": "name"} objects. A string argument
of the form "$name.createdId" (or "$name.some.path") is replaced by that field of the named earlier
step's result; "$last.createdId" means the previous step. The server's own error text is printed
and the run stops at the first failing step unless the step has "continue": true.

Use this when the Concat MCP server is not registered in the client, or to replay a recipe
(a style, a template) deterministically. Headless mode: the window must not have the project open.
"""
import argparse
import json
import re
import subprocess
import sys
import threading


class Session:
    def __init__(self, binary: str, mode: str = "headless"):
        self.p = subprocess.Popen([binary, "--mcp", mode], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.err: list[str] = []
        threading.Thread(target=lambda: [self.err.append(x) for x in self.p.stderr], daemon=True).start()
        self.n = 0
        self.call_raw("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "mcp_run", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()

    def call_raw(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit("server closed. stderr tail:\n" + "".join(self.err)[-1500:])
            d = json.loads(line)
            if d.get("id") == self.n:
                return d

    def tool(self, name: str, args: dict) -> tuple[bool, dict | str]:
        d = self.call_raw("tools/call", {"name": name, "arguments": args})
        if "error" in d:
            return False, d["error"].get("message", str(d["error"]))
        r = d["result"]
        text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        data = r.get("structuredContent")
        if data is None:
            try:
                data = json.loads(text)
            except ValueError:
                data = {"text": text}
        return (not r.get("isError", False)), (data if not r.get("isError") else text)

    def close(self) -> None:
        self.p.terminate()


def compact(tool: str, out):
    """Drop the bulk every edit result repeats (bin, project, undo flags, lanes) so a run reads."""
    if not isinstance(out, dict) or "timeline" not in out:
        return out
    keep = {k: v for k, v in out.items() if k not in ("media", "project", "canUndo", "canRedo", "timeline")}
    tl = out["timeline"]
    keep["timeline"] = {"duration": tl.get("duration"), "clips": tl.get("clips")}
    if tool in ("project_create", "project_open", "timeline_read"):
        keep["timeline"]["tracks"] = [t["id"] for t in tl.get("tracks", [])]
        keep["media"] = [{k: m.get(k) for k in ("id", "name", "kind", "duration")} for m in out.get("media", [])]
    return keep


def dig(obj, path: str):
    for key in path.split("."):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def subst(v, results: dict):
    if isinstance(v, str):
        m = re.fullmatch(r"\$(\w+)\.(.+)", v)
        if m:
            return dig(results[m.group(1)], m.group(2))
        return v
    if isinstance(v, list):
        return [subst(x, results) for x in v]
    if isinstance(v, dict):
        return {k: subst(x, results) for k, x in v.items()}
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin", required=True, help="the concat executable")
    ap.add_argument("steps", nargs="?")
    ap.add_argument("--tools", help="also save the full tools/list (names, descriptions, JSON schemas) here")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--mode", default="headless", choices=["headless", "window", "auto"])
    a = ap.parse_args()
    s = Session(a.bin, a.mode)
    try:
        if a.list_tools or a.tools:
            tools = s.call_raw("tools/list")["result"]["tools"]
            if a.tools:
                json.dump(tools, open(a.tools, "w"), indent=1)
            if a.list_tools:
                for t in tools:
                    print(f"{t['name']}: {t['description'][:110]}")
        if a.steps:
            results: dict = {}
            for i, step in enumerate(json.load(open(a.steps))):
                args = subst(step.get("args", {}), results)
                ok, out = s.tool(step["tool"], args)
                results[step.get("as", f"s{i}")] = results["last"] = out if ok else {}
                short = json.dumps(compact(step["tool"], out), separators=(",", ":"))[:1500] if ok else out
                print(f"[{i}] {step['tool']} {'ok' if ok else 'FAILED'}: {short}")
                if not ok and not step.get("continue"):
                    sys.exit(1)
    finally:
        s.close()


if __name__ == "__main__":
    main()

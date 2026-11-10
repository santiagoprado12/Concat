# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Concat is a free, local-only video editor (AGPL-3.0-or-later, Rust + Slint) for macOS, Windows, Linux, Android and iOS. This checkout is a personal fork (`origin`), with the upstream project as `upstream`.

## Two directories matter

The git root and the **Cargo workspace root are different**: the workspace is `src/`. Every `cargo` command runs from `src/` (use an absolute path; `cd` state is not reliable). The toolchain is pinned in `src/rust-toolchain.toml` (1.93.1), and the build needs FFmpeg 7+ dev libraries (`brew install ffmpeg`), cmake and a C++ compiler. The editor is a native window, not a web app.

## Commands

```sh
cd src
cargo dev                                  # alias: run the editor with --profile quick (optimised deps, unoptimised UI crate)
cargo run -p concat                        # plain debug build
cargo check -p concat                      # also compiles the .slint files; catches UI wiring errors a per-crate check misses
cargo build --profile app -p concat        # shipping binary (fat LTO, stripped); slow

cargo fmt --check && cargo clippy --workspace --all-targets -- -D warnings   # what CI runs
cargo test                                 # CI uses cargo-nextest: cargo nextest run --workspace
cargo test -p concat-project some_test_name            # one test in one crate
cargo test -p concat-effects -p concat-export -p concat-render -p concat-project --features gpu   # the shader tests need a real GPU (wgpu)

cargo run -p concat-cli -- probe video.mp4             # the engine without the window
cargo run -p concat-cli -- api '{"method":"catalogue.list","kind":"filter"}'
```

From the repo root, CI also checks:

```sh
python3 scripts/locales.py --check    # run without --check after changing any UI string (en.json is the inventory; see TRANSLATING.md)
python3 scripts/models.py --check     # after adding or changing a downloadable model (also list it in models/manifest.toml)
```

Run the app with a project directly: `concat --project <folder>`. A project folder is locked by one process at a time (`concat.lock`), so close the window or the MCP session before opening it elsewhere.

## Architecture

The dependency arrows point one way (`src/README.md` has the full table):

```
concat -> concat-speech -> concat-host -> {export, project, media} -> core
                                       -> render -> core
                                          export -> effects -> project
concat-cli -> concat-server -> concat-api -> concat-host
concat-mcp -> concat-api            (the MCP server behind `concat --mcp`)
```

- `concat-core` is std-only (time, arena, frames, timeline model); `concat-media` is the only crate that touches FFmpeg.
- `concat-project` is the document: a project is a **folder with `concat.json`**, and every edit is a command (`edit.apply`) with undo. The window, the JSON-RPC API and the MCP server all go through the same commands, so anything the GUI can do an agent can do, with the same refusals.
- `concat-effects`: each effect, filter, transition and audio package is a folder in `crates/concat-effects/packages/concat.<name>/` (WGSL shader or FFmpeg chain + manifest), discovered by `build.rs` at compile time. A new package needs no Rust registration; if it does not show up, `cargo clean -p concat-effects`.
- `concat-api` is the one dispatcher (JSON requests in, responses and events out; exports are jobs); `concat-server` carries it over TCP/Unix socket/gRPC. `concat-mcp` (`tools.rs`) generates its tool schemas from the API types. A new capability usually means a variant in `concat-api/src/message.rs` plus an entry in `concat-mcp`'s tool catalogue.
- `concat` is the Slint window; `crates/concat/src/platform.rs` is where desktop, Android and iOS differ.

Conventions that are easy to violate:
- Timestamps are `concat_core::time::Rational`, never `f64`.
- Threads, not async. Concrete types over generics until three call sites need one.
- Log with the `log` facade, never `println!`/`eprintln!` (a packaged build has no terminal; `CONCAT_LOG=debug`).
- New source files start with the two-line SPDX header (see `CONTRIBUTING.md`; do not add another copyright line). Commits to upstream-bound work are signed off (`git commit -s`).

## Project files and media

- Media paths in `concat.json` are **absolute**; there is no relative-path or "collect files" feature yet, so a project does not move between machines by copying the folder. Templates (`concat-host/src/templates.rs`) are the exception: they bundle assets with bundle-relative paths.
- Lanes: a higher lane number draws above a lower one.

## Driving Concat from an agent (MCP)

`concat --mcp [auto|window|headless]` serves 42 tools (`docs/MCP.md`; trust `--list-tools` over the docs). Headless writes only under the home folder (exports, previews, projects). Edits stay in memory until `project_save`.

This fork carries skills that use it, in `.claude/skills/`, meant to run in this order for a new raw video (`fetch-reference-video` first when the reference is a link): `propose-edit-plan` (publish a design canvas the user approves) -> `analyze-reference-video` -> `distill-editing-style` -> `replicate-style-in-concat`. Read `replicate-style-in-concat/references/learnings.md` before driving the MCP: it lists what was verified against the real app (lane order, trim recipe, `title_add above:true`, tracking gotchas) and what cannot be done (no text animation, no sound library, no transcription in the MCP). `run-concat` builds and launches the app; `study-editors` benchmarks against CapCut/DaVinci Resolve. `fetch-course-lesson-video` downloads the video of a lesson on a private course page through the user's Chrome (needs the Claude in Chrome or Codex Chrome extension; it guides the install if missing). `upload-to-drive-via-browser` delivers a big final file (over the 10 MB per-call limit of the browser file tool) to a Drive folder through the user's own Chrome, for when they only have a phone. The user's house editing style is in `propose-edit-plan/references/house-style.md`.

The user's taste is recorded, and later videos start from it: `propose-edit-plan/references/house-style.md` (picture, text, grade, voice chain, working preferences), `replicate-style-in-concat/sounds/` (the eight approved sound files, CC0, with when to use each and their levels) and `replicate-style-in-concat/fonts/` (Open Sans static files and which font is for what), `replicate-style-in-concat/references/sfx-sources.md` (the sources and rules for sounds; Concat's own sound shelf is still empty) and the newest entries of `learnings.md` (the split-screen two-character reel, 2026-11-07: listener footage, boomerang, cuts measured with `frame_descriptors.py`, fonts, review renders) (copying an edit from a screen recording, the one-frame black flash, filter order). Use those choices first and ask before departing from them.

**Review renders are small** (`export_start` with width 540, height 960, crf 34: about a minute and 3 MB); export full quality only after the user approves. The user usually reviews on a phone and answers with screenshots and timestamps: fix those seconds, keep what they approved.

Skill scripts are PEP 723 files run with `uv run --python 3.12 <script>` (3.12 is needed for the numpy/librosa/onnxruntime/torch wheels); after changing `analyze.py` run `analyze-reference-video/scripts/selftest.py`. Optional ONNX models (TransNet V2, YAMNet) live under `~/concat-analysis/models/` and are downloaded only with `--download`, after asking the user.

## Working in this fork

- The repo is public. Analysis output, footage, transcripts and anything from the user's videos go under `~/concat-analysis/<job>/`, never in the repo, and no personal data (email, home paths, names from footage) goes into commits or skills.
- Commits use the GitHub noreply identity configured in this repo's local git config; check `git config user.email` is the `@users.noreply.github.com` address before committing.
- Push only to `origin` (the fork) and only when asked. Several GitHub accounts exist on this machine: check `gh auth status` and that the active account is the fork owner's before any `gh` call that writes.
- Pull upstream changes with `git fetch upstream` and merge; the fork's `main` has already diverged by the `.claude/skills/` additions.

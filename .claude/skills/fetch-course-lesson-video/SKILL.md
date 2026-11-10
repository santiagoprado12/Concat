---
name: fetch-course-lesson-video
description: Download the video of a lesson from a private course or membership page (Circle, Skool-style communities and similar) that needs the user's login, by opening the page in the user's own Chrome through an AI browser extension, finding the real video link inside it, and downloading it with yt-dlp. Use it when the user pastes a link to a lesson or class page ("baja el video de esta clase", "entra a este link, necesita contraseña", "es como de YouTube pero privado"), or wants the editing instructions of a class turned into notes. Needs the Claude in Chrome or the Codex Chrome extension; if it is not installed, this skill walks the user through installing it.
---

# Fetching the video of a private course lesson

Claude (or Codex) cannot sign in for the user and cannot watch a link. What works: the user is already signed in to the course site in one of their Chrome profiles, a browser extension lets the AI tool drive that profile, and the lesson page usually embeds a normal video (often an unlisted YouTube link) that `yt-dlp` can download without any password. This was verified on a 22-minute lesson hosted on Circle: the page showed the link as text under the player, and `fetch-reference-video` downloaded it (4K, 471 MB) with no cookies.

## 0. What is needed (check, and help install what is missing)

1. **`yt-dlp` and `ffmpeg`** on the PATH (`brew install yt-dlp ffmpeg` on macOS). If missing, say so and ask before installing (a few MB).
2. **A Chrome extension that lets the AI tool drive the user's Chrome**, signed in to the course. Check which one this session has:
   - **Claude in Chrome**: tools named `mcp__claude-in-chrome__*` (they may be deferred: load them with ToolSearch; the skill `anthropic-skills:chrome-browser`, when listed, explains the details).
   - **Codex Chrome extension**: the Chrome plugin inside the Codex app.
   - Any other AI tool with a browser extension works the same way: open the page, read it, never type the password.

   If none is available, **do not give up and do not improvise with the user's cookies: walk the user through installing it** (section "Installing the extension", below), step by step, one question at a time, and wait for them to confirm each step. If they do not want to install anything, use the fallback in section 5.
3. **The user signed in to the course site in the Chrome profile where the extension is installed.** Several profiles are common (personal, work, a family member's): the extension only controls the profile where it is installed and enabled. In the session that verified this, the first connected browser was a profile that was not signed in (the lesson URL redirected to the login page); the right profile only appeared as a second connected browser after the user installed the extension there and signed in to the extension with the same account.

## 1. Open the lesson in the right browser

1. List the connected browsers (Claude in Chrome: `list_connected_browsers`; pick one with `select_browser`, loading it with ToolSearch first). With two or more, choose the one the user named; if unsure, open the page and look at which account is signed in, and ask.
2. Open a **new tab** for the lesson URL (do not reuse the user's tabs), wait 3 seconds, and take a screenshot.
3. If the page is a login or sign-up page, stop: tell the user the profile is not signed in and ask them to sign in in that tab (or to switch profile). **Never enter or request a password**, never create an account, never accept terms for them.

## 2. Find the real video link in the page

Look in this order, with the extension's `find` and `read_page` (they return element text and attributes without dumping the whole page):

1. Text near the player that contains a link: course platforms often print a line such as "copy and paste this link in your browser: https://youtu.be/..." under the video. Search for `youtu.be`, `youtube.com`, `vimeo.com`, `wistia`, `loom.com`.
2. The player's `<iframe>`: ask `find` for "video iframe" and read its `src` attribute (an embed URL such as `youtube.com/embed/<id>` is the video id: `https://youtu.be/<id>`).
3. A "download" or "share" button next to the lesson.

Notes from the verified run: the page-script tool refused to print a result that contained query strings or cookie-like data (`[BLOCKED: Cookie/query string data]`), so use `find` and `read_page` to read links instead of printing `document.cookie`, `location` or full `href` lists. Do not read cookies.

State what you found before downloading: the host, the lesson title if visible, and the duration if the player shows it.

## 3. Download

Use the existing skill `fetch-reference-video` (its `scripts/fetch.py`), with the video link, not the lesson page:

```bash
python3 -I <repo>/.claude/skills/fetch-reference-video/scripts/fetch.py "https://youtu.be/<id>"
```

- **YouTube (public or unlisted):** works without cookies. A 22-minute 4K lesson came down as 471 MB and keeps its sound; `source.json` records duration and resolution. Tell the user the size before starting if it is over 200 MB.
- **Other hosts (Vimeo, Wistia, Loom, a direct `.mp4`):** `fetch.py` refuses them unless `--any-site` is passed; pass it only because the user asked for this lesson. Not verified in this repo: some embeds only play from the course page (they check the `Referer`); if `yt-dlp` fails, retry once with `--referer <lesson page URL>` through `yt-dlp` directly, and if it still fails use the fallback in section 5.
- **Cookies:** never pass `--cookies-from-browser` on your own. It would use the user's signed-in session; ask first, say which browser profile, and only when the site refuses a plain download.
- The file goes to `~/concat-analysis/refs/<id>/video.mp4` (outside the repo, never committed: it belongs to the course author and is for the user's own study).

When the download is done, close the tab you opened (and any other tab you created in this task).

## 4. Turn the class into notes (what the user usually wants)

A class is a person talking, usually over a screen recording of an editor, not a reel: skip the shot, transition and sound-effect analysis of `analyze-reference-video` and do this instead:

1. Extract 16 kHz mono audio and transcribe with whisper.cpp using the same model file Concat uses (see "Transcript, with word timings" in `analyze-reference-video`), `-l <language>`, and add `--prompt "<tool and brand names the class uses>"` (a prompt with the names fixed most misheard words when transcribing the user's own Spanish recordings; not measured on a class). Whisper `base` mishears app names and menu labels: correct them from the screenshots and list your guesses.
2. Read the timestamped text and note the steps in order, with the minute each starts.
3. Look at frames, not just the transcript: pull one frame (`ffmpeg -ss T -i video.mp4 -frames:v 1`) at the moments where the speaker shows the result or a setting (the finished edit, the title, the labels, the export screen). Crop the phone preview area to read details.
4. Write `instructions.md` under `~/concat-analysis/<job>/` with the recipe (steps and times), the text and graphics layer, the traps the teacher mentions and the export settings, and say what the class does not cover (sound, music, transitions, the checklist it only cites). Keep names of people and courses out of anything that goes into the repo.
5. Ask what they want next (copy the editing style onto their own raw video, or just the notes). For a new raw video continue with `propose-edit-plan`.

## 5. Fallbacks

- No extension and the user does not want one: ask them to open the lesson, copy the video link shown under the player (or the share link of the embedded video) and paste it; then go straight to section 3. Or ask them to save the video from the platform and send the file path.
- The lesson uses a player that cannot be downloaded by link: ask for a screen recording or the file, and use `analyze-reference-video` on that.

## Installing the extension (guide the user, do not do it for them)

Only the user can install a browser extension and sign in. Tell them plainly what each step does, give the link, wait for "listo" before the next step, and check at the end that the tool now sees the browser. Which one to suggest: the one that matches the AI tool they are using in this conversation.

### Claude in Chrome (Anthropic)

1. Use **Google Chrome** on a computer (the extension is not supported on other Chromium browsers or on phones) and the Chrome **profile where they are signed in to the course**.
2. Open the Chrome Web Store listing and check the publisher is **Anthropic**: <https://chromewebstore.google.com/detail/fcoeoabgfenejglbffodgkkbkcdhcgfn> (extension id `fcoeoabgfenejglbffodgkkbkcdhcgfn`). Press **Add to Chrome**, then **Add extension**. Anthropic's own guide: <https://support.claude.com/en/articles/12012173-getting-started-with-claude-in-chrome>.
3. Pin the extension (puzzle icon, pin) and open its side panel; **sign in with the same Claude account** they use here. Availability depends on the plan (it launched in beta for paid plans; the guide above is the current source): if the extension says their plan is not supported, tell them and use the fallback.
4. Leave Chrome open. Back in the AI tool, list the connected browsers: a new one should appear. If it does not, ask them to open the side panel again, check the extension is enabled for that profile (`chrome://extensions`), and try once more before stopping.
5. Permissions: the extension asks for each site the first time; they approve the course site (and the video host, if asked). They can refuse any of them, and then the fallback applies.

### Codex Chrome extension (OpenAI)

1. Requirements at the time of writing (check the page): macOS or Windows, Chrome, and a region where it is offered (not the EU or the UK). Official page: <https://developers.openai.com/codex/app/chrome-extension>.
2. Install the extension from the Chrome Web Store: <https://chromewebstore.google.com/detail/codex/hehggadaopoacecdllhhajmbjkdcmajg> (check the publisher is OpenAI), in the profile where they are signed in to the course.
3. In the **Codex app**, open the plugins section and install the **Chrome** plugin, then approve site access when Chrome and Codex ask. Codex asks before sensitive actions (visiting sites, downloads, uploads).
4. Start a new Codex thread and ask it to open the lesson link. If the connection does not work, the official troubleshooting says a fresh thread often clears it.

### Other AI tools

If the tool they use has its own Chrome extension, the same rule holds: install it from the Chrome Web Store listing of that vendor (check the publisher), enable it in the right profile, sign in to the tool, and test by opening a harmless page first. If it has none, use the fallback in section 5.

## Do not

- Do not type, read or store passwords, cookies or tokens; do not use the user's cookies without asking.
- Do not download anything but the lesson the user pointed at (no whole courses, no other lessons from the sidebar), and do not republish it: study only.
- Do not put the course name, the author, the lesson link or any transcript text in a commit, a skill or anything public; the repo is public.

---
name: upload-to-drive-via-browser
description: Upload a large file (a finished video of 20 to 500 MB) to the user's Google Drive by driving their own Chrome through Claude in Chrome, when they cannot do it themselves (they are on their phone, away from the computer). Use it whenever the user says "súbelo al Drive", "upload the final video there", or asks for the export to be delivered to a Drive folder; also for any other web page that has a file picker and a file bigger than the 10 MB per-call limit of the browser file tool.
---

# Uploading a big file to Drive through the user's browser

The Claude in Chrome tool `file_upload` can put a local file into a page's `<input type=file>` without the bytes passing through the chat, but it accepts at most **10 MB per call**, and Drive creates its picker input only when "Upload file" is clicked (clicking that opens a native dialog that cannot be driven). This recipe gets around both. It was verified with a 18.9 MB and a 34.5 MB mp4 (4 parts); the uploads completed and Drive showed the file in the folder.

## Before you start (outward-facing action: ask)

- Uploading puts the user's file into someone's account. Ask **which Drive and folder**, say the file name and size, and wait for a clear answer. A folder marked "shared" is visible to everyone who has access: say so.
- Confirm the browser is the right profile: `list_connected_browsers`, then `select_browser` with the right `deviceId` (load it with ToolSearch first). After opening Drive, check the avatar letter in the top right before touching anything. The first browser the tools pick may be a different profile than the one the user means.
- Never use the user's cookies or passwords; the signed-in session in that profile is enough. Do not create accounts or share links.

## Recipe

1. Split the file where the shell can read it: `bash -c 'split -b 9000000 -d -a 2 FILE part_'` (9 MB parts, under the limit; zsh stops on an empty glob, so use bash). Parts go in their own temporary folder under the home directory.
2. `tabs_context_mcp` (createIfEmpty), `navigate` to `https://drive.google.com/drive/my-drive`, open the target folder (find the folder cell, double-click it) and screenshot to confirm the breadcrumb.
3. With `javascript_tool`, in one call: save `HTMLInputElement.prototype.click`, replace it so that for `type === 'file'` it only gives the element an id (`claude-upload-input`), appends it to `document.body` and stores it in `window.__fileInput`; then create N hidden staging inputs `claude-stage-0..N-1` (position fixed, 20 px, opacity 0.01), each with a `change` listener that does `window.__parts[n] = await input.files[0].arrayBuffer()`.
4. Click **Nuevo / New** then **Subir archivo / Upload file** by coordinates (screenshot first to find them). The native dialog does not open because of step 3. Check `window.__fileInput` is set.
5. `find` "all file input elements" to get their refs (the staging inputs come first, Drive's captured input last), then `file_upload` part *n* to staging input *n*, one call each. Check `window.__parts.map(p => p.byteLength)` adds up to the file size.
6. `javascript_tool`: `new File([new Blob(window.__parts)], 'Final name.mp4', {type: 'video/mp4'})`, put it in a `DataTransfer`, set `window.__fileInput.files`, dispatch `input` and `change` events on it. Drive starts uploading.
7. Wait (10 s steps) and zoom on the bottom-right panel until it says the upload completed, and check that the file shows in the folder.
8. Clean up: restore the original `click`, remove the `claude-*` elements, null `window.__parts`, close the tab you opened, delete the parts folder. Report the folder, the exact file name and the size you sent.

## What did not work

- A local HTTP server with CORS headers on `127.0.0.1` read by `fetch` from the Drive page hung forever (most likely a Chrome local-network permission prompt that nobody can click). Do not retry it.
- Clicking the file input or "Upload file" directly: opens a native dialog and stalls the session.

## Limits

- Nothing here sets sharing or permissions; do not change them. Large files (hundreds of MB) hold all parts in the page's memory: for more than about 300 MB, ask the user to send it another way.
- Tell the user plainly what was not verified (for example, that the file was not played back from Drive).

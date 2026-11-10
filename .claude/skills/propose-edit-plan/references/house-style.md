# House style (learned from two vertical talking-head reels, one list-builds-up reel and one split-screen two-character reel)

## Our style in one page (read this first; start every new video from it)

What the user has approved or insisted on across four videos. These are defaults: **use them first, and ask before departing from any of them.** The sections below hold the exact numbers per video.

**Look**
- Vertical 1080x1920, 30 fps, hard cuts, no transitions, no punch-ins, no music by default. Clean and quiet: the picture is the people and a few well-placed graphics.
- Colour neutral to cool and slightly dark; never warmer or brighter than the raw footage without asking. Match two shots of the same room (white balance) so a seam or a cut never shows.
- Crop in a little (zoom about 1.1) to hide feet, floors and clutter, rather than showing the whole room.

**Text and graphics**
- Calm sans-serif (Open Sans regular is the current favourite; Hanken Grotesk and DM Serif Display are the bundled alternatives), no bold, soft shadow, **no background plate on captions**. White on dark parts, espresso `#2B221E` on light walls; check contrast per zone before choosing.
- Palette: espresso `#2B221E`, cream `#F4EFD0`, mauve `#8E5E67`, blush `#E8D5D0`, sand `#D9C9B6`, taupe `#B49A85`.
- Title in two lines above the people's heads; small plates (one per person) with the label; "VS" between them when it is a comparison. Captions one word at a time (or phrases of 2 to 4 words in talking-head reels), written by hand from the script, centred where they cover nobody.
- Images that illustrate what is said (cards): bottom and centred, medium size, rising 10 % and fading in over 0.22 s, a hard cut out, a transparent PNG for objects, a mirrored copy when the same object appears twice. Never over a face, never over a caption. No emoji floating around the title (the user tried three and removed them).

**Sound**
- **ALWAYS enable noise cancellation and voice enhancement, without being asked, on every clip that carries a voice** (the user reminded us twice): ffmpeg high-pass and `afftdn` on the raw first, then in Concat `denoise` strength 100, `enhance-voice` amount 100 and `loudness` -16, in that order, through `clip_update patch.filters`; check the saved project afterwards (`concat.json`: every voice clip lists the three filters) and a muted listening clip needs none. `scripts/build_steps.py` now adds the chain by default.
- Only the eight approved effects (`replicate-style-in-concat/sounds/`, with when to use each), very low under the voice: the soft swish when an image enters, the drop and confirmation sounds for list rows.

**Cuts and performance**
- One clip per phrase, the last good take of each line (unless it opens with her reading), each cut ending after the word dies away and starting with no dead air; no long pauses between phrases.
- **A person must always look alive and at the camera or the person who is speaking**: never reading a script, leaning, touching face or hair, or mouthing words. Cuts must be invisible (similar pose, still moment, measured difference under about 9). Slow motion only where the person is still, never below 0.5x unless nothing else works; repeated footage must not be obvious.
- A moment the user already called "perfecto" is locked: never change it while fixing something else.

**Working with the user**
- Spanish, short messages, on a phone: review renders small (540x960, crf 34), full quality only after "me gusta"; they answer with screenshots and a second each: fix those and re-check the frames around them.
- Propose first on a canvas and wait for approval; list the missing resources per moment with its time; ask before downloading, installing, uploading or deleting anything; Trash, never `rm`.
- Say what was measured and what was only seen in frames (they can hear and see what Claude cannot), and count the available footage against what the plan needs before promising a format.


Both reels are one person talking to camera, cut hard, with cutaways. This is what was measured or approved. Sizes are fractions of the frame height; Concat renders the listed fonts.

## Picture
- 1080x1920 at 30 fps. Hard cuts only; one soft dissolve (0.4 s) at most, for a before/after.
- No colour grade on the speaker by default. Optional: a Warm layer at about 20 % to match a colder set (the user declined it once). Direction of taste, from the list reel below: neutral to cool and a little dark (they cooled and darkened a warm, exact copy of a reference grade); never push warm or bright without asking.
- Punch-in: 100 % to 107 % in 0.25 s on about five emphasised words, held to the end of that clip.
- Cutaways (B-roll, screenshots, image cards) sit over the continuing voice. Cards and screenshots rise 10 % of the frame while fading in over 0.22 s and leave with a hard cut.

## Cuts
- One clip per spoken phrase: 0.12 s before the voice, 0.15 s after; pauses between phrases of a take are cut out; the last good take of each line unless its transcript is garbled.
- A clip must never open on the speaker looking away: a pause longer than 0.12 s before the first word is trimmed.

## Text
- Captions: phrases of 2 to 4 words, Hanken Grotesk SemiBold (600), 0.034, cream `#F4EFD0`, soft shadow, no stroke, 28 % below centre. Written by hand where the transcriber misheard.
- Step titles: "PASO N", Montserrat ExtraBold (800), 0.045, cream `#FFF6D5`, shadow, 28 % above centre, typed one letter every 0.06 s, up to 1.8 s on screen, started when the number is said.
- Accent words (the three feelings, a product name, the key word of the call to action): DM Serif Display, 0.075, cream `#FFF6D5`, one word at a time.
- Label chips: Hanken Grotesk Bold, 0.03, dark `#2B221E` on a cream plate (`#F4EFD0`, padding 0.03 x 0.012, radius 0.012). Tracking 0 (0.06 breaks the line).
- Overlay icons (check, cross, bookmark, comment): transparent PNGs, top band (-0.28 to -0.30) or just above the caption (+0.17); never over the face.
- Palette for cards and plates: blush `#E8D5D0`, sand `#D9C9B6`, taupe `#B49A85`, mauve `#8E5E67`, espresso `#2B221E`.

## Sound
- Voice normalised to -16 LUFS (Normalize Loudness on each voice clip); raw recordings were -19 to -21 LUFS.
- Background music optional and very low: a gentle CC0 ambient piece at gain 0.10 (about 20 dB under the voice), 1.5 s fade in, 2.5 s fade out. The first reel had none.
- Effects (CC0, see `replicate-style-in-concat/references/sfx-sources.md`): slide for cards and screenshots (volume 0.7) with a light swish on exit (0.4), a short swish on cuts to B-roll (0.45), a pop when a title or label appears (0.5). About 45 for a 65 s reel, each on a free audio lane. These levels and sounds were later superseded for this user by the approved palette below and in `sfx-sources.md`: only those sounds, and quieter.
- The first reference reel had no music and no placed effects (its sound was the voice only); effects and music are the user's own addition to the style.

## List-builds-up reel ("Rutina realista", 1080x1920, 9.5 s, one speaker pointing at items)

Replicated from a collaborator's CapCut edit (measured on a screen recording, see `replicate-style-in-concat/references/learnings.md`), then tuned by the user. Numbers are fractions of the frame; offsets are from the centre of the frame (positive right/down), taken from the reference at 828x1472.
- **Structure:** 3 rounds x 3 rows (frequency pill / emoji / label). A round ends with a hard cut of the take and the list clears on that frame; the next round's first row appears on the cut. A row's pill, emoji and label enter on the same frame as the speaker says its frequency and points, with no fade and no animation. Pauses between rounds are cut; the first speech starts about 0.4 s into the video, with no dead start.
- **Picture:** zoom 1.16, rotation about +1 degree (the reference straightened the horizon), offsetY -0.046. Grade the user settled on: `concat.white-balance` 5150 K + `concat.exposure` -0.3 + Adjust exposure -0.5 and temperature 11000 (net cooler than the raw footage and about 22 % darker than an exact copy of the reference).
- **Title:** two lines "Rutina realista para / cuidar tus espacios", Bodoni 72 (a macOS system font, not bundled; True Fate was the reference's), size 0.0435, line height 0.78, white with a soft shadow, no outline (the user rejected a black outline), centred at offsetY -0.342.
- **Pills:** white plates (`#FFFFFF`), Bodoni 72, size 0.025, text `#1A1A1A`, no shadow on the black text, padding 0.0109 x 0.01135, radius 0.0095; centres at x +0.215, y -0.249 / -0.048 / +0.160 ("Cada día / Cada semana / Cada mes"). The user first asked for smaller items than my first draft (twice), then asked for an exact copy of the reference, whose sizes these are.
- **Emoji:** Apple Color Emoji PNGs (256 px, square-padded), scale 0.115, centres x about +0.21 to +0.22, y -0.181 / +0.020 / +0.227; same set in every round (the user asked for Apple emoji and a woman meditating instead of a repeated sparkle on the third round's first row).
- **Labels:** Hanken Grotesk Regular (reference: Open Sans), white with a soft shadow, size 0.0225, line height 0.785, centres x +0.209 / +0.209 / +0.203, y -0.120 / +0.082 / +0.292; short two-line breaks ("Anota que / incomoda"), copy exactly as the reference writes it (including its missing accent), not as the brief did.
- **Voice:** from a cleaned copy of the take; Concat `denoise` strength 100, `enhance-voice` amount 100, `loudness` -16 (the same chain as CapCut's "mejorar voz" at maximum plus noise reduction), chain order denoise, enhance, loudness on every clip.
- **Sounds:** only the approved palette (`replicate-style-in-concat/references/sfx-sources.md`): drop 002 / confirmation 001 / confirmation 002 for the three rows, very low under the voice; a sound lands when the finger touches the row if that differs from when the row appears.

## "Two opposite versions" split-screen reel (1080x1920, 77 s, one person playing two characters)

Built from two raw takes with a locked-off camera (details and traps in `replicate-style-in-concat/references/learnings.md`, 2026-11-07). Final look approved by the user; numbers are fractions of the frame (offsets from the centre, positive right/down).
- **Structure:** five moments, each a turn per character, the same turn order throughout (first the "wrong" version, then the "right" one), ending with the brand's method and tool. One speaking clip per phrase from the last good take; the other half always listens on a layer that is muted.
- **Picture:** both raws at scale 1.12 (hides the feet at the bottom of the frame), the top layer masked on the vertical centre line with a soft edge (feather 0.14), the warmer layer cooled with `concat.white-balance` to match the wall at the seam. No transitions, no punch-in, no music.
- **Title:** two lines, Open Sans regular 0.040, espresso `#2B221E`, no shadow, centred at offsetY -0.35. **Plates:** one per person over her head (Open Sans 0.019, padding 0.03 x 0.010, radius 0.007), cream `#F4EFD0` on the left and mauve `#8E5E67` with cream text on the right, offsetY -0.23, offsetX -0.23 and +0.27, "VS" between them on a small cream plate. The reference reel used coloured plates and 4 floating emojis; the user first asked for three emoji (couch, chair, sparkles) and then removed them.
- **Captions:** one word at a time, Open Sans regular 0.034, white, soft shadow, no background, offsetY +0.07 (on the seam between the two people). Written by hand from the script, aligned to Whisper timings, proofread by the user.
- **Cards** (images that illustrate what is said): bottom and centred (offsetY +0.22 to +0.30, scale 0.30 to 0.62 depending on aspect), never over a face or a caption; they rise 10 % while fading in over 0.22 s and leave with a cut; the approved soft swish (volume 0.2) at each entrance. Objects as transparent PNG; two of the same object (chairs) as one image mirrored with `flipH`, scale 0.40 each at offsetX +-0.20; one object scale 0.48.
- **Voice:** each take cleaned with ffmpeg (`highpass 90` twice, `afftdn nr=20`) before Concat's chain (`denoise` 100, `enhance-voice` 100, `loudness` -16); the export measured -16.5 LUFS, peak -4.5 dBFS.
- **Order of the user's complaints (to avoid them from round one):** the listener reading or leaning; abrupt cuts and slow motion on movement; a speaker cut mid-word or a long pause between phrases; captions missing a phrase; images over captions or on the other person; the same listening footage repeated.

## Working with this user (process)

- **Review renders are small and fast:** 540x960 at crf 34 for every iteration (about 1 minute, 3 MB, under the phone upload limit), full quality only after "me gusta" or an explicit go-ahead. Send files with `SendUserFile` (30 MB limit: make a lighter copy).
- **Feedback comes as screenshots with a timestamp each:** check the frames around those seconds (and a frame every 0.5 s of the part you changed) and touch nothing else; ask which parts are approved and keep them fixed.
- **Final delivery:** when the user cannot reach the computer (phone only), upload the final file to the Drive folder they name through the browser (`.claude/skills/upload-to-drive-via-browser`), after asking the folder.

- Speak Spanish; the user is usually on a phone: deliver every video or audio with `SendUserFile`, keep messages short and plain, ask with choices. Tell what was measured and what was only checked on frames, since the user hears and sees what Claude cannot.
- Ask before downloading anything (state source, files, size). Free/CC0 only for sounds, music and fonts that go into a video.
- Iterate in new project folders per version (`name_vN`), keep the final one open in the Concat window when asked, and when told "this one is good" move the earlier projects and renders to the Trash (not `rm`) while keeping the assets they depend on (cleaned audio, icons): projects point at media by absolute path.
- Offer examples to choose from (frames at different exposures, numbered audio samples) instead of guessing taste; apply the choice everywhere, and record it here.
- Judge the voice by the user's ear: three rounds of "still a bit odd" were not predicted by measurements, and a measurably worse chain (max filters) was called perfect.

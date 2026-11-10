# The user's fonts for video text

Concat renders a font by its family name. Four families the user's videos use are **already bundled with Concat** (`src/crates/concat-text/fonts`), so nothing to install; **Open Sans is not bundled**, so its static files are kept here (3 files, 390 KB, SIL Open Font License, `OFL-OpenSans.txt`).

## In use now (the latest approved look)

| Font | Where | Use it for | Sizes and colours the user approved |
| --- | --- | --- | --- |
| **Open Sans Regular (400)** | installed from `fonts/` | Titles, plates ("Menos gasto, más cambio"), "VS" and **one-word captions** in the split-screen reel "Renovando mi sala". The user chose it over DM Serif Display ("de letra nos parece mejor Open Sans", then "sin negrita y en blanco, con un poco de sombra") | Title 0.040 espresso `#2B221E`, no shadow; plates 0.019 (cream `#F4EFD0` on espresso text, mauve `#8E5E67` with cream text), padding 0.03 x 0.010, radius 0.007; "VS" 0.016; captions 0.034 **white with a soft shadow, no background, no weight above regular**, at offsetY +0.07 |
| Open Sans SemiBold (600) and Bold (700) | `fonts/` | Tried and rejected for the split-screen reel (the user wanted no bold). Keep for emphasis only if asked | captions 0.028 to 0.032 on a cream plate were the rejected variant |

## Bundled with Concat (use by name, no install)

| Font | Used for | Where it was approved |
| --- | --- | --- |
| **DM Serif Display** (regular, italic) | the elegant serif of the split-screen reel's first draft (title, plates, "VS" in italic, captions 0.03); accent words 0.075 | first drafts of the split-screen reel, accent words in the talking-head reels |
| **Hanken Grotesk** (Regular 400, SemiBold 600, Bold 700) | **captions of talking-head reels**: phrases of 2 to 4 words, 600, 0.034, cream `#F4EFD0`, soft shadow, 28 % below centre; label chips 700, 0.03, dark on a cream plate | the two talking-head reels (house-style.md) |
| **Montserrat ExtraBold (800)** | "PASO N" step titles, 0.045, cream `#FFF6D5`, typed one letter every 0.06 s | the step-by-step talking-head reel |
| Hanken Grotesk Regular as a stand-in | text the user asked in another font that Concat lacks (Open Sans before it was installed, about 1.22x the size to match the width) | list reel |

Not redistributable, so **not in the repo**: Bodoni 72 and Apple Color Emoji (macOS system fonts, used for the list reel's title/pills and for emoji PNGs). They render by name on the user's Mac only.

## Installing Open Sans so Concat can use it (macOS)

Ask first; download is not needed (the files are here).

1. Copy `OpenSans-Regular.ttf` (and the others if asked) to `~/Library/Fonts/`. Use these **static** files: a *variable* Open Sans ignores the weight in Concat (every weight rendered the same). If a variable `OpenSans-VF.ttf` is already in `~/Library/Fonts`, move it out.
2. Concat caches rendered titles in `~/Library/Application Support/app.concat.editor/titles/`; move that folder's files to the Trash after installing or changing a font, or the old look keeps showing.
3. Use `fontFamily: "Open Sans"` and `fontWeight: 400` (or 600/700) in `title_add` / `captions_add`; check with `preview_frame`.

A project does not carry its fonts: on another machine the text falls back to another font unless the fonts are installed there too.

## Rules the user gave about text

White or espresso, never a colour that fails contrast on their white wall (measure the title zone before choosing; cream text failed there). Captions: no background plate, soft shadow. Titles and plates sit above the people's heads (offsetY -0.35 and -0.23), never over a face; captions on the seam between the two people; cards never under a caption.

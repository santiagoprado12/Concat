# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Concat contributors
# /// script
# dependencies = []
# ///
"""Put hand-written caption words on Whisper's timings.

Whisper hears names and jargon wrong ("moodboard" -> "mutbol") but its TIMES are good when each piece is
transcribed alone. So: you write the correct text (from the script or from what the user said), Whisper gives
the times, and this script lines the two up:

  * words that match a Whisper word (accents and punctuation ignored) take Whisper's start time,
  * words that do not match are spread between their matched neighbours in proportion to syllable count,
  * times are made increasing (at least 0.10 s apart) and the last word starts at least 0.25 s before the end.

Input  : --text "the words you want shown"   --whisper piece.json (whisper-cli -ojf ... --split-on-word --max-len 1)
Output : JSON [[word, seconds_from_piece_start], ...] on stdout (or --out)
Prints how many words matched; below about 70 % re-listen to / re-inspect that piece, the transcript is probably wrong.

Whisper command that works (one chosen piece alone, with the script's key words as a prompt):
  ffmpeg -y -ss IN -t DUR -i RAW -vn -ac 1 -ar 16000 piece.wav
  whisper-cli -m ggml-base.bin -l es -f piece.wav -ojf -of piece --split-on-word --max-len 1 -np --prompt "names and jargon"
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def syl(w):
    return max(1, len(re.findall(r"[aeiou]+", norm(w))))


def align(text, wh, dur=None):
    mine = text.split()
    sm = difflib.SequenceMatcher(None, [norm(x) for x in mine], [norm(w) for w, _ in wh], autojunk=False)
    t = [None] * len(mine)
    matched = 0
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            t[a + k] = wh[b + k][1]
            matched += 1
    first, last = wh[0][1], wh[-1][1]
    if t[0] is None:
        t[0] = first
    i = 0
    while i < len(t):
        if t[i] is None:
            j = i
            while j < len(t) and t[j] is None:
                j += 1
            t0 = t[i - 1]
            t1 = t[j] if j < len(t) else max(last + 0.35, t0 + 0.3)
            ws = [syl(mine[k]) for k in range(i - 1, j)]
            tot, acc = sum(ws), ws[0]
            for k in range(i, j):
                t[k] = t0 + (t1 - t0) * acc / tot
                acc += ws[k - i + 1]
            i = j
        else:
            i += 1
    for k in range(1, len(t)):
        t[k] = max(t[k], t[k - 1] + 0.10)
    if dur is not None:
        t = [min(x, dur - 0.25 - 0.10 * (len(t) - 1 - k)) for k, x in enumerate(t)]
    return [[w, round(x, 2)] for w, x in zip(mine, t)], matched, len(mine)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", required=True)
    ap.add_argument("--whisper", required=True)
    ap.add_argument("--duration", type=float, help="piece length in s (keeps the last word inside it)")
    ap.add_argument("--out")
    a = ap.parse_args()
    js = json.load(open(a.whisper))
    wh = [(w["text"].strip(), w["offsets"]["from"] / 1000) for w in js["transcription"] if w["text"].strip()]
    if not wh:
        sys.exit("Whisper found no words in this piece")
    words, m, n = align(a.text, wh, a.duration)
    print(f"{m}/{n} words matched Whisper", file=sys.stderr)
    s = json.dumps(words, ensure_ascii=False)
    if a.out:
        open(a.out, "w").write(s)
    else:
        print(s)


if __name__ == "__main__":
    main()

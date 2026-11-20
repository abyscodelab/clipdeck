#!/usr/bin/env python3
"""Put the words of a lyrics file onto the timings of a transcript.

    python3 scripts/lyrics.py words.json lyrics.txt --out words.json

A transcript of singing has good timings and wrong words. A lyrics file has the right words and no timings. This
lines the two up word by word (longest matching runs first, the standard library's difflib), copies the timing of
every word that matches, and spreads the words in between over the time between their neighbours. Each word gets
`lyricLine`: the line of the lyrics file it came from, so music styles break pages where the lyrics break lines.

Sung parts that are not in the file (a repeated chorus written once, ad-libs) stay as transcribed, in their own
lines. Lyric lines that were never heard are dropped and counted. Standard library only.
"""
import argparse
import difflib
import json
import re
import sys


def norm(text):
    t = re.sub(r"[^\w']+", "", text.lower(), flags=re.UNICODE).replace("'", "")
    return re.sub(r"in$", "ing", t) if t.endswith("in") and len(t) > 4 else t  # singin' = singing


def read_lyrics(path):
    """[(line index, word)] for every word; blank lines and [Chorus] / (x2) markers are skipped."""
    out, n = [], 0
    for raw in open(path, encoding="utf-8"):
        line = re.sub(r"\[[^\]]*\]|\((?:x\s*\d+|\d+\s*x|repeat[^)]*)\)", "", raw, flags=re.I).strip()
        if not line:
            continue
        for w in line.split():
            if norm(w):
                out.append((n, w))
        n += 1
    return out


def align(heard, lyrics, keep_min=4):
    """heard: transcript words. lyrics: [(line, word)]. Returns (words, stats)."""
    a = [norm(w["text"]) for w in heard]
    b = [norm(w) for _, w in lyrics]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out = []
    stats = {"lyricWords": len(b), "matched": 0, "placedBetween": 0, "notHeard": 0, "keptAsHeard": 0, "droppedHeard": 0}
    extra_line = 100000  # line numbers for stretches kept as transcribed

    def put(line, text, start, end):
        out.append({"text": text, "startMs": int(round(start)), "endMs": int(round(max(end, start + 60))), "prob": None, "lyricLine": line})

    def keep_heard(run):
        """A repeated chorus, a bridge or ad-libs the file leaves out stay as transcribed; stray words are dropped."""
        nonlocal extra_line
        if len(run) < keep_min:
            stats["droppedHeard"] += len(run)
            return
        line = extra_line
        for k, h in enumerate(run):
            if k and (h["startMs"] - run[k - 1]["endMs"] > 450 or re.search(r"[.!?]$", run[k - 1]["text"])):
                line += 1
            put(line, h["text"], h["startMs"], h["endMs"])
        extra_line = line + 1
        stats["keptAsHeard"] += len(run)

    def place_in_gap(j1, j2, t0, t1):
        """Written words nobody transcribed: spread them over a silence long enough to sing them, else count them out."""
        n = j2 - j1
        if n and t1 - t0 >= 160 * n:
            step = (t1 - t0) / n
            for k, j in enumerate(range(j1, j2)):
                put(lyrics[j][0], lyrics[j][1], t0 + k * step, t0 + (k + 0.9) * step)
            stats["placedBetween"] += n
        else:
            stats["notHeard"] += n

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                h = heard[i1 + k]
                line, text = lyrics[j1 + k]
                put(line, text, h["startMs"], h["endMs"])
            stats["matched"] += i2 - i1
        elif tag == "replace":
            # the same stretch heard differently
            nh, nl = i2 - i1, j2 - j1
            first_line = lyrics[j1][0]
            head = next((j for j in range(j1, j2) if lyrics[j][0] != first_line), j2) - j1  # written words up to the line end
            if nl > nh and head <= nh:
                # the rest of this lyric line was heard as these words: spread the line's words over them by length;
                # what the file has after that line was not sung here
                t0, t1 = heard[i1]["startMs"], heard[i2 - 1]["endMs"]
                weights = [max(2, len(norm(lyrics[j][1]))) for j in range(j1, j1 + head)]
                total, at = float(sum(weights)), float(t0)
                for j, wgt in zip(range(j1, j1 + head), weights):
                    span = (t1 - t0) * wgt / total
                    put(lyrics[j][0], lyrics[j][1], at, at + span * 0.92)
                    at += span
                stats["placedBetween"] += head
                place_in_gap(j1 + head, j2, t1, heard[i2]["startMs"] if i2 < len(heard) else t1)
            else:
                n = min(nh, nl)  # pair the words one to one from the start
                for k in range(n):
                    h = heard[i1 + k]
                    put(lyrics[j1 + k][0], lyrics[j1 + k][1], h["startMs"], h["endMs"])
                stats["placedBetween"] += n
                if nh > nl:  # more was sung than written here (ad-libs, "oh oh oh"): keep a real run as heard
                    keep_heard(heard[i1 + n:i2])
                elif nl > nh:  # more written than sung here: use the silence that follows, if there is enough
                    t0 = heard[i2 - 1]["endMs"]
                    place_in_gap(j1 + n, j2, t0, heard[i2]["startMs"] if i2 < len(heard) else t0)
        elif tag == "insert":
            # written but not heard here: use the silence between the neighbours if there is enough of it
            t0 = out[-1]["endMs"] if out else 0
            t1 = heard[i1]["startMs"] if i1 < len(heard) else t0
            place_in_gap(j1, j2, t0, t1)
        else:  # delete: heard, not in the file
            keep_heard(heard[i1:i2])
    out.sort(key=lambda w: w["startMs"])
    for x, y in zip(out, out[1:]):  # never overlap
        if x["endMs"] > y["startMs"]:
            x["endMs"] = max(x["startMs"] + 40, y["startMs"])
    stats["coverage"] = round(stats["matched"] / max(1, len(b)), 2)
    return out, stats


def main():
    ap = argparse.ArgumentParser(description="Align a lyrics file to a transcript's word timings.")
    ap.add_argument("words", help="words.json from scripts/transcribe.py")
    ap.add_argument("lyrics", help="plain text, one lyric line per line")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = json.load(open(a.words))
    lyr = read_lyrics(a.lyrics)
    if not lyr:
        sys.exit("lyrics.py: the lyrics file has no words")
    words, stats = align(data["words"], lyr)
    data["words"] = words
    data["lyrics"] = stats
    json.dump(data, open(a.out, "w"), ensure_ascii=False, indent=1)
    if stats["coverage"] < 0.5:
        stats["warning"] = "under half of the lyric words were found in the audio: is this the right lyrics file?"
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()

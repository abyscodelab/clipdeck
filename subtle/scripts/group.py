#!/usr/bin/env python3
"""Clean word timings and group them into caption pages.

    python3 scripts/group.py words.json --style styles/glide.json --out captions.json [--srt captions.srt]

Reads words.json (see docs/ARCHITECTURE.md), writes captions.json. Spoken numbers become single tokens
(scripts/spoken_numbers.py) and the highlighted words are picked by rule (scripts/emphasis.py). Standard library only.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cuts import clamp_pages, split_pages  # noqa: E402
from emphasis import MODES, SENTENCE_END, WEAK_END, bare, finalise, rule_picks, split_words  # noqa: E402
from spoken_numbers import normalise_numbers  # noqa: E402

CLAUSE_END = re.compile(r"[,;:–—]['\")\]]*$")
FILLERS = {"um", "uh", "umm", "uhh", "erm", "hmm", "mm"}


def clean_words(words, replacements=None, strip_fillers=False, min_ms=80, close_gap_ms=30, numbers="auto", language=None):
    """Fix timings so every word is usable: ordered, at least min_ms long, tiny gaps closed."""
    out = []
    for w in words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        if strip_fillers and bare(text) in FILLERS:
            continue
        if replacements:
            key = bare(text)
            if key in replacements:
                lead = re.match(r"^\W*", text).group(0)
                trail = re.search(r"\W*$", text).group(0)
                text = lead + replacements[key] + trail
        item = {"text": text, "startMs": int(round(w["startMs"])), "endMs": int(round(w["endMs"])), "prob": w.get("prob")}
        if w.get("lyricLine") is not None:  # from scripts/lyrics.py: which line of the lyrics file this word belongs to
            item["lyricLine"] = w["lyricLine"]
        out.append(item)
    out.sort(key=lambda w: w["startMs"])
    joined = []
    for w in out:  # "25" + ",000" → "25,000"; a lone "." or "%" belongs to the word before it
        if joined and (re.match(r"^[,.]\d", w["text"]) or re.match(r"^[^\w$₹€£#@(\[\"'“‘]+$", w["text"], flags=re.UNICODE)):
            joined[-1]["text"] += w["text"]
            joined[-1]["endMs"] = max(joined[-1]["endMs"], w["endMs"])
        else:
            joined.append(w)
    out = joined
    if numbers != "off":  # "five thousand dollars" -> "$5,000": one token, so it is never split across lines or pages
        out = normalise_numbers(out, language, numbers)
    for i, w in enumerate(out):
        if i and w["startMs"] < out[i - 1]["startMs"]:
            w["startMs"] = out[i - 1]["startMs"]
        if w["endMs"] <= w["startMs"]:
            w["endMs"] = w["startMs"] + min_ms
    for i, w in enumerate(out):
        nxt = out[i + 1]["startMs"] if i + 1 < len(out) else None
        if w["endMs"] - w["startMs"] < min_ms:
            w["endMs"] = w["startMs"] + min_ms
        if nxt is not None:
            if w["endMs"] > nxt:  # overlap: give the earlier word what is left, but never less than 40 ms
                w["endMs"] = max(w["startMs"] + 40, nxt)
                if w["endMs"] > nxt:
                    out[i + 1]["startMs"] = w["endMs"]
                    out[i + 1]["endMs"] = max(out[i + 1]["endMs"], out[i + 1]["startMs"] + 40)
            elif nxt - w["endMs"] < close_gap_ms:
                w["endMs"] = nxt
    return out


def split_lines(words, max_chars, max_lines):
    """Assign a line index to each word: as few lines as fit (up to max_lines), split as evenly as possible."""
    texts = [w["text"] for w in words]
    n = len(words)
    if max_lines < 2 or n < 2 or len(" ".join(texts)) <= max_chars:
        return [0] * n
    from itertools import combinations

    def score(cuts):
        bounds = [0, *cuts, n]
        lens = [len(" ".join(texts[a:b])) for a, b in zip(bounds, bounds[1:])]
        sc = (max(lens) - min(lens)) + sum(1000 for v in lens if v > max_chars)
        for k in cuts:
            if CLAUSE_END.search(texts[k - 1]) or SENTENCE_END.search(texts[k - 1]):
                sc -= 3  # prefer breaking after punctuation
            if bare(texts[k - 1]) in WEAK_END:
                sc += 4  # do not leave "the" / "of" hanging at the end of a line
        return sc

    best = None
    for lines in range(2, min(max_lines, n) + 1):
        cand = min(combinations(range(1, n), lines - 1), key=score)
        best = cand
        if score(cand) < 500:  # every line fits: stop at the smallest number of lines
            break
    out, line = [], 0
    for k in range(n):
        if line < len(best) and k == best[line]:
            line += 1
        out.append(line)
    return out


def snap_to_beats(pages, beats, mode, hold, frame):
    """Music styles: a page starts on the beat (or bar) at or just before its first word, and cuts happen on beats."""
    grid = sorted(beats.get("downbeats" if mode == "bar" else "times") or [])
    every = sorted(beats.get("times") or [])
    if len(grid) < 2 or len(every) < 2:
        return pages
    import bisect
    beat = (every[-1] - every[0]) / (len(every) - 1)
    tol = 0.3 * beat  # a word may start this much before its beat (singers push)

    def at_or_before(t, g):
        k = bisect.bisect_right(g, t + tol) - 1
        return g[k] if k >= 0 else None

    def next_beat(t):
        k = bisect.bisect_left(every, t)
        return every[k] if k < len(every) else None

    prev_start = None
    for p in pages:
        first = p["words"][0]["startMs"]
        b = at_or_before(first, grid)
        # a bar line that is far before the word is the wrong one: fall back to the beat grid, then to the word itself
        if b is None or first - b > (2.2 * beat if mode == "bar" else 1.2 * beat):
            b = at_or_before(first, every)
        if b is None or first - b > 1.2 * beat:
            b = first
        if prev_start is not None and b <= prev_start:
            b = first
        p["startMs"] = int(round(b / frame) * frame + 1e-6) if abs(round(b / frame) * frame - b) < 1 else int(b // frame * frame + 1e-6)
        prev_start = p["startMs"]
    for i, p in enumerate(pages):
        nxt = pages[i + 1]["startMs"] if i + 1 < len(pages) else None
        last = p["words"][-1]["endMs"]
        if nxt is not None and (hold or nxt - last < 2 * beat):
            end = nxt if nxt - last < 8 * beat else (next_beat(last + beat) or last + 2 * beat)  # a long gap: let go after a beat
        else:
            end = next_beat(last + 0.5 * beat) or last + beat
            if nxt is not None:
                end = min(end, nxt)
        if end != nxt:  # a page start is already on the frame grid: snapping it again would lose a frame
            end = int(end // frame * frame + 1e-6)
        p["endMs"] = max(int(end), p["startMs"] + int(frame))
    return pages


def group_pages(words, page_cfg, fps, wide, beats=None, cuts=None):
    max_words = int(page_cfg.get("maxWords", 3))
    max_lines = int(page_cfg.get("maxLines", 1))
    per_line = int(page_cfg.get("maxCharsPerLineWide" if wide else "maxCharsPerLine", 30 if wide else 18))
    # line mode (music styles): maxWords and the character limit are per lyric line, and a page holds linesPerPage lines
    max_chars = per_line if page_cfg.get("unit") == "line" else per_line * max_lines
    gap_break = int(page_cfg.get("gapBreakMs", 350))
    frame = 1000.0 / fps
    min_ms = int(page_cfg.get("minFrames", 10) * 1000 / 30)
    max_ms = int(page_cfg.get("maxFrames", 90) * 1000 / 30)

    def text_len(ws):
        return len(" ".join(x["text"] for x in ws))

    # 1. Phrases: split at sentence and clause punctuation and at pauses. A caption page never crosses a phrase.
    phrases, cur = [], []
    for w in words:
        if cur:
            prev = cur[-1]
            if SENTENCE_END.search(prev["text"]) or CLAUSE_END.search(prev["text"]) or w["startMs"] - prev["endMs"] > gap_break:
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    # A one-word clause ("Hi,") reads better attached to what follows, when the pause between them is short.
    merged = []
    for ph in phrases:
        if merged and len(merged[-1]) == 1 and not SENTENCE_END.search(merged[-1][-1]["text"]) \
                and ph[0]["startMs"] - merged[-1][-1]["endMs"] <= gap_break and len(ph) + 1 <= max_words \
                and text_len(merged[-1] + ph) <= max_chars:
            merged[-1] = merged[-1] + ph
        else:
            merged.append(ph)
    phrases = merged

    # 2. Pages: cut each phrase into evenly sized pages, so "with gold three / times," becomes "with gold / three times,".
    def fits(c):
        return len(c) == 1 or (len(c) <= max_words and text_len(c) <= max_chars and c[-1]["endMs"] - c[0]["startMs"] <= max_ms)

    pages = []
    for ph in phrases:
        n = max(1, math.ceil(len(ph) / max_words))
        base, extra = divmod(len(ph), n)
        chunks, at = [], 0
        for k in range(n):
            sz = base + (1 if k < extra else 0)
            chunks.append(ph[at:at + sz])
            at += sz
        if not all(fits(c) for c in chunks):
            # long words: pack greedily instead, then even out a lonely last word
            chunks, cur = [], []
            for w in ph:
                if cur and not fits(cur + [w]):
                    chunks.append(cur)
                    cur = []
                cur.append(w)
            if cur:
                chunks.append(cur)
            if len(chunks) > 1 and len(chunks[-1]) == 1 and len(chunks[-2]) > 2 and fits([chunks[-2][-1]] + chunks[-1]):
                chunks[-1].insert(0, chunks[-2].pop())
        # do not end a page on "the", "of", "to" ... when the phrase goes on: pass the word to the next page,
        # unless that would leave another weak word hanging
        for k in range(len(chunks) - 1):
            c, nx = chunks[k], chunks[k + 1]
            if len(c) > 1 and bare(c[-1]["text"]) in WEAK_END and bare(c[-2]["text"]) not in WEAK_END and fits([c[-1]] + nx):
                nx.insert(0, c.pop())
        pages.extend(c for c in chunks if c)

    # 2b. Hard cuts: a page never straddles one. Split at the cut; a tiny remainder joins a neighbour of the same shot.
    if cuts and page_cfg.get("unit") != "line":
        pages = split_pages(pages, cuts, min_ms, max_words, max_chars)

    # Line mode (music styles): a page is one lyric line, or a block of `linesPerPage` lines. Lines come from the
    # lyrics file when there is one (lyricLine), else from the phrases and chunks above.
    line_mode = page_cfg.get("unit") == "line"
    page_lines = None
    if line_mode:
        if any("lyricLine" in w for w in words):
            lines, cur = [], []
            for w in words:
                if cur and w.get("lyricLine") != cur[-1].get("lyricLine"):
                    lines.append(cur)
                    cur = []
                cur.append(w)
            if cur:
                lines.append(cur)
            split, piece_count = [], []
            for ln in lines:  # a lyric line too long for the style is cut into even pieces
                n = max(1, math.ceil(max(len(ln) / max_words, text_len(ln) / per_line)))
                base, extra = divmod(len(ln), n)
                at = 0
                for k in range(n):
                    sz = base + (1 if k < extra else 0)
                    if sz:
                        split.append(ln[at:at + sz])
                        piece_count.append(n - k)  # pieces of this lyric line from here to its end
                    at += sz
            lines = split
        else:
            lines = pages
            piece_count = [1] * len(lines)
        per_page = max(1, int(page_cfg.get("linesPerPage", 1)))
        block_gap = int(page_cfg.get("blockGapMs", 2500))
        pages, page_lines = [], []
        for ln, rest in zip(lines, piece_count):
            # a lyric line that was cut in pieces stays on one page when the page has room for all of it
            room = pages and len(page_lines[-1]) + min(rest, per_page) <= per_page
            if room and ln[0]["startMs"] - pages[-1][-1]["endMs"] <= block_gap:
                page_lines[-1].append(len(pages[-1]))
                pages[-1] = pages[-1] + ln
            else:
                pages.append(list(ln))
                page_lines.append([0])

    out = []
    for i, p in enumerate(pages):
        start = p[0]["startMs"]
        nxt = pages[i + 1][0]["startMs"] if i + 1 < len(pages) else None
        end = p[-1]["endMs"] + 400
        if nxt is not None:
            end = min(end, nxt)
        if end - start < min_ms:  # too short to read: hold it until the next page if there is room
            end = min(start + min_ms, nxt) if nxt is not None else start + min_ms
        end = max(end, p[-1]["endMs"] if nxt is None else min(p[-1]["endMs"], nxt))
        if page_lines is not None:  # line starts were fixed above
            starts = page_lines[i]
            lines = [sum(1 for st in starts if st <= k) - 1 for k in range(len(p))]
        else:
            lines = split_lines(p, per_line, max_lines)
        out.append({
            "startMs": int(round(start / frame) * frame),
            "endMs": int(round(end / frame) * frame),
            "words": [{"text": w["text"], "startMs": w["startMs"], "endMs": w["endMs"], "line": ln, "emphasis": False}
                      for w, ln in zip(p, lines)],
        })
    if beats and page_cfg.get("snap") in ("beat", "bar"):
        snap_to_beats(out, beats, page_cfg["snap"], bool(page_cfg.get("hold")), frame)
    if cuts:
        clamp_pages(out, cuts, fps)
    return out


def to_srt(pages, case):
    def ts(ms):
        h, r = divmod(ms, 3600000)
        m, r = divmod(r, 60000)
        s, ms = divmod(r, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    rows = []
    for i, p in enumerate(pages, 1):
        lines = {}
        for w in p["words"]:
            lines.setdefault(w["line"], []).append(w["text"])
        text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
        rows.append(f"{i}\n{ts(p['startMs'])} --> {ts(p['endMs'])}\n{text}\n")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description="Group word timings into caption pages.")
    ap.add_argument("words")
    ap.add_argument("--style", required=True, help="path to a style JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--srt")
    ap.add_argument("--max-words", type=int, help="override the style's words per page")
    ap.add_argument("--emphasis", default="auto",
                    help="which words to highlight: auto (numbers, prices, names, contrast words), numbers (numbers only) or off")
    ap.add_argument("--emphasis-words", default="", help='words to highlight for sure, e.g. "gold, $5,000"')
    ap.add_argument("--no-auto-emphasis", action="store_true", help="same as --emphasis off")
    ap.add_argument("--numbers", default="auto", choices=["auto", "western", "indian", "off"],
                    help="rewrite spoken numbers as one token ($5,000, 40%%, ₹5 lakh); digit grouping: auto, western or indian; off keeps the transcript")
    ap.add_argument("--cuts", help="cuts.json from scripts/cuts.py ({\"cuts\": [ms, ...]}) or a comma-separated list of ms: pages never straddle a cut")
    ap.add_argument("--beats", help="beats.json from scripts/beats.py: music styles start pages on the beat")
    ap.add_argument("--replace", action="append", default=[], help="heard=Shown spelling fix, e.g. refs=Refs (repeatable)")
    ap.add_argument("--clean", action="store_true", help="drop filler words (um, uh)")
    a = ap.parse_args()

    data = json.load(open(a.words))
    style = json.load(open(a.style))
    src = data["source"]
    fps = float(src.get("fps") or 30)
    wide = src["width"] > src["height"]
    page_cfg = dict(style.get("page", {}))
    if a.max_words:
        page_cfg["maxWords"] = a.max_words
    repl = {}
    for r in a.replace:
        if "=" in r:
            k, v = r.split("=", 1)
            repl[bare(k)] = v
    words = clean_words(data["words"], repl, a.clean, numbers=a.numbers, language=data.get("language"))
    if not words:
        sys.exit("group.py: no words in " + a.words)
    beats = json.load(open(a.beats)) if a.beats else None
    cuts = []
    if a.cuts:
        raw = open(a.cuts).read() if Path(a.cuts).exists() else a.cuts
        try:
            cuts = sorted({int(c) for c in (json.loads(raw)["cuts"] if raw.lstrip().startswith("{") else raw.split(",")) if str(c).strip()})
        except (ValueError, KeyError):
            sys.exit("group.py: --cuts must be a cuts.json file or a comma-separated list of milliseconds")
    pages = group_pages(words, page_cfg, fps, wide, beats, cuts)
    mode, forced = a.emphasis, split_words(a.emphasis_words)
    if mode not in MODES:  # older calls passed the words here: --emphasis "gold,three" meant only these words
        forced, mode = forced + split_words(mode), "off"
    if a.no_auto_emphasis:
        mode = "off"
    rule_picks(pages, mode, forced)
    out = {
        "version": 1,
        "video": {"width": src["width"], "height": src["height"], "fps": fps, "durationMs": src["durationMs"]},
        "style": style.get("name"),
        "language": data.get("language"),
        "pages": pages,
    }
    if beats and beats.get("times"):
        out["beats"] = {"bpm": beats.get("bpm"), "times": beats["times"], "downbeats": beats.get("downbeats", [])}
    if cuts:
        out["cuts"] = cuts
    finalise(out, style)  # emphasised pages hold a beat longer; styles with a giant word get their `big` list
    clamp_pages(pages, cuts, fps)  # the longer hold must not run past a cut either
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    if a.srt:
        open(a.srt, "w").write(to_srt(pages, style.get("case")))
    n = sum(len(p["words"]) for p in pages)
    picks = [{"page": i, "word": w["text"], "reason": w.get("reason")} for i, p in enumerate(pages) for w in p["words"] if w["emphasis"]]
    print(json.dumps({"pages": len(pages), "words": n, "big": len(out.get("big", [])), "highlighted": len(picks), "out": a.out}, ensure_ascii=False))


if __name__ == "__main__":
    main()

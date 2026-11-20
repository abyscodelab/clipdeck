#!/usr/bin/env python3
"""Pick the words a caption highlights, and keep a captions.json consistent after the picks change.

Two ways to pick:
  - rules (no judgement): prices, numbers, percentages and years first, then names, then a few contrast words;
  - by hand (Claude or the user): --pick PAGE:WORD=reason, on top of or instead of the rules.

    python3 scripts/emphasis.py talk.captions.json --style styles/glide.json --show
    python3 scripts/emphasis.py talk.captions.json --style styles/glide.json --pick "12:$5,000=the price, the point of the line" --drop 3:gold
    python3 scripts/emphasis.py talk.captions.json --style styles/glide.json --clear --pick ...      # only my picks
    python3 scripts/emphasis.py talk.captions.json --style styles/glide.json --mode numbers          # run the rules again
    python3 scripts/emphasis.py talk.captions.json --style styles/glide.json                         # after editing the file by hand

Every run ends by refreshing what depends on the picks: an emphasised page holds a beat longer when the next page
leaves room, and styles with a giant word (keyword) get their `big` list rebuilt. Standard library only.
"""
import argparse
import json
import re
import sys

SENTENCE_END = re.compile(r"[.!?…]['\")\]]*$")
# Words a page should not end on when the phrase continues (article + noun, preposition + noun, ...).
WEAK_END = set("""a an the of to in on at for from with by and or but nor so as if than that this these those my your his
her its our their is are was were be been am i'm it's we're you're they're i you we he she they not no very just
ka ki ke ko se mein me par aur ya hai hain tha thi the ek yeh ye woh wo kya nahi""".split())
STOP = WEAK_END | set("""it there here what when where who how why which do does did have has had will would can could should
may might must also then now about into over under up down out off again more most some any all each every""".split())
MODES = ("auto", "numbers", "off")

NUMBER_WORDS = set("""two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty sixty seventy eighty
ninety dozen dozens hundred hundreds thousand thousands million millions billion billions trillion lakh lakhs crore crores
half double twice triple zero""".split())
CONTRAST = set("""never nothing nobody none free broke zero always worst best biggest first only wrong secret impossible
banned illegal dead""".split())
# Capitalised words that are not names.
NOT_NAMES = set("""i i'm i'll i've i'd ok okay yes no hi hello hey so and but well now actually maybe monday tuesday wednesday
thursday friday saturday sunday""".split())
# Long words that carry no meaning by themselves: never a guess.
DULL = set("""that's there's what's actually really basically literally something anything everything someone anyone
everyone thing things saying said going being having doing getting making because through before after between
together another other others always maybe quite rather though although while where which their there these those
people person today tomorrow yesterday""".split())
MAX_HOLD_MS = 700  # an emphasised page may stay this long after its last word (plain pages: 400)


def bare(text):
    return re.sub(r"[^\w']+", "", text, flags=re.UNICODE).lower()


def split_words(arg):
    """ "gold, $5,000" -> ["gold", "$5,000"]: split on commas, but not on the comma inside a number."""
    return [x.strip() for x in re.split(r",(?!\d{3}(?!\d))\s*|;\s*", arg or "") if x.strip()]


def number_kind(text):
    """'price', 'percentage', 'year', 'number' for a token with digits or a currency sign, else None."""
    core = re.sub(r"^[^\w$₹€£]+|[^\w%]+$", "", text, flags=re.UNICODE)
    if not core:
        return None
    if re.search(r"[$₹€£]", core):
        return "price"
    if not re.search(r"\d", core):
        return None
    if core.endswith("%"):
        return "percentage"
    if re.fullmatch(r"(1[5-9]|20)\d\d", core):
        return "year"
    return "number"


def classify(words, i, names, starts=frozenset()):
    """(score, reason) for words[i] in the flat word list. Higher scores win a page's one or two highlight slots."""
    text = words[i]["text"]
    b = bare(text)
    if not b:
        return 0, None
    kind = number_kind(text)
    if kind:
        return {"price": 10, "percentage": 9.6, "year": 9.2, "number": 9}[kind], kind
    if b in STOP and b not in CONTRAST:
        return 0, None
    letters = re.sub(r"[^A-Za-zÀ-ɏऀ-ॿ]", "", text)
    if len(letters) >= 2 and letters.isupper() and b not in NOT_NAMES:
        return 7.5, "name (acronym)"
    if text.lstrip("\"'“‘(")[:1].isupper() and b not in NOT_NAMES and len(b) > 1:
        start = i == 0 or i in starts or bool(SENTENCE_END.search(words[i - 1]["text"]))
        stem = b[:-2] if b.endswith("'s") else b
        if not start or stem in names:
            return 7, "name"
    if b in CONTRAST:
        return 6, "contrast word"
    if b in NUMBER_WORDS:
        return 5.5, "count"
    return 0, None


def guess_score(text):
    """The old fallback: a long content word. Only used in auto mode on pages with nothing better."""
    b = bare(text)
    if not b or b in STOP or b in DULL or len(b) < 4:
        return 0
    s = min(len(b), 10) / 2.0
    if SENTENCE_END.search(text):
        s += 1.0
    return s


def rule_picks(pages, mode="auto", forced=()):
    """Set emphasis and reason on every word from the rules. forced words always win their page."""
    if mode not in MODES:
        raise ValueError(f"emphasis mode must be one of {', '.join(MODES)}")
    wanted = {bare(x) for x in forced if bare(x)}
    flat = [w for p in pages for w in p["words"]]
    # Lyrics have no full stops and every line starts with a capital: there, the first word of a line is a line start,
    # not a name.
    starts = set()
    if not any(SENTENCE_END.search(w["text"]) for w in flat):
        k = 0
        for p in pages:
            for j, w in enumerate(p["words"]):
                if j == 0 or w.get("line") != p["words"][j - 1].get("line"):
                    starts.add(k)
                k += 1
        caps = [i for i, w in enumerate(flat) if w["text"].lstrip("\"'“‘(")[:1].isupper() and bare(w["text"]) not in NOT_NAMES]
        at_start = sum(1 for i in caps if i in starts)
        if len(caps) < 3 or at_start < 0.6 * len(caps):  # capitals sit mid-line: unpunctuated speech with names, not lyrics
            starts = set()
    # A capitalised word in the middle of a sentence is a name; the same word at a sentence start then counts too.
    names = set()
    for i, w in enumerate(flat):
        b = bare(w["text"])
        if i and i not in starts and not SENTENCE_END.search(flat[i - 1]["text"]) and w["text"].lstrip("\"'“‘(")[:1].isupper() and b not in NOT_NAMES and b not in STOP:
            names.add(b[:-2] if b.endswith("'s") else b)
    seen = {}
    at = 0
    quiet = 1  # pages since the last highlight

    def key(text):
        b = bare(text)
        return b[:-2] if b.endswith("'s") else b
    for p in pages:
        ws = p["words"]
        for w in ws:
            w["emphasis"] = False
            w.pop("reason", None)
        slots = 2 if len(ws) >= 5 else 1
        used = 0
        for w in ws:
            if bare(w["text"]) in wanted:
                w["emphasis"], w["reason"] = True, "asked for with --emphasis-words"
                used += 1
        if mode != "off" and used < slots:
            cands = []
            for j, w in enumerate(ws):
                if w["emphasis"]:
                    continue
                score, reason = classify(flat, at + j, names, starts)
                if mode == "numbers" and reason not in ("price", "percentage", "year", "number", "count"):
                    continue
                if reason and not number_kind(w["text"]):
                    score -= 2.0 * seen.get(key(w["text"]), 0)  # the third "India" is not news any more
                if score >= 5:
                    cands.append((score, -j, j, reason))
            cands.sort(reverse=True)
            for score, _, j, reason in cands:
                if used >= slots:
                    break
                # two neighbours share one slot only when they are one name ("New Delhi")
                ws[j]["emphasis"], ws[j]["reason"] = True, reason
                used += 1
                if reason.startswith("name") and j + 1 < len(ws) and not ws[j + 1]["emphasis"]:
                    s2, r2 = classify(flat, at + j + 1, names, starts)
                    if r2 and r2.startswith("name") and not SENTENCE_END.search(ws[j]["text"]):
                        ws[j + 1]["emphasis"], ws[j + 1]["reason"] = True, r2
            if mode == "auto" and used == 0 and quiet >= 2:
                # nothing certain here or on the page before: guess the longest content word, so a stretch
                # without numbers or names still gets a highlight now and then
                best = max(((guess_score(w["text"]), -j, j) for j, w in enumerate(ws)), default=(0, 0, 0))
                if best[0] >= 4.0 and seen.get(key(ws[best[2]]["text"]), 0) == 0:
                    ws[best[2]]["emphasis"], ws[best[2]]["reason"] = True, "long word (a guess)"
        hit = False
        for w in ws:
            if w["emphasis"]:
                seen[key(w["text"])] = seen.get(key(w["text"]), 0) + 1
                hit = True
        quiet = 0 if hit else quiet + 1
        at += len(ws)
    return pages


RULE_REASONS = ("name", "name (acronym)", "contrast word", "count", "long word (a guess)")


def big_words(pages, behind_cfg, duration_ms):
    """Pick the beats drawn large behind the person: emphasis words, spaced out, held long enough to read.

    When two candidates are too close together the more important one stays: numbers and prices first, then
    words picked by hand, then names and the other rule picks, and guesses last.
    """
    max_big = int(behind_cfg.get("maxBigWords", 2))
    min_hold = int(behind_cfg.get("minHoldMs", 700))
    min_gap = int(behind_cfg.get("minGapMs", 250))
    max_chars = int(behind_cfg.get("maxChars", 11))
    every_ms = int(behind_cfg.get("everyMs", 1400))
    flat = [w for p in pages for w in p["words"]]

    def rank(w):
        if number_kind(w["text"]):
            return 3
        r = w.get("reason") or ""
        if r.endswith("(a guess)"):
            return 0
        return 1 if r in RULE_REASONS else 2

    kinds = behind_cfg.get("kinds")  # optional: only these kinds of word go big ("number", "name", "word")
    numbers_behind = bool(behind_cfg.get("numbersBehind"))  # a style built for numerals draws them behind too
    min_words = int(behind_cfg.get("minWords", 1))

    def kind_of(group):
        if any(number_kind(g["text"]) for g in group):
            return "number"
        return "name" if any((g.get("reason") or "").startswith("name") for g in group) else "word"

    def clean(g):
        return re.sub(r"^[^\w$₹€£]+|[^\w%]+$", "", g["text"])

    cands = []
    i = 0
    while i < len(flat):
        w = flat[i]
        if w.get("emphasis"):
            group = [w]
            while len(group) < max_big and i + 1 < len(flat) and flat[i + 1].get("emphasis") and \
                    len(" ".join(bare(g["text"]) for g in group + [flat[i + 1]])) <= max_chars:
                group.append(flat[i + 1])
                i += 1
            text = " ".join(clean(g) for g in group)
            if text and len(text) <= max_chars and len(group) >= min_words and (not kinds or kind_of(group) in kinds):
                start = group[0]["startMs"]
                b = {"text": text, "startMs": start, "endMs": max(group[-1]["endMs"], start + min_hold)}
                if any(number_kind(g["text"]) for g in group) and not numbers_behind:
                    b["front"] = True  # a number must stay fully readable: drawn in front of the speaker, never behind
                cands.append((max(rank(g) for g in group), b))
        i += 1
    out = []
    for _, b in sorted(cands, key=lambda c: (-c[0], c[1]["startMs"])):
        if all(abs(b["startMs"] - o["startMs"]) >= every_ms for o in out):
            out.append(b)
    out.sort(key=lambda b: b["startMs"])
    for a, b in zip(out, out[1:]):
        a["endMs"] = min(a["endMs"], b["startMs"] - min_gap)
    if out:
        out[-1]["endMs"] = min(out[-1]["endMs"], duration_ms)
    return [b for b in out if b["endMs"] - b["startMs"] >= 300]


def finalise(cap, style):
    """Refresh what follows from the emphasis flags: page holds, and the giant words of behind styles."""
    pages = cap["pages"]
    fps = float(cap["video"].get("fps") or 30)
    frame = 1000.0 / fps
    dur = cap["video"]["durationMs"]
    for i, p in enumerate(pages):
        if not any(w.get("emphasis") for w in p["words"]):
            continue
        nxt = pages[i + 1]["startMs"] if i + 1 < len(pages) else dur
        want = min(p["words"][-1]["endMs"] + MAX_HOLD_MS, nxt)
        want = int(want // frame * frame + 1e-6)  # on the frame grid, never into the next page
        if want > p["endMs"]:
            p["endMs"] = want
    behind = (style or {}).get("behind") or {}
    if behind.get("enabled"):
        cap["big"] = big_words(pages, behind, dur)
        try:
            from shots import mark_bigs  # per-shot subject data (scripts/shots.py), when the captions carry it
            mark_bigs(cap)
        except ImportError:
            pass
    return cap


def find_word(page, token):
    """A word of a page by its text ("$5,000", "gold") or, failing that, by its 0-based index."""
    want = bare(token)
    for j, w in enumerate(page["words"]):
        if want and bare(w["text"]) == want:
            return j
    if re.fullmatch(r"\d+", token.strip()) and int(token) < len(page["words"]):
        return int(token)
    part = [j for j, w in enumerate(page["words"]) if want and want in bare(w["text"])]
    return part[0] if len(part) == 1 else None  # "lakh" finds "₹1 lakh" when it is the only match


def show(cap):
    rows = []
    for i, p in enumerate(cap["pages"]):
        text = " ".join(f"[{w['text']}]" if w.get("emphasis") else w["text"] for w in p["words"])
        why = "; ".join(f"{w['text']}: {w.get('reason', 'no reason given')}" for w in p["words"] if w.get("emphasis"))
        rows.append(f"{i:3d}  {p['startMs'] / 1000:7.2f}s  {text}" + (f"      <- {why}" if why else ""))
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description="Pick or edit the highlighted words of a captions.json.")
    ap.add_argument("captions")
    ap.add_argument("--style", help="style name or path to a style JSON (needed for styles with a giant word)")
    ap.add_argument("--show", action="store_true", help="print every page with its highlighted words in [brackets] and the reasons")
    ap.add_argument("--mode", choices=MODES, help="run the rules again: auto, numbers (numbers only) or off (clear)")
    ap.add_argument("--words", default="", help='with --mode: words to force, e.g. "gold, $5,000"')
    ap.add_argument("--clear", action="store_true", help="remove every highlight before applying --pick")
    ap.add_argument("--pick", action="append", default=[], metavar="PAGE:WORD=reason",
                    help='highlight a word: "12:$5,000=the price" (WORD is the word as shown, or its 0-based position)')
    ap.add_argument("--drop", action="append", default=[], metavar="PAGE:WORD", help="remove one highlight")
    a = ap.parse_args()

    cap = json.load(open(a.captions))
    style = None
    if a.style:
        from pathlib import Path
        sp = Path(a.style) if a.style.endswith(".json") else Path(__file__).resolve().parent.parent / "styles" / f"{a.style}.json"
        style = json.loads(sp.read_text())
    changed = False
    if a.mode:
        rule_picks(cap["pages"], a.mode, split_words(a.words))
        changed = True
    if a.clear:
        for p in cap["pages"]:
            for w in p["words"]:
                w["emphasis"] = False
                w.pop("reason", None)
        changed = True
    errors = []
    for spec, on in [(s, True) for s in a.pick] + [(s, False) for s in a.drop]:
        left, _, reason = spec.partition("=") if on else (spec, "", "")
        pg, _, token = left.partition(":")
        if not pg.strip().isdigit() or int(pg) >= len(cap["pages"]) or not token.strip():
            errors.append(f"{spec!r}: write it as PAGE:WORD{'=reason' if on else ''}, with PAGE from --show")
            continue
        page = cap["pages"][int(pg)]
        j = find_word(page, token)
        if j is None:
            errors.append(f"{spec!r}: page {pg} is \"{' '.join(w['text'] for w in page['words'])}\"; no word {token.strip()!r} there (a word with $ needs single quotes around the whole --pick)")
            continue
        page["words"][j]["emphasis"] = on
        if on:
            page["words"][j]["reason"] = reason.strip() or "picked by hand"
        else:
            page["words"][j].pop("reason", None)
        changed = True
    if errors:
        sys.exit("emphasis.py: nothing was saved.\n - " + "\n - ".join(errors))
    for p in cap["pages"]:  # a flag without a reason came from a hand edit of the file
        for w in p["words"]:
            if w.get("emphasis") and not w.get("reason"):
                w["reason"] = "picked by hand"
            elif not w.get("emphasis"):
                w.pop("reason", None)
    finalise(cap, style)
    json.dump(cap, open(a.captions, "w"), ensure_ascii=False, indent=1)
    if a.show:
        print(show(cap))
    n = sum(1 for p in cap["pages"] for w in p["words"] if w.get("emphasis"))
    crowded = [i for i, p in enumerate(cap["pages"]) if sum(1 for w in p["words"] if w.get("emphasis")) > (2 if len(p["words"]) >= 5 else 1)]
    info = {"captions": a.captions, "pages": len(cap["pages"]), "highlighted": n, "big": len(cap.get("big", [])), "changed": changed}
    if crowded:
        info["warning"] = f"pages {crowded} have more highlights than fit (1 per page, 2 on pages of 5 words or more)"
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()

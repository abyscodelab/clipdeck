#!/usr/bin/env python3
"""Checks for scripts/group.py. Standard library only: python3 tests/test_group.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = ROOT / "tests" / "sample-words.json"


def group(style, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "captions.json"
        srt = Path(tmp) / "captions.srt"
        subprocess.run([sys.executable, str(ROOT / "scripts" / "group.py"), str(WORDS), "--style", str(ROOT / "styles" / f"{style}.json"),
                        "--out", str(out), "--srt", str(srt), *extra], check=True, capture_output=True)
        return json.loads(out.read_text()), srt.read_text()


def main():
    words = json.loads(WORDS.read_text())["words"]
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    for path in sorted((ROOT / "styles").glob("*.json")):
        style = json.loads(path.read_text())
        name = style["name"]
        for key in ("name", "label", "description", "engines", "font", "case", "size", "wideScale", "color", "position", "page", "anim"):
            check(key in style, f"{name}: style is missing '{key}'")
        check((ROOT / "fonts" / style["font"]["file"]).exists(), f"{name}: font file {style['font']['file']} is not in fonts/")
        cap, srt = group(path.stem)
        pages = cap["pages"]
        page_cfg = style["page"]
        check(sum(len(p["words"]) for p in pages) == len(words), f"{name}: words were lost or duplicated")
        if page_cfg.get("unit") == "line":  # music styles: the limits are per lyric line, and a page holds linesPerPage lines
            per_line = [sum(1 for w in p["words"] if w["line"] == ln) for p in pages for ln in set(w["line"] for w in p["words"])]
            check(all(n <= page_cfg["maxWords"] for n in per_line), f"{name}: a line has more than maxWords words")
            check(all(max(w["line"] for w in p["words"]) < page_cfg.get("linesPerPage", 1) for p in pages), f"{name}: too many lines on a page")
        else:
            check(all(len(p["words"]) <= page_cfg["maxWords"] for p in pages), f"{name}: a page has more than maxWords words")
            check(all(max(w["line"] for w in p["words"]) < page_cfg.get("maxLines", 1) for p in pages), f"{name}: too many lines on a page")
        check(all(p["endMs"] > p["startMs"] for p in pages), f"{name}: a page has no duration")
        check(all(a["endMs"] <= b["startMs"] for a, b in zip(pages, pages[1:])), f"{name}: pages overlap")
        check(all(p["startMs"] <= p["words"][0]["startMs"] + 45 for p in pages), f"{name}: a page starts after its first word")
        check(srt.count("-->") == len(pages), f"{name}: SRT has the wrong number of entries")
        if (style.get("behind") or {}).get("enabled"):
            check("big" in cap, f"{name}: captions have no 'big' list")
        check(style["anim"].get("type"), f"{name}: anim.type is missing")

    names = sorted(p.stem for p in (ROOT / "styles").glob("*.json"))
    check(names, "styles/ is empty")
    first = names[0]
    cap, _ = group(first, "--emphasis", "gold,Meera")
    flagged = [w["text"] for p in cap["pages"] for w in p["words"] if w["emphasis"]]
    check(flagged and all(t.strip(".,").lower() in ("gold", "meera") for t in flagged), f"--emphasis picked the wrong words: {flagged}")
    cap, _ = group(first, "--replace", "meera=Mira")
    check(any("Mira" in w["text"] for p in cap["pages"] for w in p["words"]), "--replace did not change the spelling")
    for name in names:
        style = json.loads((ROOT / "styles" / f"{name}.json").read_text())
        if (style.get("behind") or {}).get("enabled"):
            cap, _ = group(name, "--emphasis", "gold,three,won")
            if not style["behind"].get("kinds") and not style["behind"].get("minWords"):  # numeral and poster only take numbers/names or phrases
                check(len(cap.get("big", [])) >= 2, f"{name}: expected at least two big words")
            check(all(b["endMs"] - b["startMs"] >= 300 for b in cap.get("big", [])), f"{name}: a big word is on screen under 300 ms")

    if failures:
        print("FAILED")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print(f"ok: {len(list((ROOT / 'styles').glob('*.json')))} styles, grouping, emphasis, replace and SRT checks passed")


if __name__ == "__main__":
    main()

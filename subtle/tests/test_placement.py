#!/usr/bin/env python3
"""Checks for scripts/placement.py and scripts/cuts.py (pure logic, no video). Standard library only: python3 tests/test_placement.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cuts as C  # noqa: E402
import placement as P  # noqa: E402

WORDS = ROOT / "tests" / "sample-words.json"


def style(name="bottom", **pos):
    st = json.loads((ROOT / "styles" / f"{name}.json").read_text())
    st["position"].update(pos)
    return st


def word(t, s, e, line=0):
    return {"text": t, "startMs": s, "endMs": e, "line": line, "emphasis": False}


def main():
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # ---- flex ranges ----
    check(P.flex_range(style("bottom")) == (65.0, 84.0), "bottom: default flex is a band around y, kept above the lower edge")
    check(P.flex_range(style("bottom", flex=[60, 82])) == (60.0, 82.0), "explicit flex is used")
    check(P.flex_range(style("bottom", flex=0)) == (77.0, 77.0), "flex 0 is fixed")
    check(P.flex_range(style("bottom", flex=[80, 90])) == (77.0, 90.0), "the preset y is always inside the range")
    check(P.flex_range(style("keyword"))[0] == P.flex_range(style("keyword"))[1], "keyword keeps its own position")
    check(P.flex_range(style("singalong"))[0] == P.flex_range(style("singalong"))[1], "music styles are fixed")

    # ---- overlap scoring ----
    box = (0.2, 0.7, 0.6, 0.08)
    check(P.overlap_share(box, (0.0, 0.0, 1.0, 0.3)) == 0.0, "no overlap above the box")
    check(abs(P.overlap_share(box, (0.0, 0.7, 1.0, 0.04)) - 0.5) < 1e-9, "half the box covered by a strip over its top half")
    check(abs(P.overlap_share(box, (0.0, 0.0, 1.0, 1.0)) - 1.0) < 1e-9, "a box inside another is fully covered")
    face_low = {"faces": [(0.3, 0.66, 0.4, 0.2)], "hands": [], "person": []}
    check(P.conflict(box, [face_low]) > 1.0, "a face under the caption is a big conflict")
    check(P.conflict(box, [{"faces": [], "hands": [], "person": []}]) == 0.0, "no subject, no conflict")
    check(P.conflict(box, [{"faces": [], "hands": [(0.4, 0.69, 0.1, 0.1)]}]) > 0.0, "a hand under the caption counts")
    check(P.busy((0, 0.2, 1, 0.1), [{"person": [0.0] * 12 + [1.0] * 12}]) == 0.0, "the empty top half is not busy")
    check(P.busy((0, 0.9, 1, 0.1), [{"person": [0.0] * 12 + [1.0] * 12}]) == 1.0, "the full bottom half is busy")

    # ---- choosing y ----
    st = style("bottom", flex=[50, 84])
    page = {"words": [word("hello", 0, 400), word("there", 400, 800)]}
    size = P.caption_size(st, page, 720, 1280)
    check(0.1 < size[0] < 0.94 and 0.03 < size[1] < 0.2, f"caption box size is plausible, got {size}")
    lo, hi = P.flex_range(st)
    clear = {"faces": [], "hands": [], "person": [0.0] * 24}
    check(P.choose([clear], size, 0.5, lo, hi, 77.0) == 77.0 or abs(P.choose([clear], size, 0.5, lo, hi, 77.0) - 77.0) <= 1.0,
          "nothing in the way: stay at the preset y")
    # a chin and a hand in the lower third, clear above y=70
    face = {"faces": [(0.25, 0.55, 0.5, 0.2)], "hands": [], "person": [0.0] * 24}
    ys = P.choose([face], size, 0.5, lo, hi, 77.0)
    cap = (0.5 - size[0] / 2, ys / 100 - size[1] / 2, size[0], size[1])
    check(P.conflict(cap, [face]) <= P.TOLERANCE, f"chosen y {ys} is clear of the face")
    check(lo <= ys <= hi, "chosen y stays inside the range")
    boxed = {"faces": [(0.0, 0.0, 1.0, 1.0)], "hands": [], "person": []}
    check(lo <= P.choose([boxed], size, 0.5, lo, hi, 77.0) <= hi, "a face over everything still returns a y inside the range")
    # hysteresis: prev y kept when still clear, even if another y would be a little better
    busy_here = {"faces": [], "hands": [], "person": [0.9] * 24}
    check(P.choose([busy_here], size, 0.5, lo, hi, 77.0, prev_y=70.0) == 70.0, "the previous y is kept while it is clear")
    low_face = {"faces": [(0.25, 0.68, 0.5, 0.2)], "hands": [], "person": [0.0] * 24}
    moved = P.choose([low_face], size, 0.5, lo, hi, 77.0, prev_y=77.0)
    check(moved != 77.0, "the previous y is dropped when the subject moves under it")

    # ---- place_pages: stable across pages, re-decides at a cut ----
    pages = [{"startMs": i * 1000, "endMs": i * 1000 + 900, "words": [word("a", i * 1000, i * 1000 + 400), word("b", i * 1000 + 400, i * 1000 + 800)]} for i in range(6)]
    samples = [[low_face]] * 3 + [[clear]] * 3
    ys = P.place_pages(pages, samples, st, 720, 1280)
    check(ys[0] == ys[1] == ys[2] and ys[0] != 77.0, f"pages with the same subject share one y: {ys}")
    check(ys[3] == ys[2], f"once moved, a page stays put while it is still clear (no jitter): {ys}")
    ys_cut = P.place_pages(pages, samples, st, 720, 1280, cuts=[3000])
    check(abs(ys_cut[3] - 77.0) <= 1.0, f"after a cut the page is decided again, near the preset: {ys_cut}")
    ys_fixed = P.place_pages(pages, samples, style("bottom", flex=0), 720, 1280)
    check(set(ys_fixed) == {77.0}, "flex 0 never moves a page")

    # ---- cuts: picking ----
    check(C.pick([(2000, 0.6)], fps=24) == [2000], "a clear cut is kept (frame grid)")
    check(C.pick([(2000, 0.2)]) == [], "a low score is not a cut")
    check(C.pick([(3000, 0.7), (3125, 0.7)]) == [], "two cuts within 220 ms are a flash: both dropped")
    check(C.pick([(3000, 0.4), (3300, 0.9)]) == [3300], "two cuts closer than a shot: the stronger stays")
    check(C.pick([(100, 0.9)]) == [], "a 'cut' in the first frames is the video starting")

    # ---- cuts: splitting words into pages ----
    ws = [word("one", 0, 400), word("two", 400, 800), word("three", 800, 1200), word("four", 1200, 1600)]
    out = C.split_pages([ws], [1000])
    check([[w["text"] for w in p] for p in out] == [["one", "two", "three"], ["four"]] or len(out) == 2, "a page is split at a cut")
    check(all(not (min(w["endMs"] for w in p) < 1000 < max((w["startMs"] + w["endMs"]) / 2 for w in p)) for p in out), "no page holds words on both sides")
    ws = [word("one", 0, 600), word("two", 600, 1200), word("three", 1200, 1800), word("a", 1800, 1900)]
    out = C.split_pages([ws], [1500], min_ms=330, max_words=4, max_chars=40)
    check(len(out) == 2 and [w["text"] for w in out[1]] == ["three", "a"], "no cut inside a page: nothing changes except at the cut")
    ws1 = [word("so", 0, 300), word("this", 300, 700), word("is", 700, 1000)]
    ws2 = [word("big", 1050, 1400), word("news", 1400, 1800)]
    out = C.split_pages([ws1, ws2], [1030], max_words=5)
    check(len(out) == 2, "cut falls between two pages: they stay as they are")
    # a tiny remainder merges with the same-shot neighbour instead of flickering
    p1 = [word("what", 0, 400), word("a", 400, 500), word("crazy", 500, 900)]
    p2 = [word("day", 900, 1300), word("it", 1300, 1400), word("was", 1400, 1700)]
    out = C.split_pages([p1, p2], [1280], max_words=4)
    check(all(len(p) >= 2 for p in out[:-1]) or len(out) == 2, f"a tiny split-off piece joins its neighbour: {[[w['text'] for w in p] for p in out]}")
    # clamp: a page never runs across a cut, even when its words do not
    pg = [{"startMs": 0, "endMs": 1400, "words": [word("a", 0, 500), word("b", 500, 900)]}]
    C.clamp_pages(pg, [1000], 24)
    check(pg[0]["endMs"] <= 1000, "the hold after the last word is cut at the shot's end")
    pg = [{"startMs": 800, "endMs": 1800, "words": [word("a", 950, 1300), word("b", 1300, 1500)]}]
    C.clamp_pages(pg, [1000], 24)
    check(pg[0]["startMs"] >= 1000 - 1, "a page whose words sit in the new shot does not show before the cut")

    # ---- group.py end to end: cuts.json key, pages never straddle ----
    with tempfile.TemporaryDirectory() as tmp:
        outp = Path(tmp) / "c.json"
        cuts = [1500, 3300, 9000]
        subprocess.run([sys.executable, str(ROOT / "scripts" / "group.py"), str(WORDS), "--style", str(ROOT / "styles" / "glass.json"),
                        "--out", str(outp), "--cuts", ",".join(map(str, cuts))], check=True, capture_output=True)
        cap = json.loads(outp.read_text())
        check(cap.get("cuts") == cuts, "captions.json carries `cuts`")
        for p in cap["pages"]:
            lo, hi = C.shot_bounds(cuts, (p["words"][0]["startMs"] + p["words"][0]["endMs"]) / 2)
            ok = p["startMs"] >= lo - 1 and (hi is None or p["endMs"] <= hi + 1)
            mids = {C.bisect.bisect_right(cuts, (w["startMs"] + w["endMs"]) / 2) for w in p["words"]}
            check(ok and len(mids) == 1, f"page {p['startMs']}-{p['endMs']} stays inside one shot")
        check(all(a["endMs"] <= b["startMs"] + 1 for a, b in zip(cap["pages"], cap["pages"][1:])), "pages still do not overlap")
        plain = Path(tmp) / "p.json"
        subprocess.run([sys.executable, str(ROOT / "scripts" / "group.py"), str(WORDS), "--style", str(ROOT / "styles" / "glass.json"), "--out", str(plain)],
                       check=True, capture_output=True)
        check("cuts" not in json.loads(plain.read_text()), "no cuts, no `cuts` key")

    if failures:
        print("FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("placement and cuts checks passed")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Hard cuts: find them with ffmpeg and keep caption pages from straddling them.

    python3 scripts/cuts.py video.mp4 [--out cuts.json] [--threshold 0.34]

Prints (and optionally writes) {"cuts": [ms, ...], "candidates": n}. A cut is the time of the first frame of the new
shot. group.py imports `split_pages` and `clamp_pages`; scripts/subtle.py calls `detect`. Standard library only.
"""
import argparse
import bisect
import json
import re
import subprocess
import sys

# ffmpeg's scene score is 0..1 (share of the picture that changed). On the test footage, cuts between shots of the same
# person against the same room (jump cuts) scored 0.34 to 0.42, cuts to a new scene 0.5 to 0.95, and a person gesturing,
# leaning in or turning stayed under 0.2 (the odd flash or whip pan jumps higher: see FLASH_MS).
THRESHOLD = 0.30
FLASH_MS = 220      # two cuts closer than this are a flash or a strobe, not an edit: both are dropped
MIN_SHOT_MS = 350   # a shot shorter than this is not an edit either: the stronger cut of the pair stays


def detect(video, threshold=THRESHOLD, fps=None):
    """Cut times in ms (on the frame grid when fps is given), after dropping flashes and over-close pairs."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
           f"scale=320:-2,select='gt(scene,{min(threshold, 0.2)})',metadata=print:file=-", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    cand, t = [], None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"scene_score=([\d.]+)", line)
        if m and t is not None:
            cand.append((t * 1000.0, float(m.group(1))))
            t = None
    return pick(cand, threshold, fps)


def pick(cand, threshold=THRESHOLD, fps=None):
    """Pure part of detect: [(ms, score)] -> cut times."""
    cand = sorted(c for c in cand if c[1] >= threshold)
    drop = set()
    for i in range(1, len(cand)):
        if cand[i][0] - cand[i - 1][0] < FLASH_MS:
            drop.update((i - 1, i))
    cand = [c for i, c in enumerate(cand) if i not in drop]
    kept = []
    for ms, sc in cand:
        if kept and ms - kept[-1][0] < MIN_SHOT_MS:
            if sc > kept[-1][1]:
                kept[-1] = (ms, sc)
            continue
        kept.append((ms, sc))
    out = []
    for ms, _ in kept:
        if ms < MIN_SHOT_MS:  # a "cut" in the first frames is just the video starting
            continue
        out.append(int(round(round(ms * fps / 1000.0) * 1000.0 / fps)) if fps else int(round(ms)))
    return out


def shot_bounds(cuts, ms):
    """(start, end) of the shot holding time `ms`; end is None for the last shot."""
    k = bisect.bisect_right(cuts, ms)
    return (cuts[k - 1] if k else 0), (cuts[k] if k < len(cuts) else None)


def _mid(w):
    return (w["startMs"] + w["endMs"]) / 2.0


def split_pages(pages, cuts, min_ms=330, max_words=4, max_chars=40):
    """Split word-list pages at cuts. `pages` is a list of lists of word dicts (startMs/endMs/text).

    A word belongs to the shot holding its midpoint. A page whose words sit in two shots becomes one page per shot.
    A tiny fragment (one short word) joins the neighbouring page of the same shot when that page has room, so a cut
    never leaves a one-word flicker next to a page that could have taken the word.
    """
    if not cuts:
        return pages
    shot = lambda w: bisect.bisect_right(cuts, _mid(w))  # noqa: E731
    frags = []  # (words, shot)
    for p in pages:
        run = [p[0]]
        for w in p[1:]:
            if shot(w) != shot(run[-1]):
                frags.append((run, shot(run[0])))
                run = []
            run.append(w)
        frags.append((run, shot(run[0])))

    def tiny(ws):
        return len(ws) == 1 and (ws[0]["endMs"] - ws[0]["startMs"] < min_ms or len(ws[0]["text"]) <= 3)

    def fits(a, b):
        return len(a) + len(b) <= max_words and len(" ".join(x["text"] for x in a + b)) <= max_chars

    i = 0
    while i < len(frags):
        ws, sh = frags[i]
        is_split_piece = (i > 0 and frags[i - 1][1] != sh and _same_origin(pages, frags[i - 1][0], ws)) or \
                         (i + 1 < len(frags) and frags[i + 1][1] != sh and _same_origin(pages, ws, frags[i + 1][0]))
        if is_split_piece and tiny(ws):
            if i > 0 and frags[i - 1][1] == sh and fits(frags[i - 1][0], ws):
                frags[i - 1] = (frags[i - 1][0] + ws, sh)
                del frags[i]
                continue
            if i + 1 < len(frags) and frags[i + 1][1] == sh and fits(ws, frags[i + 1][0]):
                frags[i + 1] = (ws + frags[i + 1][0], sh)
                del frags[i]
                continue
        i += 1
    return [f[0] for f in frags]


def _same_origin(pages, a, b):
    """True when the last word of a and the first word of b were on one original page."""
    for p in pages:
        if any(w is a[-1] for w in p):
            return any(w is b[0] for w in p)
    return False


def clamp_pages(pages, cuts, fps):
    """Pull every page's start and end inside the shot its first word belongs to. Pages are caption-page dicts."""
    if not cuts:
        return pages
    frame = 1000.0 / fps
    snap = lambda x: int(round(round(x / frame) * frame))  # noqa: E731
    for p in pages:
        lo, hi = shot_bounds(cuts, _mid(p["words"][0]))
        if p["startMs"] < lo:
            p["startMs"] = snap(lo)
        if hi is not None and p["endMs"] > hi:
            p["endMs"] = snap(hi)
        if p["endMs"] <= p["startMs"]:
            p["endMs"] = snap(p["startMs"] + frame)
    return pages


def main():
    ap = argparse.ArgumentParser(description="Detect hard cuts with ffmpeg.")
    ap.add_argument("video")
    ap.add_argument("--out")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--fps", type=float)
    a = ap.parse_args()
    try:
        res = {"cuts": detect(a.video, a.threshold, a.fps)}
    except RuntimeError as e:  # cut detection is optional: report and carry on with no cuts
        res = {"cuts": [], "error": str(e)}
    if a.out:
        json.dump(res, open(a.out, "w"))
    print(json.dumps(res))


if __name__ == "__main__":
    sys.exit(main())

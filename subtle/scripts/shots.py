#!/usr/bin/env python3
"""Per-shot subject data for "behind the speaker" styles: where the person is in each shot, and whether text fits behind.

    python3 scripts/shots.py video.mp4 captions.json --style styles/cover.json [--out captions.json]

A close-up fills the frame, so a giant word behind the speaker would be hidden; a wide shot leaves room. The decision is
made per shot (the shots are the spans between `cuts`), not for the whole video. For every shot this samples the picture with
scripts/vision-subject (Apple Vision, macOS; the same cached samples as placement.py) and writes `shots` into captions.json:

    "shots": [ {"startMs": 0, "endMs": 23700, "person": 1.0,
                "bands": [0, 0, 0.31, 0.33, 0.3, 0.52, 1.0, ...],   # 24 values: share of each horizontal band the person covers
                "face": [0.22, 0.09, 0.2, 0.11],                      # [x, y, w, h] of the largest face, fractions; absent without one
                "behind": true, "y": 17.5, "cover": 0.31} ]           # a band the size of the style's word sits at y% of the height
    "subject": [ {"ms": 0, "bands": [...24], "face": [x, y, w, h]}, ... ]   # the same data every 400 ms: a word is placed where the person is while it is up

and marks each giant word (`big`): in a shot where nothing fits behind the person the word gets `front: true` (the style
draws it in front, smaller, or skips it). `emphasis.py` repeats the marking whenever it rebuilds `big`, from the saved `shots`.
Standard library only; without macOS (vision-subject) nothing is written and the style behaves as before.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BANDS = 24
TARGET = 0.30      # the person should cover about this share of the word's band (a head in front of a word, both ends clear)
MIN_COVER = 0.06   # less than this: nothing is in front of the word, it floats (fine, but the effect is lost)
MAX_COVER = 0.45   # more than this: the word is mostly hidden
ROW_MAX = 0.55     # no row of the word may be covered more than this (a head in a close-up spans most of the width)
MIN_SHOT_MS = 700
SAMPLES = 7
SUBJECT_EVERY_MS = 400


def shots_from_cuts(cuts, duration_ms):
    edges = [0] + [int(c) for c in sorted(cuts) if 0 < int(c) < duration_ms] + [int(duration_ms)]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]


def sample_times_for(shot, fps):
    a, b = shot
    pad = min(200, (b - a) // 4)
    lo, hi = a + pad, max(a + pad, b - pad - int(1000 / fps))
    n = max(2, min(SAMPLES + (b - a) // 5000, 12)) if b - a >= 1500 else 2 if b - a >= 700 else 1
    if n == 1:
        return [int((a + b) / 2)]
    return sorted({int(lo + (hi - lo) * k / (n - 1)) for k in range(n)})


def window_cover(bands, c, h):
    """Mean person share over the window of height h (fraction) centred at c (fraction)."""
    n = len(bands)
    top, bot = max(0.0, c - h / 2) * n, min(1.0, c + h / 2) * n
    tot = wsum = 0.0
    for i in range(int(top), min(n, int(bot) + 1)):
        w = min(i + 1, bot) - max(i, top)
        if w > 0:
            tot += bands[i] * w
            wsum += w
    return tot / wsum if wsum else 0.0


def window_max(bands, c, h):
    n = len(bands)
    top, bot = max(0.0, c - h / 2) * n, min(1.0, c + h / 2) * n
    return max((bands[i] for i in range(int(top), min(n, int(bot) + 1)) if min(i + 1, bot) - max(i, top) > 0.25), default=0.0)


def best_window(bands, h, lo=0.0, hi=0.7, target=TARGET):
    """(y fraction, cover) where a word of height h fraction should sit so the person covers about TARGET of it."""
    best = None
    y = max(lo, h / 2 + 0.02)
    while y <= min(hi, 0.98 - h / 2) + 1e-9:
        cov = window_cover(bands, y, h)
        cost = abs(cov - target) + 0.02 * y + (1.0 if window_max(bands, y, h) > ROW_MAX else 0.0)  # ties go higher: more headroom, less body
        if best is None or cost < best[0] - 1e-9:
            best = (cost, y, cov)
        y += 0.005
    return (best[1], best[2]) if best else (0.3, 1.0)


def analyse_shot(shot, frames, band_h, target=TARGET):
    """One entry of `shots` from the sampled frames of that shot."""
    a, b = shot
    seen = [f for f in frames if f.get("person") and max(f["person"]) > 0.04]
    out = {"startMs": a, "endMs": b, "samples": len(frames), "person": round(len(seen) / len(frames), 2) if frames else 0.0}
    if not seen:
        out.update(behind=False, reason="no person")
        return out
    n = len(seen[0]["person"])
    mean = [sum(f["person"][i] for f in seen) / len(seen) for i in range(n)]
    out["bands"] = [round(v, 2) for v in mean]
    faces = [max(f["faces"], key=lambda r: r[2] * r[3]) for f in seen if f.get("faces")]
    if faces:  # the median box over the samples: one wave of the head does not move it
        out["face"] = [round(sorted(r[k] for r in faces)[len(faces) // 2], 3) for k in range(4)]
    y, cov = best_window(mean, band_h, target=target)
    out["y"], out["cover"] = round(y * 100, 1), round(cov, 2)
    if b - a < MIN_SHOT_MS:
        out.update(behind=False, reason="shot too short")
    elif len(seen) / len(frames) < 0.6:
        out.update(behind=False, reason="the person is in under 60% of the samples")
    elif not (MIN_COVER <= cov <= MAX_COVER) or window_max(mean, y, band_h) > ROW_MAX:
        out.update(behind=False, reason="nothing in front of the word" if cov < MIN_COVER else f"the person fills the word's place (up to {int(window_max(mean, y, band_h) * 100)}% of a row): a close-up")
    else:
        out["behind"] = True
    return out


def subject_entry(t, f):
    e = {"ms": t, "bands": [round(v, 2) for v in (f.get("person") or [])]}
    if f.get("faces"):
        e["face"] = [round(v, 3) for v in max(f["faces"], key=lambda r: r[2] * r[3])]
    return e


def shot_at(shots, ms):
    for s in shots or []:
        if s["startMs"] <= ms < s["endMs"]:
            return s
    return None


def mark_bigs(cap):
    """Mark every giant word: `front: true` in a shot where nothing fits behind the person. Pure; needs only `shots`."""
    shots = cap.get("shots")
    if not shots:
        return cap
    for b in cap.get("big") or []:
        s = shot_at(shots, b["startMs"] + 40)
        if b.get("close") and (s is None or s.get("behind")):
            b.pop("front", None)
            b.pop("close", None)
        if s is not None and not s.get("behind") and not b.get("front"):
            b["front"] = True
            b["close"] = True  # in front only because of the shot, not by the style's rule (a number)
    return cap


def band_height(style):
    b = style.get("behind") or {}
    if b.get("bandHeight"):
        return float(b["bandHeight"])
    return (float(b.get("bigSize", 14)) + float(b.get("bigMaxSize", 24))) / 200.0


def apply(video, cap, style, cache_dir=None):
    """Write `shots` into the captions dict and mark the big words. Returns (notes, shots). Raises RuntimeError without the tool."""
    import placement as pl
    if pl.ensure_tool() is None:
        raise RuntimeError("needs macOS with the Xcode command line tools (vision-subject)")
    fps = float(cap["video"].get("fps") or 30)
    dur = cap["video"]["durationMs"]
    spans = shots_from_cuts(cap.get("cuts") or [], dur)
    per = [sample_times_for(s, fps) for s in spans]
    tl = list(range(0, int(dur - 1000 / fps), SUBJECT_EVERY_MS))  # a timeline for placing each word where the person is at that moment
    got = pl.subject_frames(video, sorted({t for ts in per for t in ts} | set(tl)), cache_dir)
    h = band_height(style)
    tgt = float((style.get('behind') or {}).get('target', TARGET))
    shots = [analyse_shot(s, [got[t] for t in ts if t in got], h, tgt) for s, ts in zip(spans, per)]
    cap["shots"] = shots
    cap["subject"] = [subject_entry(t, got[t]) for t in tl if t in got]
    mark_bigs(cap)
    ok = sum(1 for s in shots if s.get("behind"))
    notes = [f"behind the speaker: {ok} of {len(shots)} shots leave room for the word; the others draw it in front"]
    return notes, shots


def main():
    ap = argparse.ArgumentParser(description="Per-shot subject data for behind-the-speaker styles.")
    ap.add_argument("video")
    ap.add_argument("captions")
    ap.add_argument("--style", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    cap = json.load(open(a.captions))
    style = json.load(open(a.style))
    try:
        notes, shots = apply(a.video, cap, style)
    except RuntimeError as e:
        sys.exit(f"shots.py: {e}")
    json.dump(cap, open(a.out or a.captions, "w"), ensure_ascii=False, indent=1)
    for s in shots:
        print(f"{s['startMs'] / 1000:6.2f}-{s['endMs'] / 1000:6.2f}s  behind={s.get('behind')}  y={s.get('y')}  cover={s.get('cover')}  {s.get('reason', '')}", file=sys.stderr)
    print(json.dumps({"notes": notes, "shots": len(shots), "behind": sum(1 for s in shots if s.get("behind"))}))


if __name__ == "__main__":
    main()

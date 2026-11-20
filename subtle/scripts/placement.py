#!/usr/bin/env python3
"""Subject-aware caption placement: keep captions off the face and the hands, and move them only when they must.

    python3 scripts/placement.py video.mp4 captions.json --style styles/glass.json [--out captions.json]

Samples the picture (faces, hands, how much of each horizontal band the person fills) with scripts/vision-subject
(Apple Vision, macOS), then writes `pages[i].y` (percent of the frame height) into captions.json. The renderer reads it
instead of the style's `position.y`. The style may allow a range with `position.flex: [low, high]` (0 = fixed).
Standard library only; the Vision tool is optional (without it every page keeps the style's y).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "vision-subject" / ".build" / "vision-subject"
CACHE_VERSION = 1
BANDS = 24

# A style whose caption does not sit at position.y (it flows from the top, fills the frame, or is placed by its own
# logic) keeps its own place.
FIXED_TYPES = {"chalkline", "downbeat", "billboard", "singalong", "keyword"}

FACE_MARGIN = (0.025, 0.035)  # (x, y) growth of a face box, as a fraction of the frame: hair, chin, a shrug
HAND_MARGIN = (0.03, 0.04)    # hands hold the product: the box is grown so the thing in the hand is clear too
TOLERANCE = 0.01              # a caption box overlapped by less than this share of its area is "clear"


# ---------- geometry (pure) ----------
def flex_range(style):
    """Allowed (low, high) for the caption centre in % of height. `position.flex` = [low, high] or 0 (fixed)."""
    pos = style.get("position") or {}
    y = float(pos.get("y", 50))
    if (style.get("anim") or {}).get("type") in FIXED_TYPES or style.get("group") == "music":
        return y, y
    flex = pos.get("flex", None)
    if flex is None:
        lo, hi = max(10.0, y - 12.0), min(max(84.0, y), y + 12.0)
    elif not flex:
        return y, y
    else:
        lo, hi = float(flex[0]), float(flex[1])
    lo, hi = min(lo, y), max(hi, y)  # the preferred y is always allowed
    return lo, hi


def caption_size(style, page, frame_w, frame_h):
    """Approximate caption box (width, height) as fractions of the frame."""
    pos = style.get("position") or {}
    wide = frame_w > frame_h
    scale = float(style.get("wideScale", 1.35)) if wide else 1.0
    size = float(style.get("size", 4)) / 100.0 * frame_h * scale  # px
    lh = float(style.get("lineHeight", 1.15))
    ws = page["words"]
    lines = {}
    for w in ws:
        lines.setdefault(min(int(w.get("line", 0)), 3), []).append(w["text"])
    n_lines = max(1, len(lines))
    anim = style.get("anim") or {}
    cont = style.get("container") or {}
    char_w = 0.68 if style.get("case") == "upper" else 0.58
    if anim.get("type") == "stack":  # one word per row down a diagonal pile
        n_lines, lh = len(ws), anim.get("pitch", 1.08) * 0.72
        longest = max(len(w["text"]) for w in ws)
        width = min(float(anim.get("pileWidth", 50)) / 100.0, longest * size * 1.0 * 0.62 / frame_w + 0.1)
    else:
        longest = max(len(" ".join(t)) for t in lines.values())
        width = longest * size * char_w / frame_w + 2 * float(cont.get("padX", 0)) * size / frame_w
        if anim.get("type") == "sticker":
            lh = float(cont.get("height", 1.5)) * 1.05
    width = min(width, 1.0 - 2 * float(pos.get("marginX", 6)) / 100.0)
    height = (n_lines * size * lh + 2 * float(cont.get("padY", 0.3 if cont else 0)) * size) / frame_h
    return width, height


def overlap_share(box, other):
    """Share of `box` (x, y, w, h) covered by `other`."""
    ix = max(0.0, min(box[0] + box[2], other[0] + other[2]) - max(box[0], other[0]))
    iy = max(0.0, min(box[1] + box[3], other[1] + other[3]) - max(box[1], other[1]))
    return ix * iy / max(1e-9, box[2] * box[3])


def grow(b, m):
    return (b[0] - m[0], b[1] - m[1], b[2] + 2 * m[0], b[3] + 2 * m[1])


def conflict(box, frames):
    """Penalty for a caption box against the subject in the sampled frames (averaged over the samples)."""
    if not frames:
        return 0.0
    total = 0.0
    for f in frames:
        c = 0.0
        for fb in f.get("faces", []):
            c += 3.0 * overlap_share(box, grow(fb, FACE_MARGIN))
        for hb in f.get("hands", []):
            c += 2.0 * overlap_share(box, grow(hb, HAND_MARGIN))
        total += c
    return total / len(frames)


def busy(box, frames):
    """How much of the picture the person fills in the rows the box covers (0..1): the emptier band reads better."""
    vals = []
    for f in frames:
        per = f.get("person") or []
        if not per:
            continue
        a = max(0, int(box[1] * len(per)))
        b = min(len(per), max(a + 1, int((box[1] + box[3]) * len(per) + 0.999)))
        seg = per[a:b]
        if seg:
            vals.append(sum(seg) / len(seg))
    return sum(vals) / len(vals) if vals else 0.0


def choose(frames, size, cx, lo, hi, y_pref, prev_y=None, step=1.0):
    """Best y (percent) in [lo, hi] for one page. `prev_y` is kept when it is still clear (hysteresis)."""
    w, h = size
    if lo >= hi:
        return float(y_pref)

    def box_at(y):
        return (cx - w / 2, y / 100.0 - h / 2, w, h)

    if prev_y is not None and lo - 1e-6 <= prev_y <= hi + 1e-6 and conflict(box_at(prev_y), frames) <= TOLERANCE:
        return prev_y
    ref = prev_y if prev_y is not None else y_pref
    best, best_cost = float(y_pref), None
    y = lo
    while y <= hi + 1e-6:
        b = box_at(y)
        if b[1] >= 0.03 and b[1] + b[3] <= 0.96 or abs(y - y_pref) < 1e-6:  # on the frame (the preset's own y always is)
            cost = 100.0 * conflict(b, frames) + 0.25 * busy(b, frames) + 0.01 * abs(y - ref)
            if best_cost is None or cost < best_cost - 1e-9:
                best, best_cost = y, cost
        y += step
    return round(best * 2) / 2.0


def place_pages(pages, samples, style, frame_w, frame_h, cuts=()):
    """Decide y for every page. `samples[i]` is the list of sampled frames for page i. Returns a list of y."""
    lo, hi = flex_range(style)
    y_pref = float((style.get("position") or {}).get("y", 50))
    cx = float((style.get("position") or {}).get("x", 50)) / 100.0
    out, prev_y, prev_start = [], None, None
    import bisect
    for p, frames in zip(pages, samples):
        shot = bisect.bisect_right(list(cuts), (p["words"][0]["startMs"] + p["words"][0]["endMs"]) / 2.0)
        new_shot = prev_start is not None and shot != prev_start
        size = caption_size(style, p, frame_w, frame_h)
        y = choose(frames, size, cx, lo, hi, y_pref, None if (new_shot or prev_y is None) else prev_y)
        out.append(y)
        prev_y, prev_start = y, shot
    return out


# ---------- sampling (Vision) ----------
def sample_times(pages, cuts, duration_ms, fps):
    """Times (ms) to look at: three per page and the first frames of every shot."""
    frame = 1000.0 / fps
    per_page = []
    for p in pages:
        s, e = p["startMs"], max(p["endMs"] - frame, p["startMs"])
        per_page.append([int(min(duration_ms - frame, s + (e - s) * k)) for k in (0.15, 0.5, 0.85)])
    extra = [int(min(duration_ms - frame, c + 2 * frame)) for c in cuts]
    return per_page, extra


def video_key(video):
    h = hashlib.sha256()
    with open(video, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def run_tool(video, times_ms, bands=BANDS):
    if not times_ms:
        return {}
    cmd = [str(TOOL), "sample", str(video), "--times", ",".join(f"{t / 1000.0:.3f}" for t in times_ms), "--bands", str(bands)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("vision-subject failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    data = json.loads(r.stdout)
    return {round(f["t"] * 1000): f for f in data["frames"]}


def ensure_tool():
    """Path of the built tool, building it when needed. None when this is not macOS or the build fails."""
    if sys.platform != "darwin":
        return None
    if not TOOL.exists():
        r = subprocess.run(["bash", str(HERE / "vision-subject" / "build.sh")], capture_output=True, text=True)
        if r.returncode != 0 or not TOOL.exists():
            return None
    return TOOL


def subject_frames(video, times_ms, cache_dir=None):
    """{ms: frame} for the times, from the cache when it has them. The cache lives next to the transcript cache."""
    cdir = Path(cache_dir or os.environ.get("SUBTLE_CACHE", str(Path.home() / ".cache" / "subtle"))) / video_key(video)
    cdir.mkdir(parents=True, exist_ok=True)
    path = cdir / f"subject.v{CACHE_VERSION}.json"
    have = {}
    if path.exists():
        try:
            have = {int(k): v for k, v in json.loads(path.read_text()).items()}
        except ValueError:
            have = {}
    need = sorted({int(t) for t in times_ms} - set(have))
    if need:
        for i in range(0, len(need), 60):
            got = run_tool(video, need[i:i + 60])
            for t in need[i:i + 60]:
                f = got.get(t)
                if f is not None:
                    have[t] = f
        path.write_text(json.dumps({str(k): v for k, v in have.items()}))
    return {int(t): have[int(t)] for t in times_ms if int(t) in have}


def apply(video, cap, style, cuts=(), cache_dir=None):
    """Write pages[i].y into the captions dict. Returns (notes, report) or raises RuntimeError."""
    pages = cap["pages"]
    vw, vh = cap["video"]["width"], cap["video"]["height"]
    fps = float(cap["video"].get("fps") or 30)
    lo, hi = flex_range(style)
    if lo >= hi:
        return ["placement: this style keeps its own position"], {"moved": 0}
    per_page, extra = sample_times(pages, cuts, cap["video"]["durationMs"], fps)
    got = subject_frames(video, sorted({t for ts in per_page for t in ts} | set(extra)), cache_dir)
    samples = [[got[t] for t in ts if t in got] for ts in per_page]
    ys = place_pages(pages, samples, style, vw, vh, cuts)
    for p, y in zip(pages, ys):
        p["y"] = y
    pref = float((style.get("position") or {}).get("y", 50))
    moved = sum(1 for y in ys if abs(y - pref) > 0.01)
    changes = sum(1 for a, b in zip(ys, ys[1:]) if a != b)
    seen = sum(1 for s in samples for f in s if f.get("faces") or f.get("hands"))
    return [], {"pages": len(pages), "moved": moved, "changes": changes, "range": [lo, hi], "samplesWithSubject": seen}


def main():
    ap = argparse.ArgumentParser(description="Place caption pages around the face and hands.")
    ap.add_argument("video")
    ap.add_argument("captions")
    ap.add_argument("--style", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    cap = json.load(open(a.captions))
    style = json.load(open(a.style))
    if ensure_tool() is None:
        sys.exit("placement.py: needs macOS with the Xcode command line tools (vision-subject)")
    notes, rep = apply(a.video, cap, style, cap.get("cuts") or [])
    json.dump(cap, open(a.out or a.captions, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"notes": notes, **rep}))


if __name__ == "__main__":
    main()

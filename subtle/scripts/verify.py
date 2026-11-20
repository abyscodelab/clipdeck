#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "pillow"]
# ///
"""Check a captioned video and build a contact sheet to look at.

    uv run scripts/verify.py --video out.mp4 --source in.mp4 --captions captions.json --style styles/glide.json \
        --overlay overlay.mov [--behind overlay-behind.mov --matte matte.mp4] --out preview.jpg

Checks: captions are drawn, they sit inside the safe area, the text has enough contrast, and in behind mode
at least 55% of each big word is still visible next to the person. Prints one JSON object.
"""
import argparse
import json
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw


def grab(path, t, pix, w, h):
    ch = {"rgb24": 3, "rgba": 4, "gray": 1}[pix]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1",
                          "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", pix, "-"], capture_output=True).stdout
    if len(raw) < w * h * ch:
        return None
    a = np.frombuffer(raw[: w * h * ch], dtype=np.uint8).reshape(h, w, ch)
    return a[:, :, 0] if ch == 1 else a


def lum(rgb):
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def safe_box(w, h):
    """Left, top, right, bottom as fractions. Vertical video leaves room for app buttons and captions UI."""
    if h > w:
        return 0.05, 0.12, 0.95, 0.80
    return 0.04, 0.05, 0.96, 0.94


def big_visibility(b, behind, matte, W, H):
    """Share of a big word's pixels that the person does not cover, at the word's midpoint. None if unreadable."""
    t = (b["startMs"] + b["endMs"]) / 2000.0
    ov = grab(behind, t, "rgba", W, H)
    m = grab(matte, t, "gray", W, H)
    if ov is None or m is None:
        return None
    al = ov[:, :, 3].astype(np.float32) / 255.0
    tot = float(al.sum())
    if tot < 50:
        return None
    return float((al * (1.0 - m.astype(np.float32) / 255.0)).sum() / tot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", help="the captioned result")
    ap.add_argument("--source", help="the original video")
    ap.add_argument("--captions", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--overlay", required=True, help="caption overlay (the 'all' or 'front' layer)")
    ap.add_argument("--behind", help="big-word overlay (behind mode)")
    ap.add_argument("--matte", help="person matte video (behind mode)")
    ap.add_argument("--out", help="contact sheet .jpg")
    ap.add_argument("--min-visible", type=float, default=0.55)
    ap.add_argument("--prune-to", help="behind mode: measure every big word and write captions without the hidden ones here")
    a = ap.parse_args()

    cap = json.load(open(a.captions))
    style = json.load(open(a.style))
    W, H = cap["video"]["width"], cap["video"]["height"]
    pages = cap["pages"]
    if not pages:
        sys.exit("verify.py: captions.json has no pages")
    if a.prune_to:
        if not (a.behind and a.matte):
            sys.exit("verify.py: --prune-to needs --behind and --matte")
        kept, dropped = [], []
        for b in cap.get("big", []):
            vis = None if b.get("front") else big_visibility(b, a.behind, a.matte, W, H)  # front words are not behind anyone
            if vis is None or vis >= a.min_visible:
                kept.append(b)
            else:
                dropped.append({"text": b["text"], "t": round((b["startMs"] + b["endMs"]) / 2000.0, 2), "visible": round(vis, 2)})
        cap["big"] = kept
        json.dump(cap, open(a.prune_to, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"kept": len(kept), "dropped": dropped, "out": a.prune_to}, ensure_ascii=False))
        return
    if not (a.video and a.source and a.out):
        sys.exit("verify.py: --video, --source and --out are required")
    warnings, frames = [], []
    L, T, R, B = safe_box(W, H)
    # text inside a container (pill, chip, block) or with an outline is readable on any footage
    protected = bool((style.get("stroke") or {}).get("width", 0) >= 0.3 or style.get("box") or style.get("container")
                     or (style.get("recipe") or {}).get("plate") or ((style.get("recipe") or {}).get("stroke") or {}).get("width", 0) >= 0.04)

    # automatic help (halo, scrim, stroke, plate) was measured and drawn for pages that needed it: see scripts/legibility.py
    helped = bool(cap.get("legibility")) and ((style.get("legibility") or {}).get("mode", "halo") != "none")
    protected = protected or helped

    picks = sorted({0, len(pages) // 4, len(pages) // 2, (3 * len(pages)) // 4, len(pages) - 1})
    for pi in picks:
        p = pages[pi]
        last = p["words"][-1]
        # a moment when the page is fully on screen: early in its last word, clear of the fade in and the fade out
        ps, pe = p["startMs"] / 1000.0, p["endMs"] / 1000.0
        t = last["startMs"] / 1000.0 + 0.3 * (min(last["endMs"], p["endMs"]) - last["startMs"]) / 1000.0
        t = max(min(t, pe - 0.25), min(ps + 0.2, (ps + pe) / 2))
        t = min(t, cap["video"]["durationMs"] / 1000.0 - 2.5 / float(cap["video"].get("fps") or 30))  # never past the last frame
        ov = grab(a.overlay, t, "rgba", W, H)
        src = grab(a.source, t, "rgb24", W, H)
        text = " ".join(w["text"] for w in p["words"])
        rec = {"t": round(t, 2), "page": pi, "text": text}
        if ov is None or src is None:
            rec["error"] = "could not read frame"
            warnings.append(f"{rec['t']}s: could not read a frame")
            frames.append(rec)
            continue
        alpha = ov[:, :, 3].astype(np.float32) / 255.0
        ys, xs = np.where(alpha > 0.5)
        if len(xs) < 20:
            rec["drawn"] = False
            warnings.append(f"{rec['t']}s: no caption drawn for \"{text}\"")
            frames.append(rec)
            continue
        if float((alpha > 0.5).mean()) > 0.85:
            # a full-frame style (lyric videos on a colour field): the field is the caption's own background, so the
            # safe-area and footage-contrast checks do not apply. Check the type against its field instead.
            ll = lum(ov[:, :, :3][alpha > 0.95])
            field = float(np.median(ll))  # the field is most of the frame; the type is the far end from it
            lo, hi = float(np.percentile(ll, 0.3)), float(np.percentile(ll, 99.7))
            ink = hi if hi - field >= field - lo else lo
            ratio = (max(ink, field) + 0.05) / (min(ink, field) + 0.05)
            rec.update(drawn=True, fullFrame=True, contrast=round(ratio, 2))
            if ratio < 3.0:
                warnings.append(f"{rec['t']}s: low contrast ({ratio:.1f}:1) between the type and its colour field")
            frames.append(rec)
            continue
        x0, x1, y0, y1 = xs.min() / W, (xs.max() + 1) / W, ys.min() / H, (ys.max() + 1) / H
        rec.update(drawn=True, box=[round(float(v), 3) for v in (x0, y0, x1, y1)])
        inside = x0 >= L - 0.005 and x1 <= R + 0.005 and y0 >= T - 0.005 and y1 <= B + 0.005
        rec["insideSafeArea"] = bool(inside)
        if not inside:
            warnings.append(f"{rec['t']}s: caption box {rec['box']} leaves the safe area [{L}, {T}, {R}, {B}]")
        elif H > W and x1 > 0.87 and y1 > 0.45:
            rec["note"] = "right edge may sit under the app's like/share buttons on TikTok and Reels"
        solid = alpha > 0.95
        pad = max(4, int(0.004 * H))
        bx0, bx1 = max(0, xs.min() - pad), min(W, xs.max() + pad)
        by0, by1 = max(0, ys.min() - pad), min(H, ys.max() + pad)
        bg = lum(src[by0:by1, bx0:bx1])
        tl = lum(ov[:, :, :3][solid]) if solid.any() else np.array([1.0])
        text_l = float(np.percentile(tl, 75))  # the fill, not the dark stroke
        bg_l = float(bg.mean())
        ratio = (max(text_l, bg_l) + 0.05) / (min(text_l, bg_l) + 0.05)
        rec.update(contrast=round(ratio, 2), protected=protected)
        if ratio < 3.0 and not protected:
            warnings.append(f"{rec['t']}s: low contrast ({ratio:.1f}:1) between the text and the footage behind it; use a style with a container (glass, chip, block) or a different text colour")
        frames.append(rec)

    behind = None
    if a.behind and a.matte and cap.get("big"):
        hidden, vis_all = [], []
        bigs = [b for b in cap["big"] if not b.get("front")]
        step = max(1, len(bigs) // 14)
        for b in bigs[::step]:
            t = (b["startMs"] + b["endMs"]) / 2000.0
            vis = big_visibility(b, a.behind, a.matte, W, H)
            if vis is None:
                continue
            vis_all.append(vis)
            if vis < a.min_visible:
                hidden.append({"text": b["text"], "t": round(t, 2), "visible": round(vis, 2)})
        behind = {"checked": len(vis_all), "minVisible": round(min(vis_all), 2) if vis_all else None,
                  "meanVisible": round(float(np.mean(vis_all)), 2) if vis_all else None, "hidden": hidden}
        for hgt in hidden:
            warnings.append(f"{hgt['t']}s: big word \"{hgt['text']}\" is only {int(hgt['visible'] * 100)}% visible behind the person")

    # contact sheet: caption frames, plus up to three big-word frames in behind mode
    times = [f["t"] for f in frames]
    if behind and cap.get("big"):
        bigs = cap["big"]
        for k in (0, len(bigs) // 2, len(bigs) - 1):
            times.append(round((bigs[k]["startMs"] + bigs[k]["endMs"]) / 2000.0, 2))
    times = sorted(set(times))[:8]
    th = 640
    tw = int(round(W * th / H))
    sheet = Image.new("RGB", (tw * len(times) + 8 * (len(times) - 1), th + 30), (16, 16, 18))
    for i, t in enumerate(times):
        fr = grab(a.video, t, "rgb24", tw, th)
        if fr is None:
            continue
        im = Image.fromarray(fr)
        d = ImageDraw.Draw(im)
        d.rectangle([L * tw, T * th, R * tw, B * th], outline=(120, 220, 235), width=1)
        x = i * (tw + 8)
        sheet.paste(im, (x, 0))
        ImageDraw.Draw(sheet).text((x + 6, th + 8), f"{t:.2f}s", fill=(210, 210, 210))
    sheet.save(a.out, quality=90)

    result = {"ok": not warnings, "warnings": warnings, "frames": frames, "behind": behind, "preview": a.out,
              "safeArea": [L, T, R, B]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

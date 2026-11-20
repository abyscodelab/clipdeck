#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "pillow"]
# ///
"""Build a contact sheet of every style on one clip.

    python3 tests/contact_sheet.py DIR --out sheet.jpg [--anchor gold] [--cols 9] [--tile 360]

DIR holds <style>.mp4 and <style>.captions.json, one pair per style (see tests/render_all.sh). Each tile is the frame where the
page holding the anchor word is fully on screen (the first page with that word, else the middle page).
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def pick_time(cap, anchor):
    pages = cap["pages"]
    idx = next((i for i, p in enumerate(pages) if any(anchor in w["text"].lower() for w in p["words"])), len(pages) // 2)
    p = pages[idx]
    last = p["words"][-1]
    s, e = p["startMs"] / 1000.0, p["endMs"] / 1000.0
    t = last["startMs"] / 1000.0 + 0.3 * (min(last["endMs"], p["endMs"]) - last["startMs"]) / 1000.0
    return max(min(t, e - 0.25), min(s + 0.2, (s + e) / 2))


def grab(path, t, w, h):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < w * h * 3:
        return Image.new("RGB", (w, h), (40, 0, 0))
    return Image.fromarray(np.frombuffer(raw[: w * h * 3], dtype=np.uint8).reshape(h, w, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor", default="three")
    ap.add_argument("--cols", type=int, default=9)
    ap.add_argument("--tile", type=int, default=360, help="tile width in px")
    ap.add_argument("--order", help="comma-separated style names (default: styles/ order from the repo)")
    a = ap.parse_args()
    d = Path(a.dir)
    root = Path(__file__).resolve().parent.parent
    if a.order:
        names = a.order.split(",")
    else:
        names = [json.loads(p.read_text()).get("name", p.stem) for p in sorted((root / "styles").glob("*.json"))]
        # the order of the published sheet: caption styles first, music styles last
        music = [n for n in names if json.loads((root / "styles" / f"{n}.json").read_text()).get("group") == "music"]
        names = [n for n in names if n not in music] + music
    names = [n for n in names if (d / f"{n}.mp4").exists()]
    first = json.loads((d / f"{names[0]}.captions.json").read_text())["video"]
    tw = a.tile
    th = int(round(tw * first["height"] / first["width"] / 2) * 2)
    rows = (len(names) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (tw * a.cols, th * rows), (12, 12, 12))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        font = ImageFont.load_default()
    for i, n in enumerate(names):
        cap = json.loads((d / f"{n}.captions.json").read_text())
        im = grab(d / f"{n}.mp4", pick_time(cap, a.anchor), tw, th)
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, 8 * len(n) + 16, 24], fill=(0, 0, 0))
        dr.text((6, 3), n, fill=(255, 255, 255), font=font)
        sheet.paste(im, ((i % a.cols) * tw, (i // a.cols) * th))
    sheet.save(a.out, quality=90)
    print(a.out, sheet.size, len(names), "styles")


if __name__ == "__main__":
    main()

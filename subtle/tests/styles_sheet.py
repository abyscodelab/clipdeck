#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "pillow"]
# ///
"""A contact sheet of styles on one clip, at a chosen moment, with the person cut-out in front of the "behind" words.

    uv run tests/styles_sheet.py --caps DIR --video clip.mp4 --matte matte.mp4 --moment wide --out sheet.jpg
        [--styles a,b,c] [--cols 6] [--tile 300] [--full-dir DIR] [--shot-wide 0-23.7 --shot-close 23.7-27.8]

DIR holds <style>.json: the captions.json of each style for this clip (what `subtle.py --stop-after group` writes). For every
style the three layers are rendered as stills with template/stills.mjs (one bundle), then stacked like the real composite:
source frame, behind layer, person cut-out (source x matte), front layer. `--moment wide` / `close` / seconds: with a number
every style is drawn at that time; with `wide` or `close` each style is drawn at the first moment of that kind of shot where its
giant word (or, for a front style, its page) is fully on screen.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def moment(cap, style, kind, span):
    """A time (s) inside span=(a, b) seconds where the style's giant word or page is settled on screen."""
    a, b = span
    behind = (style.get("behind") or {}).get("enabled") and cap.get("big")
    if behind:
        for w in cap["big"]:
            t = w["startMs"] / 1000 + 0.55
            if a <= t < b - 0.2 and t < w["endMs"] / 1000 and not (kind == "wide" and w.get("front")):
                return t
    for p in cap["pages"]:
        s, e = p["startMs"] / 1000, p["endMs"] / 1000
        last = p["words"][-1]
        t = max(s + 0.35, last["startMs"] / 1000 + 0.45)  # the last word has settled
        if t >= e - 0.05:
            t = max(s + 0.2, e - 0.12)
        if a <= t < b - 0.2:
            return t
    return (a + b) / 2


def grab(path, t, w, h, pix="rgb24"):
    ch = {"rgb24": 3, "gray": 1}[pix]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", pix, "-"], capture_output=True).stdout
    a = np.frombuffer(raw[: w * h * ch], dtype=np.uint8)
    return a.reshape(h, w, ch) if ch == 3 else a.reshape(h, w)


def over(base, top):
    """Alpha-composite RGBA `top` over RGB `base` (both uint8 arrays)."""
    al = top[:, :, 3:4].astype(np.float32) / 255.0
    return (base.astype(np.float32) * (1 - al) + top[:, :, :3].astype(np.float32) * al).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--matte")
    ap.add_argument("--moment", default="wide")
    ap.add_argument("--styles")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--tile", type=int, default=300)
    ap.add_argument("--out", required=True)
    ap.add_argument("--full-dir", help="also save every tile at full size here")
    ap.add_argument("--shot-wide", default="0-23.7")
    ap.add_argument("--shot-close", default="23.7-27.8")
    ap.add_argument("--at", default="", help="style=seconds,style=seconds: draw that style at that time instead")
    ap.add_argument("--notes", help="JSON file {style: 'text'} printed under each tile (ratings)")
    a = ap.parse_args()
    caps = Path(a.caps)
    names = a.styles.split(",") if a.styles else sorted(p.stem for p in caps.glob("*.json"))
    notes = json.loads(Path(a.notes).read_text()) if a.notes else {}
    span = tuple(float(x) for x in (a.shot_wide if a.moment == "wide" else a.shot_close).split("-")) if a.moment in ("wide", "close") else None
    work = Path(tempfile.mkdtemp(prefix="sheet-"))
    jobs, plan = [], {}
    for n in names:
        cap = json.loads((caps / f"{n}.json").read_text())
        st_path = ROOT / "styles" / f"{n}.json"
        st = json.loads(st_path.read_text())
        fps = cap["video"]["fps"]
        t = moment(cap, st, a.moment, span) if span else float(a.moment)
        t = {k: float(v) for k, v in (x.split("=") for x in a.at.split(",") if x)}.get(n, t)
        fr = int(round(t * fps))
        use_behind = bool((st.get("behind") or {}).get("enabled")) and a.matte
        layers = ["behind", "front"] if use_behind else ["all"]
        plan[n] = (t, layers)
        for ly in layers:
            jobs.append({"captions": str(caps / f"{n}.json"), "style": str(st_path), "layer": ly, "frame": fr, "png": str(work / f"{n}.{ly}.png")})
    (work / "jobs.json").write_text(json.dumps(jobs))
    subprocess.run(["node", str(ROOT / "template" / "stills.mjs"), str(work / "jobs.json")], check=True, capture_output=True)
    first = json.loads((caps / f"{names[0]}.json").read_text())["video"]
    W, H = first["width"], first["height"]
    tw = a.tile
    th = int(tw * H / W)
    pad = 6
    label_h = 34
    rows = (len(names) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (a.cols * (tw + pad) + pad, rows * (th + label_h + pad) + pad), (14, 14, 16))
    font = ImageFont.load_default(size=13)
    if a.full_dir:
        Path(a.full_dir).mkdir(parents=True, exist_ok=True)
    for k, n in enumerate(names):
        t, layers = plan[n]
        frame = grab(a.video, t, W, H)
        if layers == ["all"]:
            comp = over(frame, np.array(Image.open(work / f"{n}.all.png").convert("RGBA")))
        else:
            comp = over(frame, np.array(Image.open(work / f"{n}.behind.png").convert("RGBA")))
            m = grab(a.matte, t, W, H, "gray").astype(np.float32)[:, :, None] / 255.0
            comp = (comp.astype(np.float32) * (1 - m) + frame.astype(np.float32) * m).astype(np.uint8)
            comp = over(comp, np.array(Image.open(work / f"{n}.front.png").convert("RGBA")))
        img = Image.fromarray(comp)
        if a.full_dir:
            img.save(Path(a.full_dir) / f"{n}.png")
        x, y = pad + (k % a.cols) * (tw + pad), pad + (k // a.cols) * (th + label_h + pad)
        sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y))
        d = ImageDraw.Draw(sheet)
        d.text((x + 2, y + th + 4), f"{n}  {t:.1f}s", fill=(235, 235, 235), font=font)
        if n in notes:
            d.text((x + 2, y + th + 19), notes[n], fill=(134, 228, 240), font=font)
    sheet.save(a.out, quality=90)
    print(a.out, len(names), "styles")


if __name__ == "__main__":
    main()

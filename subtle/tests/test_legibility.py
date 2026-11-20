#!/usr/bin/env python3
"""Checks for scripts/legibility.py: contrast maths, how much help a page needs, palette picking and style tokens.
Needs numpy (skips with a note when it is missing): python3 tests/test_legibility.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import numpy as np
except ImportError:
    print("skip: numpy is not installed (scripts/legibility.py needs it; subtle.py runs it through uv)")
    sys.exit(0)
import legibility as lg  # noqa: E402

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def near(a, b, tol=0.01):
    return abs(a - b) <= tol


def main():
    # WCAG relative luminance and contrast ratio
    check(near(float(lg.rel_lum((255, 255, 255))), 1.0, 1e-6), "white luminance is 1")
    check(near(float(lg.rel_lum((0, 0, 0))), 0.0, 1e-6), "black luminance is 0")
    check(near(lg.contrast_ratio(1.0, 0.0), 21.0, 1e-6), "white on black is 21:1")
    check(near(lg.contrast_ratio(0.0, 1.0), 21.0, 1e-6), "contrast ratio is symmetric")
    check(near(lg.contrast_ratio(0.5, 0.5), 1.0, 1e-9), "same luminance is 1:1")
    check(near(float(lg.rel_lum((119, 119, 119))), 0.184, 0.002), "mid grey #777 luminance is about 0.184")
    check(near(lg.contrast_ratio(float(lg.rel_lum((119, 119, 119))), 1.0), 4.48, 0.03), "white on #777 is about 4.48:1")
    check(lg.parse_color("#fff") == (255.0, 255.0, 255.0), "short hex parses")
    check(lg.parse_color("rgba(10, 20, 30, 0.5)") == (10.0, 20.0, 30.0), "rgba parses")
    check(lg.parse_color({"auto": "accent"}) is None, "a token is not a colour")
    check(lg.to_hex((255, 128.4, 0)) == "#FF8000", "to_hex rounds")

    # boost: 0 on a clean dark background, 1 when the ink vanishes, monotone in both inputs
    check(lg.boost_for(18.0, 0.05) == 0.0, "white on a calm dark background needs no help")
    check(lg.boost_for(21.0, 0.0) == 0.0, "21:1 needs no help")
    check(lg.boost_for(1.0, 0.5) == 1.0, "invisible ink needs full help")
    check(lg.boost_for(4.6, 0.0) == 0.0, "4.5:1 on a calm background is enough")
    check(lg.boost_for(4.6, 0.8) > 0.2, "the same contrast on a busy background needs help")
    prev = 2.0
    for c in (1.2, 1.8, 2.5, 3.5, 4.5, 6.0, 9.0, 15.0):
        b = lg.boost_for(c, 0.5)
        check(b <= prev + 1e-9, f"boost falls as contrast rises ({c})")
        prev = b
    prev = -1.0
    for busy in (0.0, 0.25, 0.5, 0.75, 1.0):
        b = lg.boost_for(6.0, busy)
        check(b >= prev - 1e-9, f"boost rises with busyness ({busy})")
        prev = b
    check(all(0.0 <= lg.boost_for(c, u) <= 1.0 for c in (0.5, 1, 3, 30) for u in (-1, 0, 0.5, 2)), "boost stays in 0..1")

    # busyness: a flat field is calm, noise is busy
    flat = np.full((60, 80), 0.3)
    noise = np.random.default_rng(1).random((60, 80))
    check(lg.busyness(flat) < 0.01, "flat is calm")
    check(lg.busyness(noise) > 0.8, "noise is busy")

    # style tokens
    style = {"color": "#FFFFFF", "activeColor": {"auto": "accent", "fallback": "#F5F258"}, "emphasis": {"color": {"auto": "accent", "fallback": "#D6FCA5"}}}
    check(lg.has_auto(style), "has_auto finds nested tokens")
    check(not lg.has_auto({"color": "#fff"}), "has_auto is false for plain colours")
    check(lg.resolve_auto(style, None)["activeColor"] == "#F5F258", "no palette: the fallback")
    check(lg.resolve_auto(style, {"accent": "#AABBCC"})["emphasis"]["color"] == "#AABBCC", "palette: the footage colour")
    check(lg.style_mode({"container": {"kind": "pill"}}) == "none", "boxed styles default to none")
    check(lg.style_mode({}) == "halo", "unboxed styles default to halo")
    check(lg.style_mode({"container": {}, "legibility": {"mode": "plate"}}) == "plate", "a declared mode wins")
    main_ink, accent, dim = lg.style_inks(lg.resolve_auto(style, {"accent": "#AABBCC"}))
    check(main_ink == (255.0, 255.0, 255.0) and accent == (170.0, 187.0, 204.0) and dim == 1.0, "style_inks reads color, accent, dim")

    # k-means is deterministic and finds the colours that are there
    rng = np.random.default_rng(3)
    pix = np.concatenate([rng.normal((200, 60, 40), 6, (600, 3)), rng.normal((30, 40, 160), 6, (400, 3))]).clip(0, 255)
    c1, w1 = lg.kmeans(pix, k=2)
    c2, w2 = lg.kmeans(pix, k=2)
    check(np.allclose(c1, c2) and np.allclose(w1, w2), "kmeans is deterministic")
    check(abs(float(w1.max()) - 0.6) < 0.03, "kmeans weights match the cluster sizes")

    # palette: contrast against the darkened background, a hex colour, shade much darker than accent
    warm = np.array([[170.0, 120.0, 80.0], [60.0, 40.0, 30.0], [200.0, 170.0, 130.0]])
    for bg_rgb in ((131, 111, 89), (20, 20, 24), (230, 225, 215)):
        bg_lum = float(lg.rel_lum(np.array(bg_rgb, dtype=float)))
        pal = lg.pick_palette(warm, np.array([0.4, 0.3, 0.3]), np.array(bg_rgb, dtype=float), bg_lum)
        acc = lg.parse_color(pal["accent"])
        c = lg.contrast_ratio(float(lg.rel_lum(np.array(acc))), bg_lum * (1 - lg.SHIELD))
        check(c >= 3.0, f"accent keeps at least 3:1 on bg {bg_rgb} ({c:.2f})")
        if bg_lum < 0.3:
            check(c >= 4.5, f"accent reaches 4.5:1 when the background allows it ({bg_rgb}: {c:.2f})")
        check(float(lg.rel_lum(np.array(lg.parse_color(pal["shade"])))) < 0.03, "shade is dark")
        check(set(pal) >= {"accent", "accent2", "ink", "shade", "bg", "contrast"}, "palette keys")
    # a warm scene gets a warm accent
    pal = lg.pick_palette(warm, np.array([0.4, 0.3, 0.3]), np.array([131.0, 111.0, 89.0]), 0.17)
    import colorsys
    h = colorsys.rgb_to_hsv(*(np.array(lg.parse_color(pal["accent"])) / 255.0))[0] * 360
    check(h < 90 or h > 330, f"warm scene, warm accent (hue {h:.0f})")

    # the caption region stays inside the frame
    page = {"words": [{"text": "three", "line": 0, "emphasis": True}, {"text": "times,", "line": 1}]}
    for style in ({"size": 3.9, "position": {"y": 52, "marginX": 6}}, {"size": 6, "position": {"y": 96, "marginX": 4}, "lineHeight": 1.4}):
        x0, y0, x1, y1 = lg.region_of(page, style, 720, 1280)
        check(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, f"region inside the frame: {(x0, y0, x1, y1)}")

    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("ok: contrast maths, boost curve, busyness, style tokens, k-means, palette and caption region passed")


if __name__ == "__main__":
    main()

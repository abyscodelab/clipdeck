#!/usr/bin/env python3
"""Checks for the music path: beat detection (scripts/beats.py), lyric alignment (scripts/lyrics.py) and
lyric-line pages that start on the beat (scripts/group.py). Uses a generated click track, no real music.
Needs ffmpeg; the beat check also needs uv or numpy. python3 tests/test_music.py"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from group import group_pages, split_lines  # noqa: E402
from lyrics import align  # noqa: E402

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def main():
    # ---- lyric alignment: right words, transcript timings ----
    heard_txt = "we walked along the rival in the rain oh oh oh oh then the lights came on and gain"
    heard = [{"text": t, "startMs": 500 * k, "endMs": 500 * k + 400} for k, t in enumerate(heard_txt.split())]
    lyrics = [(0, w) for w in "We walked along the river in the rain".split()] + [(1, w) for w in "Then the lights came on again".split()] \
        + [(2, w) for w in "A line that is never sung".split()]
    words, stats = align(heard, lyrics)
    texts = [w["text"] for w in words]
    check("river" in texts and "rival" not in texts, f"lyrics: the written word must replace the misheard one: {texts}")
    check(texts.count("oh") == 4, f"lyrics: a sung run that is not in the file stays as heard: {texts}")
    check("never" not in texts and stats["notHeard"] >= 6, f"lyrics: an unsung line must be left out: {texts} {stats}")
    river = next(w for w in words if w["text"] == "river")
    check(river["startMs"] == 2000, f"lyrics: 'river' should take the timing of the word it replaces, got {river['startMs']}")
    check("again" in texts, f"lyrics: the end of a line heard as two other words should still be placed: {texts}")
    check(all(a["endMs"] <= b["startMs"] for a, b in zip(words, words[1:])), "lyrics: words overlap")
    check([w["lyricLine"] for w in words if w["text"] in ("We", "rain", "Then")] == [0, 0, 1], "lyrics: lyricLine is wrong")

    # ---- lines: as few as fit, up to max_lines ----
    ws = [{"text": t} for t in "one two three four five six seven eight nine".split()]
    check(max(split_lines(ws, 16, 3)) == 2 and max(split_lines(ws, 30, 3)) == 1 and max(split_lines(ws, 80, 3)) == 0, "split_lines: wrong number of lines")

    # ---- pages are lyric lines and start on the beat ----
    beat = 500
    beats = {"bpm": 120.0, "times": [beat * k for k in range(60)], "downbeats": [beat * k for k in range(0, 60, 4)]}
    sung = []
    for line, (t0, text) in enumerate([(2030, "first line of the song"), (6040, "second line comes after"), (9980, "third")]):
        for k, t in enumerate(text.split()):
            sung.append({"text": t, "startMs": t0 + 420 * k, "endMs": t0 + 420 * k + 380, "lyricLine": line})
    cfg = {"unit": "line", "maxWords": 6, "maxCharsPerLine": 40, "snap": "beat", "hold": True, "minFrames": 6, "maxFrames": 200}
    pages = group_pages(sung, cfg, 30.0, False, beats)
    check(len(pages) == 3, f"line pages: expected 3 pages, got {len(pages)}")
    check(all(min(abs(p["startMs"] - b) for b in beats["times"]) <= 34 for p in pages), f"line pages: a page does not start on a beat: {[p['startMs'] for p in pages]}")
    check(all(p["startMs"] <= p["words"][0]["startMs"] + 34 for p in pages), "line pages: a page starts after its first word")
    check(pages[0]["endMs"] == pages[1]["startMs"], "line pages: with hold, a page stays until the next one starts")
    cfg4 = dict(cfg, linesPerPage=4, snap="bar")
    block = group_pages(sung, cfg4, 30.0, False, beats)
    check(len(block) >= 1 and max(w["line"] for w in block[0]["words"]) >= 1, "line pages: a block should hold several lines")
    plain = group_pages(sung, cfg, 30.0, False, None)
    check(len(plain) == 3, "line pages: must work with no beats")

    # ---- beat detection on a generated click track: 120 BPM, clicks at 0.5 s steps from 0.25 s ----
    runner = ["uv", "run", "-q"] if shutil.which("uv") else [sys.executable]
    have_numpy = bool(shutil.which("uv")) or subprocess.run([sys.executable, "-c", "import numpy"], capture_output=True).returncode == 0
    if shutil.which("ffmpeg") and have_numpy:
        with tempfile.TemporaryDirectory() as tmp:
            wav, out = Path(tmp) / "click.wav", Path(tmp) / "beats.json"
            import array
            import math
            import wave
            sr = 22050
            pcm = array.array("h")
            for n in range(sr * 20):  # a kick-like thump plus a tick, every 0.5 s from 0.25 s
                t = n / sr
                ph = (t + 0.25) % 0.5
                v = 0.8 * math.sin(2 * math.pi * 90 * t) * math.exp(-28 * ph) + 0.15 * math.sin(2 * math.pi * 2000 * t) * math.exp(-60 * ph)
                pcm.append(int(max(-1.0, min(1.0, v)) * 30000))
            with wave.open(str(wav), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sr)
                f.writeframes(pcm.tobytes())
            r = subprocess.run(runner + [str(ROOT / "scripts" / "beats.py"), str(wav), "--out", str(out), "--no-cache"], capture_output=True, text=True)
            check(r.returncode == 0, f"beats.py failed: {r.stderr[-300:]}")
            if r.returncode == 0:
                b = json.loads(out.read_text())
                check(b["bpm"] and abs(b["bpm"] - 120) < 1.5, f"beats: tempo {b['bpm']}, expected 120")
                err = [min(abs(t - (250 + 500 * k)) for k in range(41)) for t in b["times"]]
                check(len(b["times"]) >= 34 and sorted(err)[int(len(err) * 0.9)] <= 35, f"beats: 90% of beats should be within 35 ms of a click: {sorted(err)[-5:]}")
                check(len(b["downbeats"]) >= 8, "beats: no bar starts")
    else:
        print("skipped the beat check (needs ffmpeg and uv or numpy)")

    if failures:
        print("FAILED")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("ok: lyric alignment, multi-line splits, beat-snapped lyric pages and beat detection passed")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy"]
# ///
"""Find the tempo, the beats and the bar starts of a song. Local and free: ffmpeg + numpy, no model, no network.

    uv run scripts/beats.py song.mp3 --out beats.json

Writes {"bpm", "times" (ms, every beat), "downbeats" (ms, every 4th beat: 4/4 is assumed), "clarity" (0..1)}.
Music styles use it to start pages on a beat and to move on the beat. The result is cached by the file's SHA-256.

Method: onset strength from the spectral flux of a log-magnitude spectrogram, tempo from its autocorrelation
(weighted towards 120 BPM), beats by dynamic programming over the onset curve, and the bar phase from the low
band: the beat of each four that carries the most bass is called the downbeat. A weak pulse (clarity under 0.25:
speech, ambient music) still returns a grid, but callers should not trust it.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
N_FFT = 1024
HOP = 256  # 11.6 ms
CACHE_VERSION = 1


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_curves(y):
    """(full-band onset strength, low-band onset strength) per hop."""
    n = 1 + max(0, (len(y) - N_FFT) // HOP)
    if n < 8:
        return np.zeros(0), np.zeros(0)
    win = np.hanning(N_FFT).astype(np.float32)
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(y[idx] * win, axis=1))  # n x 513
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    # 36 bands, evenly spaced on a log axis from 40 Hz to 10 kHz
    edges = np.geomspace(40, 10000, 37)
    bands = np.stack([mag[:, (freqs >= lo) & (freqs < hi)].sum(axis=1) for lo, hi in zip(edges[:-1], edges[1:])], axis=1)
    logb = np.log1p(20.0 * bands)
    flux = np.maximum(0.0, np.diff(logb, axis=0, prepend=logb[:1]))
    full = flux.sum(axis=1)
    low = flux[:, edges[:-1] < 160].sum(axis=1)

    def norm(x):
        x = x - np.convolve(x, np.ones(87) / 87, mode="same")  # remove the slow trend (about 1 s)
        x = np.maximum(0.0, x)
        s = x.std()
        return x / s if s > 0 else x
    return norm(full), norm(low)


def tempo_of(onset, lo=55.0, hi=210.0, centre=120.0):
    """(beat period in hops, clarity). Autocorrelation with a log-normal weight around `centre` BPM."""
    fps = SR / HOP
    n = len(onset)
    ac = np.correlate(onset, onset, mode="full")[n - 1:]
    if ac[0] <= 0:
        return fps * 60.0 / centre, 0.0
    ac = ac / ac[0]
    lag_lo, lag_hi = int(fps * 60.0 / hi), min(int(fps * 60.0 / lo), n - 1)
    lags = np.arange(lag_lo, lag_hi + 1)
    bpm = 60.0 * fps / lags
    weight = np.exp(-0.5 * (np.log2(bpm / centre) / 0.9) ** 2)
    # a real pulse also correlates at twice the lag
    score = (ac[lags] + 0.5 * ac[np.minimum(2 * lags, n - 1)]) * weight
    best = int(lags[int(np.argmax(score))])
    # refine the lag to a fraction of a hop with a parabola through the peak
    a, b, c = ac[best - 1], ac[best], ac[best + 1] if best + 1 < n else ac[best]
    off = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    return best + float(np.clip(off, -0.5, 0.5)), float(max(0.0, ac[best]))


def track(onset, period, tightness=100.0):
    """Beat positions (hops) that follow the onset curve while keeping the period (Ellis 2007)."""
    n = len(onset)
    score = onset.copy()
    back = -np.ones(n, dtype=int)
    lo, hi = int(round(period * 0.5)), int(round(period * 2.0))
    gaps = np.arange(lo, hi + 1)
    penalty = -tightness * np.log(gaps / period) ** 2
    for t in range(lo, n):
        prev = t - gaps
        ok = prev >= 0
        if not ok.any():
            continue
        cand = score[prev[ok]] + penalty[ok]
        k = int(np.argmax(cand))
        score[t] = onset[t] + cand[k]
        back[t] = prev[ok][k]
    t = int(np.argmax(score[max(0, n - int(period)):])) + max(0, n - int(period))
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return np.array(beats[::-1])


def analyse(path):
    y = decode(path)
    full, low = onset_curves(y)
    if len(full) < 64:
        return {"bpm": None, "times": [], "downbeats": [], "clarity": 0.0}
    period, clarity = tempo_of(full)
    beats = track(full, period)
    # drop beats in a silent lead-in or tail: nothing happens there
    env = np.convolve(np.abs(y), np.ones(HOP * 8) / (HOP * 8), mode="same")[::HOP][:len(full)]
    loud = env > 0.02 * env.max()
    first, last = int(np.argmax(loud)), len(loud) - int(np.argmax(loud[::-1]))
    beats = beats[(beats >= first - period) & (beats <= last)]
    if len(beats) < 4:
        return {"bpm": None, "times": [], "downbeats": [], "clarity": round(clarity, 3)}
    spacing = float(np.median(np.diff(beats)))
    bpm = 60.0 * SR / HOP / spacing
    # bar phase: which of every four beats carries the most bass
    w = 3
    strength = np.array([low[max(0, b - w):b + w + 1].max() for b in beats])
    phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
    ms = lambda b: int(round((b * HOP + N_FFT / 2) * 1000.0 / SR))
    times = [ms(b) for b in beats]
    return {"bpm": round(bpm, 2), "times": times, "downbeats": times[phase::4], "clarity": round(clarity, 3),
            "beatsPerBar": 4, "note": "4/4 assumed; the downbeat is the beat of each four with the most bass"}


def main():
    ap = argparse.ArgumentParser(description="Tempo, beats and bar starts of a song (local, numpy only).")
    ap.add_argument("audio", help="any file ffmpeg reads (audio or video)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    src = Path(a.audio).expanduser()
    if not src.exists():
        sys.exit(f"beats.py: no such file: {src}")
    digest = sha256(src)
    cache_dir = Path(os.environ.get("SUBTLE_CACHE", Path.home() / ".cache" / "subtle")) / "beats"
    cache = cache_dir / f"{digest}-v{CACHE_VERSION}.json"
    cached = cache.exists() and not a.no_cache
    if cached:
        res = json.loads(cache.read_text())
    else:
        res = analyse(src)
        res["sha256"] = digest
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(res))
    Path(a.out).write_text(json.dumps(res))
    print(json.dumps({"out": a.out, "bpm": res["bpm"], "beats": len(res["times"]), "bars": len(res["downbeats"]),
                      "clarity": res["clarity"], "cached": cached}))


if __name__ == "__main__":
    main()

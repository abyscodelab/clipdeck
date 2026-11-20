#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["mlx-whisper>=0.4"]
# ///
"""Transcribe a video to word timings with mlx-whisper (Apple Silicon, local, free).

    uv run scripts/transcribe.py video.mp4 --out words.json [--lang en] [--vocab "Refs, Claude"] [--script roman]

Without uv: `pip install mlx-whisper`, then run it with python3.
The result is cached by the file's SHA-256, so a second run on the same video returns at once.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
CACHE_VERSION = 3  # bump when the transcription or spelling logic changes, so old cache entries are not reused


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def probe(path):
    """Display width/height (rotation applied), fps and duration via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,avg_frame_rate:stream_disposition=attached_pic:stream_side_data=rotation:stream_tags=rotate:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    streams = [x for x in d.get("streams", []) if not (x.get("disposition") or {}).get("attached_pic")]
    if not streams:  # a song or a voice memo: no picture. The runner makes a canvas and sets the real size.
        return {"width": 1080, "height": 1920, "fps": 30.0, "durationMs": int(float(d["format"]["duration"]) * 1000), "audioOnly": True}
    s = streams[0]
    w, h = int(s["width"]), int(s["height"])
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if not rot and s.get("tags", {}).get("rotate"):
        rot = int(s["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (s.get("avg_frame_rate") or s["r_frame_rate"]).split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    if not fps or fps > 240:
        num, den = s["r_frame_rate"].split("/")
        fps = float(num) / float(den)
    return {"width": w, "height": h, "fps": round(fps, 3), "durationMs": int(float(d["format"]["duration"]) * 1000)}


# ---- Devanagari → Roman (casual "Hinglish" spelling, best effort) ----
_CONS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
         "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
         "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
         "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f"}
_VOW = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऋ": "ri", "ऑ": "o"}
_MATRA = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri", "ॉ": "o"}
_NUKTA, _VIRAMA = "़", "्"
# How people actually type the most common Hindi words; the rules below cannot guess these.
_COMMON = {"में": "mein", "मैं": "main", "हैं": "hain", "है": "hai", "नहीं": "nahi", "हम": "hum", "और": "aur", "यह": "yeh", "ये": "yeh",
           "वह": "woh", "वो": "woh", "क्या": "kya", "क्यों": "kyun", "सिर्फ": "sirf", "लेकिन": "lekin", "दोस्तों": "doston",
           "आप": "aap", "आपको": "aapko", "कि": "ki", "की": "ki", "का": "ka", "के": "ke", "को": "ko", "से": "se", "पर": "par",
           "हुआ": "hua", "हुई": "hui", "था": "tha", "थी": "thi", "थे": "the", "भी": "bhi", "ही": "hi", "तो": "toh", "अब": "ab",
           "बहुत": "bahut", "अच्छा": "accha", "कौन": "kaun", "कुछ": "kuch", "मुझे": "mujhe", "इंडिया": "India", "इंडिय": "India"}
_LATIN_FIX = str.maketrans({"š": "sh", "č": "ch", "ñ": "n", "ā": "aa", "ī": "ee", "ū": "oo", "ṭ": "t", "ḍ": "d", "ṇ": "n", "ś": "sh", "ṣ": "sh"})


def romanize_word(word):
    """Transliterate one Devanagari word. Drops the silent final and medial 'a' the way people type Hinglish."""
    if word in _COMMON:
        return _COMMON[word]
    units = []  # (roman, has_inherent_a, is_consonant)
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        two = word[i:i + 2]
        if two in _CONS or ch in _CONS:
            base = _CONS[two] if two in _CONS else _CONS[ch]
            i += 2 if two in _CONS else 1
            if i < n and word[i] == _NUKTA:
                base = {"j": "z", "ph": "f", "k": "q", "d": "r", "dh": "rh"}.get(base, base)
                i += 1
            if i < n and word[i] == _VIRAMA:
                units.append([base, False, True]); i += 1
            elif i < n and word[i] in _MATRA:
                m = word[i]
                rom = _MATRA[m]
                # a long vowel in the middle of a word is typed double (baat, teen, door); at the end it is single (sona, ki)
                if i + 1 < n and m in "ाीू" and word[i + 1] not in "ंँ":
                    rom = {"ा": "aa", "ी": "ee", "ू": "oo"}[m]
                units.append([base + rom, False, True]); i += 1
            else:
                units.append([base, True, True])
        elif ch in _VOW:
            units.append([_VOW[ch], False, False]); i += 1
        elif ch in "ंँ":
            units.append(["n", False, False]); i += 1
        elif ch == "ः":
            units.append(["h", False, False]); i += 1
        else:
            units.append([ch, False, False]); i += 1
    out = []
    for k, (rom, inherent, cons) in enumerate(units):
        if inherent:
            last = k == len(units) - 1
            nxt = units[k + 1] if not last else None
            # final 'a' is silent; so is a medial 'a' before a consonant that carries its own vowel (kar-na, not karana)
            medial_drop = (k >= 1 and nxt is not None and nxt[2] and not nxt[1] and nxt[0][-1:] in "aeiou")
            if last and len(units) > 1:
                pass
            elif medial_drop:
                pass
            else:
                rom += "a"
        out.append(rom)
    return "".join(out)


def romanize(text):
    """Devanagari runs → Latin, then strip the stray accents Whisper sometimes adds to romanised Hindi."""
    import unicodedata
    text = re.sub(r"[ऀ-ॿ]+", lambda m: romanize_word(m.group(0)), text).translate(_LATIN_FIX)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


ROMAN_HINT = ("Yeh video Hinglish mein hai. Hindi ko Roman script mein likho aur English words ko English mein rakho: "
              "doston, aaj hum baat karenge, yeh sirf ek example nahi hai, kya aapko pata hai.")


def main():
    ap = argparse.ArgumentParser(description="Word-level transcription with mlx-whisper.")
    ap.add_argument("video")
    ap.add_argument("--out", help="where to write words.json (default: the cache folder)")
    ap.add_argument("--lang", help="language code, e.g. en, hi, es (default: detect)")
    ap.add_argument("--vocab", default="", help="names and brand words, comma-separated; passed to Whisper as a hint")
    ap.add_argument("--script", choices=["native", "roman"], default="native",
                    help="roman: write Hindi in Latin letters (Hinglish), best effort")
    ap.add_argument("--hinglish", action="store_true", help="short for --lang hi --script roman")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--cache-dir", default=os.environ.get("SUBTLE_CACHE", str(Path.home() / ".cache" / "subtle")))
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    if a.hinglish:
        a.lang, a.script = a.lang or "hi", "roman"
    video = Path(a.video).expanduser().resolve()
    if not video.exists():
        sys.exit(f"transcribe.py: no such file: {video}")
    t0 = time.time()
    digest = sha256(video)
    key = hashlib.sha256(json.dumps([CACHE_VERSION, a.lang, a.vocab, a.script, a.model]).encode()).hexdigest()[:10]
    cdir = Path(a.cache_dir) / digest[:16]
    cdir.mkdir(parents=True, exist_ok=True)
    cached = cdir / f"words.{key}.json"
    out_path = Path(a.out).expanduser() if a.out else cached

    if cached.exists() and not a.no_cache:
        data = json.loads(cached.read_text())
        if out_path != cached:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        print(json.dumps({"out": str(out_path), "words": len(data["words"]), "language": data["language"], "cached": True, "seconds": round(time.time() - t0, 2)}))
        return

    meta = probe(video)
    wav = cdir / "audio.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ar", "16000", "-ac", "1", str(wav)], check=True)

    try:
        import mlx_whisper
    except ImportError:
        sys.exit("transcribe.py: mlx-whisper is not installed. Run this script with `uv run`, or `pip install mlx-whisper`.")

    kwargs = dict(path_or_hf_repo=a.model, word_timestamps=True, condition_on_previous_text=False, verbose=None)
    if a.lang:
        kwargs["language"] = a.lang
    hints = []
    if a.script == "roman" and (a.lang or "") == "hi":
        hints.append(ROMAN_HINT)  # with this hint Whisper writes most Hindi in Latin letters by itself
    if a.vocab.strip():
        hints.append("Vocabulary: " + a.vocab.strip().rstrip(".") + ".")
    if hints:
        kwargs["initial_prompt"] = " ".join(hints)
    result = mlx_whisper.transcribe(str(wav), **kwargs)

    words = []
    for seg in result.get("segments", []):
        seg_words = 0
        for w in seg.get("words", []) or []:
            raw = w.get("word") or ""
            text = raw.strip()
            if not text:
                continue
            if a.script == "roman":
                text = romanize(text)
            if words and not raw.startswith(" ") and seg_words > 0 and re.match(r"^[\w,.'’%-]", text):
                # Whisper split one word into two tokens ("25" + ",000"): glue it back together
                words[-1]["text"] += text
                words[-1]["endMs"] = int(round(float(w["end"]) * 1000))
                continue
            seg_words += 1
            words.append({"text": text, "startMs": int(round(float(w["start"]) * 1000)), "endMs": int(round(float(w["end"]) * 1000)),
                          "prob": round(float(w.get("probability", 0)), 3)})
    data = {"version": 1, "source": {"sha256": digest, **meta}, "language": result.get("language") or a.lang, "model": a.model,
            "script": a.script, "words": words}
    cached.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    if out_path != cached:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    secs = time.time() - t0
    print(json.dumps({"out": str(out_path), "words": len(words), "language": data["language"], "cached": False,
                      "seconds": round(secs, 2), "secondsPerMinuteOfVideo": round(secs / max(1e-6, meta["durationMs"] / 60000), 2)}))


if __name__ == "__main__":
    main()

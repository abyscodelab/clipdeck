#!/usr/bin/env python3
"""Subtle: beautiful captions for any video. One command, all local.

    python3 scripts/subtle.py video.mp4                       # default style: glide
    python3 scripts/subtle.py video.mp4 --style keyword       # a giant keyword behind the speaker (macOS)
    python3 scripts/subtle.py video.mp4 --style glass --emphasis "gold,three"
    python3 scripts/subtle.py --list-styles
    python3 scripts/subtle.py video.mp4 --stop-after transcribe   # only write words.json and print the transcript
    python3 scripts/subtle.py video.mp4 --captions edited.json    # re-render from captions you edited

Outputs next to the video: <name>.captioned.mp4, <name>.captions.json, <name>.srt, <name>.preview.jpg
Standard library only. The steps it runs are separate tools in this folder; see docs/ARCHITECTURE.md.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASPECTS = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "4:5": (4, 5)}
CANVAS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def deep_merge(base, over):
    """`over` on top of `base`: dicts merge key by key, everything else is replaced."""
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def has_picture(path):
    """False for a song or a voice memo (cover art does not count)."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_name:stream_disposition=attached_pic", "-of", "json", path])
    return any(not (x.get("disposition") or {}).get("attached_pic") for x in json.loads(out).get("streams", []))


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-4000:])
        sys.exit(f"subtle: step failed: {' '.join(str(c) for c in cmd[:3])} ...")
    return r.stdout


def last_json(text):
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {}


def has_auto(obj):
    """True when a style takes colours from the footage: a {"auto": ..., "fallback": ...} token anywhere in it."""
    if isinstance(obj, dict):
        return isinstance(obj.get("auto"), str) or any(has_auto(v) for v in obj.values())
    return isinstance(obj, list) and any(has_auto(v) for v in obj)


def py(script):
    """Run a script that needs packages through sys.executable if modules exist, or uv."""
    try:
        import numpy  # noqa: F401
        import PIL  # noqa: F401
        return [sys.executable, str(script)]
    except ImportError:
        pass
    if shutil.which("uv"):
        return ["uv", "run", "-q", str(script)]
    return [sys.executable, str(script)]


def probe_size(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height:stream_side_data=rotation", "-of", "json", path])
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd and abs(int(float(sd["rotation"]))) % 180 == 90:
            w, h = h, w
    return w, h


def probe_fps(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path]).strip()
    n, _, d = out.partition("/")
    try:
        return float(n) / float(d or 1)
    except (ValueError, ZeroDivisionError):
        return 30.0


def main():
    ap = argparse.ArgumentParser(description="Add animated captions to a video.")
    ap.add_argument("video", nargs="?")
    ap.add_argument("--style", default="glide",
                    help="a style name from styles/ (run with --list-styles), name:variant for a colourway (ticket:yellow), or a path to a style JSON")
    ap.add_argument("--lyrics", help="a text file with the right words, one lyric line per line: its words replace the transcript's, on the transcript's timings")
    ap.add_argument("--canvas", default="9:16", choices=sorted(CANVAS), help="frame for an audio-only input (a song): 9:16 (default), 16:9, 1:1 or 4:5")
    ap.add_argument("--list-styles", action="store_true", help="print the available styles and exit")
    ap.add_argument("--behind", choices=["auto", "on", "off"], default="auto",
                    help="auto: put the big words behind the speaker when the style supports it (keyword) and the subject check passes; on: force it; off: never")
    ap.add_argument("--placement", choices=["auto", "off"], default="auto",
                    help="auto: move each page off the face and the hands, within the style's position.flex range (macOS, Apple Vision); off: every page keeps the style's y")
    ap.add_argument("--cuts", choices=["auto", "off"], default="auto",
                    help="auto: find hard cuts with ffmpeg so no caption page straddles one; off: ignore cuts")
    ap.add_argument("--lang", help="spoken language code (default: detect)")
    ap.add_argument("--vocab", default="", help="names and brand words, comma-separated")
    ap.add_argument("--script", choices=["native", "roman"], default="native", help="roman: Hindi in Latin letters")
    ap.add_argument("--hinglish", action="store_true", help="short for --lang hi --script roman")
    ap.add_argument("--aspect", default="source", help="source (default), 9:16, 1:1, 4:5 or 16:9 (centre crop)")
    ap.add_argument("--max-words", type=int)
    ap.add_argument("--emphasis", default="auto",
                    help="which words to highlight: auto (numbers, prices, names, contrast words), numbers (numbers only) or off")
    ap.add_argument("--emphasis-words", default="", help='words to highlight for sure, e.g. "gold, $5,000" (use single quotes in a shell)')
    ap.add_argument("--numbers", default="auto", choices=["auto", "western", "indian", "off"],
                    help="spoken numbers become one token ($5,000, 40%%, ₹5 lakh); digit grouping auto, western or indian; off keeps the transcript")
    ap.add_argument("--replace", action="append", default=[], help="heard=Shown spelling fix (repeatable)")
    ap.add_argument("--clean", action="store_true", help="drop filler words")
    ap.add_argument("--words", help="use this words.json and skip transcription")
    ap.add_argument("--captions", help="use this captions.json and skip grouping")
    ap.add_argument("--out", help="output video path")
    ap.add_argument("--work", help="work folder (default: .subtle/<name> next to the video)")
    ap.add_argument("--stop-after", choices=["transcribe", "group"])
    ap.add_argument("--palette", choices=["auto", "off"], default="auto",
                    help="auto: styles whose accent colour is {auto: ...} take it from the footage (a colour that suits the scene and reads on it); off: the preset's colours")
    ap.add_argument("--legibility", choices=["auto", "off"], default="auto",
                    help="auto: measure the background behind every page and add a halo, scrim or outline where the text would not read; off: draw the preset as it is")
    ap.add_argument("--matte-quality", choices=["accurate", "balanced", "fast"], default="accurate")
    ap.add_argument("--crf", default="18")
    a = ap.parse_args()

    if a.list_styles:
        all_styles = [json.loads(p.read_text()) for p in sorted((ROOT / "styles").glob("*.json"))]
        for title, pick in (("Caption styles", lambda st: st.get("group") != "music"), ("Music / lyric styles (pages start on the beat)", lambda st: st.get("group") == "music")):
            rows = [st for st in all_styles if pick(st)]
            if rows:
                print(title)
                for st in rows:
                    variants = ", ".join(f"{st['name']}:{v}" for v in (st.get("variants") or {}))
                    print(f"  {st['name']:12s} {st.get('description', '')}" + (f"  [also: {variants}]" if variants else ""))
        return
    if not a.video:
        ap.error("the video path is required")
    if a.hinglish:
        a.lang, a.script = a.lang or "hi", "roman"
    src = Path(a.video).expanduser().resolve()
    if not src.exists():
        sys.exit(f"subtle: no such file: {src}")
    work = Path(a.work).expanduser().resolve() if a.work else src.parent / ".subtle" / src.stem
    work.mkdir(parents=True, exist_ok=True)
    out = Path(a.out).expanduser().resolve() if a.out else src.with_name(src.stem + ".captioned.mp4")
    times = {}
    notes = []

    def step(name):
        class T:
            def __enter__(s):
                s.t = time.time()
            def __exit__(s, *e):
                times[name] = round(times.get(name, 0) + time.time() - s.t, 2)
        return T()

    style_name, _, variant = (a.style, "", "") if a.style.endswith(".json") else a.style.partition(":")
    style_path = Path(a.style) if a.style.endswith(".json") else ROOT / "styles" / f"{style_name}.json"
    if not style_path.exists():
        names = sorted(p.stem for p in (ROOT / "styles").glob("*.json"))
        sys.exit(f"subtle: unknown style '{style_name}'. Styles: {', '.join(names)}")
    style = json.loads(style_path.read_text())
    if variant:  # a colourway: the preset with a few keys replaced
        variants = style.get("variants") or {}
        if variant not in variants:
            sys.exit(f"subtle: style '{style_name}' has no variant '{variant}'. " + (f"Variants: {', '.join(variants)}" if variants else "It has no variants."))
        style = deep_merge(style, variants[variant])
        style["variant"] = variant
        style_path = work / "style.json"
        style_path.write_text(json.dumps(style, indent=1))
    music = style.get("group") == "music" or (style.get("page") or {}).get("snap") in ("beat", "bar")

    # ---- a song or a voice memo has no picture: make a plain canvas for the captions to sit on ----
    video = src
    audio_only = not has_picture(src)
    if audio_only:
        cw, ch = CANVAS[a.canvas]
        video = work / f"canvas-{cw}x{ch}.mp4"
        if not video.exists():
            with step("canvas"):
                run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={cw}x{ch}:r=30", "-i", src, "-shortest",
                     "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", video])
        notes.append(f"no picture in the input: captions are drawn on a black {cw}x{ch} canvas (--canvas changes the shape)")

    # ---- aspect: centre-crop a working copy when asked ----
    if a.aspect != "source" and not audio_only:
        if a.aspect not in ASPECTS:
            sys.exit(f"subtle: --aspect must be source or one of {', '.join(ASPECTS)}")
        w, h = probe_size(src)
        aw, ah = ASPECTS[a.aspect]
        if abs(w / h - aw / ah) > 0.01:
            cw, ch = (w, int(w * ah / aw)) if w / h < aw / ah else (int(h * aw / ah), h)
            cw, ch = cw - cw % 2, ch - ch % 2
            video = work / f"cropped-{a.aspect.replace(':', 'x')}.mp4"
            if not video.exists():
                with step("crop"):
                    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"crop={cw}:{ch}", "-c:v", "libx264", "-crf", "16",
                         "-pix_fmt", "yuv420p", "-c:a", "copy", video])

    # ---- transcribe ----
    words_path = work / "words.json"
    if a.captions:
        pass
    elif a.words:
        shutil.copyfile(Path(a.words).expanduser(), words_path)
    else:
        cmd = py(HERE / "transcribe.py") + [src, "--out", words_path, "--script", a.script]
        if a.lang:
            cmd += ["--lang", a.lang]
        if a.vocab:
            cmd += ["--vocab", a.vocab]
        with step("transcribe"):
            info = last_json(run(cmd))
        if info.get("cached"):
            notes.append("transcript came from the cache")
    if not a.captions and a.lyrics:
        with step("lyrics"):
            ly = last_json(run([sys.executable, HERE / "lyrics.py", words_path, Path(a.lyrics).expanduser(), "--out", words_path]))
        notes.append(f"lyrics file: {ly.get('matched', 0)} of {ly.get('lyricWords', 0)} words found in the audio, {ly.get('notHeard', 0)} never sung here, "
                     f"{ly.get('keptAsHeard', 0)} sung words kept as transcribed" + ("; " + ly["warning"] if ly.get("warning") else ""))
    if not a.captions:
        data = json.loads(words_path.read_text())
        if video != src:  # the crop or the canvas changed the frame size, not the timing
            w, h = probe_size(video)
            data["source"].update(width=w, height=h)
            words_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        transcript = " ".join(w["text"] for w in data["words"])
        if a.stop_after == "transcribe":
            print(json.dumps({"words": str(words_path), "language": data.get("language"), "transcript": transcript, "seconds": times}, ensure_ascii=False))
            return

    # ---- behind mode: decide ----
    wants_behind = bool((style.get("behind") or {}).get("enabled"))
    use_behind = False
    check = None
    if a.behind == "on" and not wants_behind:
        style_path = ROOT / "styles" / "keyword.json"
        style = json.loads(style_path.read_text())
        wants_behind = True
        notes.append("--behind on: switched to the keyword style")
    if wants_behind and a.behind != "off":
        vm = HERE / "vision-matte" / ".build" / "vision-matte"
        if sys.platform != "darwin":
            notes.append("behind mode needs macOS; the big words are drawn in front of the speaker instead")
        else:
            if not vm.exists():
                with step("build-matte-tool"):
                    run(["bash", HERE / "vision-matte" / "build.sh"])
            bcfg = style.get("behind") or {}
            band = (float(bcfg.get("bigSize", 14)) + float(bcfg.get("bigMaxSize", 24))) / 200.0
            with step("subject-check"):
                check = last_json(run([vm, "check", video, "--band-height", f"{band:.3f}"]))
            if a.behind == "on" or check.get("recommend") == "behind":
                use_behind = True
                if check.get("bigY"):  # put the big word where the person covers about 40% of it
                    style["behind"]["bigY"] = round(float(check["bigY"]) * 100, 1)
                    # numbers are drawn in front, below the face: about a third of the frame under the head band
                    style["behind"]["frontY"] = round(min(70.0, max(52.0, style["behind"]["bigY"] + 32.0)), 1)
                    style_path = work / "style.json"
                    style_path.write_text(json.dumps(style, indent=1))
                    notes.append(f"big words placed at {style['behind']['bigY']}% of the height (the person covers {int(float(check.get('bandCoverage', 0)) * 100)}% of that band)")
            else:
                notes.append(f"behind mode skipped: {check.get('reason', 'subject check failed')}; the big words are drawn in front of the speaker instead")

    # ---- hard cuts: pages must not straddle them ----
    cuts_path = work / "cuts.json"
    cuts = []
    if not a.captions and not music and not audio_only and a.cuts == "auto":
        stamp = [video.name, video.stat().st_size, int(video.stat().st_mtime)]
        cached = json.loads(cuts_path.read_text()) if cuts_path.exists() else {}
        if cached.get("stamp") != stamp:
            with step("cuts"):
                found = last_json(run([sys.executable, HERE / "cuts.py", video, "--fps", str(probe_fps(video))]))
                if found.get("error"):
                    notes.append(f"cut detection skipped: {found['error']}")
                cached = {"stamp": stamp, "cuts": found.get("cuts", [])}
                cuts_path.write_text(json.dumps(cached))
        cuts = cached.get("cuts", [])
        if cuts:
            notes.append(f"{len(cuts)} hard cut(s) found: pages are split at them")

    # ---- group ----
    cap_path = work / "captions.json"
    srt_path = src.with_name(src.stem + ".srt")
    if a.captions:
        given = Path(a.captions).expanduser().resolve()
        if given != cap_path.resolve():
            shutil.copyfile(given, cap_path)
    else:
        cmd = [sys.executable, HERE / "group.py", words_path, "--style", style_path, "--out", cap_path, "--srt", srt_path]
        if music:  # music styles start their pages on the beat
            beats_path = work / "beats.json"
            with step("beats"):
                bt = last_json(run(py(HERE / "beats.py") + [src, "--out", beats_path]))
            if bt.get("bpm") and (bt.get("clarity") or 0) >= 0.25:
                cmd += ["--beats", beats_path]
                notes.append(f"beat grid: {bt['bpm']} BPM, {bt.get('beats')} beats (pulse clarity {bt.get('clarity')})")
            else:
                notes.append("no steady beat found in the audio: pages follow the words, not a beat grid")
        if cuts:
            cmd += ["--cuts", cuts_path]
        if a.max_words:
            cmd += ["--max-words", a.max_words]
        cmd += ["--emphasis", a.emphasis, "--numbers", a.numbers]
        if a.emphasis_words:
            cmd += ["--emphasis-words", a.emphasis_words]
        for r in a.replace:
            cmd += ["--replace", r]
        if a.clean:
            cmd += ["--clean"]
        with step("group"):
            run(cmd)
    # ---- placement: keep each page off the face and the hands ----
    placement = None
    if a.placement == "auto" and not audio_only and not music:
        cap = json.loads(cap_path.read_text())
        if a.captions and any("y" in p for p in cap["pages"]):
            notes.append("placement: the given captions already carry page positions (y); kept as they are")
        else:
            import placement as pl
            with step("placement"):
                if pl.ensure_tool() is None:
                    notes.append("placement needs macOS with the Xcode command line tools (vision-subject); every page keeps the style's y")
                else:
                    try:
                        pnotes, placement = pl.apply(video, cap, style, cap.get("cuts") or [])
                        notes += pnotes
                        cap_path.write_text(json.dumps(cap, ensure_ascii=False, indent=1))
                        if placement.get("pages"):
                            notes.append(f"placement: {placement['moved']} of {placement['pages']} pages moved off the preset y ({placement['changes']} position changes)")
                    except (RuntimeError, OSError) as e:
                        notes.append(f"placement skipped ({e}); every page keeps the style's y")
    # ---- behind mode, per shot: a close-up fills the frame, a wide shot leaves room. Decided for each shot, not once for the video ----
    needs_subject = bool(style.get("subject"))  # a front style that places words around the face (split) reads the same timeline
    if ((wants_behind and a.behind != "off") or needs_subject) and not music and not audio_only and sys.platform == "darwin":
        cap = json.loads(cap_path.read_text())
        if cap.get("cuts") or cap.get("shots") or needs_subject:
            import shots as sh
            with step("shots"):
                try:
                    if cap.get("shots"):
                        sh.mark_bigs(cap)
                        snotes = []
                    else:
                        snotes, _ = sh.apply(video, cap, style)
                    cap_path.write_text(json.dumps(cap, ensure_ascii=False, indent=1))
                    notes += snotes
                    if wants_behind and a.behind != "off":
                        use_behind = a.behind == "on" or any(x.get("behind") for x in cap["shots"])
                    if wants_behind and a.behind != "off" and not use_behind:
                        notes.append("behind mode skipped: no shot leaves room behind the speaker; the big words are drawn in front")
                except (RuntimeError, OSError) as e:
                    notes.append(f"per-shot behind check skipped ({e})")
    user_cap = src.with_name(src.stem + ".captions.json")
    if cap_path.resolve() != user_cap.resolve():
        shutil.copyfile(cap_path, user_cap)
    # ---- legibility: what is behind each page, and a palette from the footage (after grouping, before the render) ----
    style_dict = json.loads(style_path.read_text())
    if a.legibility != "off" or (a.palette != "off" and has_auto(style_dict)):
        with step("legibility"):
            lg = last_json(run(py(HERE / "legibility.py") + [cap_path, "--style", style_path, "--video", video,
                                                           "--palette", a.palette, "--legibility", a.legibility]))
        shutil.copyfile(cap_path, user_cap)
        s_ = lg.get("legibility") or {}
        if s_.get("pages"):
            notes.append(f"legibility ({s_['mode']}): {s_['boosted']} of {s_['pages']} pages need help, mean boost {s_['meanBoost']}, weakest contrast {s_['minContrast']}:1")
        if lg.get("palette"):
            notes.append(f"palette from the footage: accent {lg['palette']['accent']} ({lg['palette']['contrast']}:1 on the scene)")
    cap = json.loads(cap_path.read_text())
    picks = [f"{i}: {w['text']}" + (f" ({w['reason']})" if w.get("reason") else "") for i, p in enumerate(cap["pages"]) for w in p["words"] if w.get("emphasis")]
    if a.stop_after == "group":
        print(json.dumps({"captions": str(user_cap), "style": style["name"], "pages": len(cap["pages"]), "highlighted": picks,
                          "next": f"python3 scripts/emphasis.py \"{user_cap}\" --style {style['name']} --show",
                          "notes": notes, "seconds": times}, ensure_ascii=False, indent=1))
        return

    # ---- render ----
    preview = src.with_name(src.stem + ".preview.jpg")
    render = ["node", ROOT / "template" / "render.mjs", "--captions", cap_path, "--style", style_path]
    if use_behind:
        matte = work / "matte.mp4"
        vm = HERE / "vision-matte" / ".build" / "vision-matte"
        with step("matte"):
            minfo = last_json(run([vm, "matte", video, "--out", matte, "--quality", a.matte_quality]))
        ob, of = work / "overlay-behind.mov", work / "overlay-front.mov"
        with step("render"):
            run(render + ["--layer", "behind", "--out", ob])
            run(render + ["--layer", "front", "--out", of])
        # Drop the big words the person hides, then draw the behind layer again without them.
        min_vis = str((style.get("behind") or {}).get("minVisible", 0.55))
        pruned = work / "captions.pruned.json"
        with step("prune"):
            pr = last_json(run(py(HERE / "verify.py") + ["--captions", cap_path, "--style", style_path, "--overlay", of,
                                                         "--behind", ob, "--matte", matte, "--min-visible", min_vis, "--prune-to", pruned]))
        if pr.get("dropped"):
            shutil.copyfile(pruned, cap_path)
            shutil.copyfile(cap_path, src.with_name(src.stem + ".captions.json"))
            names = ", ".join(d["text"] for d in pr["dropped"])
            notes.append(f"dropped {len(pr['dropped'])} big words the person hid ({names}); {pr.get('kept', 0)} kept")
            with step("render"):
                run(render + ["--layer", "behind", "--out", ob])
        with step("composite"):
            run(["bash", HERE / "composite.sh", "--video", video, "--behind", ob, "--matte", matte, "--front", of, "--out", out, "--crf", a.crf])
        vcmd = py(HERE / "verify.py") + ["--video", out, "--source", video, "--captions", cap_path, "--style", style_path,
                                        "--overlay", of, "--behind", ob, "--matte", matte, "--out", preview]
        notes.append(f"matte: {minfo.get('msPerFrame', '?')} ms per frame at {minfo.get('quality', a.matte_quality)}")
    else:
        ov = work / "overlay.mov"
        comp = ["bash", HERE / "composite.sh", "--video", video, "--overlay", ov, "--out", out, "--crf", a.crf]
        with step("render"):
            run(render + ["--layer", "all", "--out", ov])
            blur = float(style.get("backdropBlur") or ((style.get("recipe") or {}).get("plate") or {}).get("backdropBlur") or 0)
            if blur > 0:  # frosted containers: the video is blurred under a mask of the containers
                mask = work / "mask.mov"
                run(render + ["--layer", "mask", "--out", mask])
                comp += ["--blur-mask", mask, "--blur", str(blur)]
        with step("composite"):
            run(comp)
        vcmd = py(HERE / "verify.py") + ["--video", out, "--source", video, "--captions", cap_path, "--style", style_path,
                                        "--overlay", ov, "--out", preview]
    with step("verify"):
        result = last_json(run(vcmd))

    minutes = cap["video"]["durationMs"] / 60000.0
    total = round(sum(times.values()), 1)
    rerender = f"python3 {Path(__file__).name} \"{src.name}\" --style <other-style>   # reuses the cached transcript"
    print(json.dumps({
        "video": str(out), "captions": str(src.with_name(src.stem + '.captions.json')), "srt": str(srt_path) if srt_path.exists() else None,
        "preview": str(preview) if preview.exists() else None, "style": style["name"], "behind": use_behind, "subjectCheck": check, "placement": placement, "cuts": cuts,
        "ok": result.get("ok"), "warnings": result.get("warnings", []), "behindVisibility": result.get("behind"),
        "highlighted": picks,
        "notes": notes, "seconds": times, "totalSeconds": total, "secondsPerMinuteOfVideo": round(total / max(minutes, 1e-6), 1),
        "rerender": rerender,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

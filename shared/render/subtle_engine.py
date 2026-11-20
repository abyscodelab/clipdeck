"""Subtle Caption Engine for ClipDeck.

Bridges ClipDeck EDL, WordTimestamps, and video rendering to the Subtle captioning system
(https://github.com/0xpratzyy/subtle). Supports 39 motion graphic styles (glide, punch,
terminal, glass, keyword, impact, bottom, cards, etc.), smart grouping, number normalization,
AI emphasis, and placement avoidance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from clipdeck.shared.ai.edl_schema import CaptionStyle
from clipdeck.shared.media.ffmpeg_utils import probe_media_file
from clipdeck.shared.transcription.base import WordTimestamp

logger = logging.getLogger(__name__)

POTENTIAL_SUBTLE_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "subtle",  # clipdeck/subtle
    Path.home() / ".claude" / "skills" / "subtle",            # ~/.claude/skills/subtle
    Path.home() / ".agents" / "skills" / "subtle",
]


def find_subtle_root() -> Path:
    """Locate the subtle skill root directory."""
    env_path = os.environ.get("SUBTLE_PATH")
    if env_path and Path(env_path).is_dir():
        return Path(env_path).resolve()

    for p in POTENTIAL_SUBTLE_PATHS:
        if (p / "scripts" / "subtle.py").exists() and (p / "styles").exists():
            return p.resolve()

    return (Path(__file__).resolve().parent.parent.parent / "subtle").resolve()


@dataclass(slots=True)
class SubtleRenderResult:
    """Result of subtle caption generation and video rendering."""

    video_path: Path
    captions_json_path: Path | None = None
    srt_path: Path | None = None
    preview_path: Path | None = None
    style_name: str = "glide"
    pages_count: int = 0
    warnings: list[str] = field(default_factory=list)
    render_mode: str = "remotion"  # 'remotion' or 'subtle_overlay'


class SubtleEngine:
    """Orchestrates Subtle captions generation, styling, and video rendering."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or find_subtle_root()
        self.scripts_dir = self.root_dir / "scripts"
        self.styles_dir = self.root_dir / "styles"
        self.template_dir = self.root_dir / "template"
        self.fonts_dir = self.root_dir / "fonts"

        # Determine python executable (prefer venv python with numpy/pillow)
        venv_py = Path(__file__).resolve().parent.parent.parent / ".venv" / "bin" / "python3"
        if venv_py.exists():
            self.python_bin = str(venv_py)
        else:
            self.python_bin = sys.executable

    def list_styles(self) -> list[dict[str, Any]]:
        """List all available subtle styles with metadata."""
        if not self.styles_dir.exists():
            return []

        styles = []
        for p in sorted(self.styles_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                variants = list((data.get("variants") or {}).keys())
                styles.append(
                    {
                        "name": data.get("name", p.stem),
                        "label": data.get("label", p.stem.title()),
                        "description": data.get("description", ""),
                        "group": data.get("group", "caption"),
                        "variants": variants,
                        "color": data.get("color", "#FFFFFF"),
                        "activeColor": data.get("activeColor", "#C8FF2E"),
                        "font": (data.get("font") or {}).get("family", "Montserrat ExtraBold"),
                    }
                )
            except Exception as e:
                logger.warning("Failed to parse style %s: %s", p, e)
        return styles

    def get_style(self, style_name: str) -> dict[str, Any]:
        """Load a subtle style JSON dictionary."""
        clean_name = style_name.split(":")[0]
        style_file = self.styles_dir / f"{clean_name}.json"
        if not style_file.exists():
            style_file = self.styles_dir / "glide.json"
        if style_file.exists():
            return json.loads(style_file.read_text(encoding="utf-8"))
        return {"name": "glide", "label": "Glide"}

    def prepare_words_json(
        self,
        words: list[WordTimestamp],
        output_file: Path,
        time_offset: float = 0.0,
        duration_sec: float = 15.0,
        width: int = 1080,
        height: int = 1920,
        fps: float = 30.0,
    ) -> Path:
        """Convert ClipDeck WordTimestamps into Subtle's words.json format."""
        adjusted_words = []
        for w in words:
            end_rel = w.end - time_offset
            if end_rel <= 0.0:
                continue
            start_rel = max(0.0, w.start - time_offset)
            adjusted_words.append(
                {
                    "text": w.word.strip(),
                    "startMs": int(round(start_rel * 1000.0)),
                    "endMs": int(round(end_rel * 1000.0)),
                    "prob": round(float(w.confidence or 0.99), 2),
                }
            )

        data = {
            "version": 1,
            "source": {
                "width": width,
                "height": height,
                "fps": round(fps, 2),
                "durationMs": int(round(duration_sec * 1000.0)),
            },
            "language": "en",
            "words": adjusted_words,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return output_file

    async def group_words(
        self,
        words_json_path: Path,
        style_name: str = "glide",
        out_captions_path: Path | None = None,
        out_srt_path: Path | None = None,
        emphasis: str = "auto",
        numbers: str = "auto",
        emphasis_words: str = "",
    ) -> tuple[Path, Path | None]:
        """Run Subtle's group.py to chunk words and compute emphasis and numbers."""
        clean_style = style_name.split(":")[0]
        style_file = self.styles_dir / f"{clean_style}.json"
        if not style_file.exists():
            style_file = self.styles_dir / "glide.json"

        if out_captions_path is None:
            out_captions_path = words_json_path.with_name(f"{words_json_path.stem}.captions.json")

        cmd = [
            self.python_bin,
            str(self.scripts_dir / "group.py"),
            str(words_json_path),
            "--style",
            str(style_file),
            "--out",
            str(out_captions_path),
            "--emphasis",
            emphasis,
            "--numbers",
            numbers,
        ]
        if out_srt_path:
            cmd.extend(["--srt", str(out_srt_path)])
        if emphasis_words:
            cmd.extend(["--emphasis-words", emphasis_words])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")
            logger.warning("Subtle group.py error: %s", err)
            raise RuntimeError(f"Subtle grouping failed: {err}")

        return out_captions_path, out_srt_path

    async def render(
        self,
        video_path: Path,
        words: list[WordTimestamp],
        caption_style: CaptionStyle | None = None,
        output_path: Path | None = None,
        time_offset: float = 0.0,
    ) -> SubtleRenderResult:
        """
        Render Subtle animated captions onto vertical video.
        Attempts Remotion motion graphic overlay render first; seamlessly falls back
        to Subtle-styled overlay burning if Remotion/Chrome is unavailable or sandboxed.
        """
        c_style = caption_style or CaptionStyle()
        style_name = c_style.style or "glide"
        if c_style.variant:
            style_name = f"{style_name}:{c_style.variant}"

        if output_path is None:
            output_path = video_path.with_name(f"{video_path.stem}_captioned.mp4")

        # Probe video dimensions & duration
        probe = await probe_media_file(video_path)
        v_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
        width = int(v_stream.get("width") or 1080)
        height = int(v_stream.get("height") or 1920)
        fps = 30.0
        try:
            r_fps = v_stream.get("r_frame_rate", "30/1")
            num, den = r_fps.split("/")
            fps = float(num) / float(den or 1)
        except Exception:
            pass

        duration = float(probe.get("format", {}).get("duration") or 15.0)

        # Temporary work folder
        work_dir = output_path.parent / f".subtle_work_{output_path.stem}"
        work_dir.mkdir(parents=True, exist_ok=True)
        words_json = work_dir / "words.json"
        captions_json = work_dir / "captions.json"
        srt_file = output_path.with_suffix(".srt")
        preview_jpg = output_path.with_name(f"{output_path.stem}.preview.jpg")

        self.prepare_words_json(
            words=words,
            output_file=words_json,
            time_offset=time_offset,
            duration_sec=duration,
            width=width,
            height=height,
            fps=fps,
        )

        # 1. Group words with Subtle's group.py
        try:
            await self.group_words(
                words_json_path=words_json,
                style_name=style_name,
                out_captions_path=captions_json,
                out_srt_path=srt_file,
                emphasis=c_style.emphasis,
                numbers=c_style.numbers,
                emphasis_words=c_style.emphasis_words,
            )
        except Exception as e:
            logger.warning("Subtle group.py failed, will proceed with raw timings: %s", e)

        # 2. Attempt Remotion motion graphics render via subtle.py
        remotion_success = False
        try:
            logger.info("Attempting Subtle Remotion motion render with style '%s'...", style_name)
            subtle_script = self.scripts_dir / "subtle.py"
            subtle_cmd = [
                self.python_bin,
                str(subtle_script),
                str(video_path),
                "--words",
                str(words_json),
                "--style",
                style_name,
                "--out",
                str(output_path),
                "--work",
                str(work_dir),
                "--aspect",
                "source",
                "--cuts",
                c_style.cuts,
                "--placement",
                c_style.placement,
                "--behind",
                c_style.behind,
                "--emphasis",
                c_style.emphasis,
                "--numbers",
                c_style.numbers,
            ]
            if c_style.emphasis_words:
                subtle_cmd.extend(["--emphasis-words", c_style.emphasis_words])

            proc = await asyncio.create_subprocess_exec(
                *subtle_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                logger.info("Subtle Remotion motion render succeeded!")
                remotion_success = True
            else:
                err = stderr.decode("utf-8", errors="replace")
                logger.info("Remotion motion render skipped (%s). Using Subtle overlay burn mode.", err[:200])
        except Exception as e:
            logger.info("Remotion pipeline exception: %s. Using Subtle overlay burn mode.", e)

        # 3. Fallback to Subtle Overlay Burn Engine if Remotion not possible
        if not remotion_success:
            logger.info("Rendering Subtle captions via deterministic overlay burn engine...")
            await self.render_subtle_overlay_burn(
                video_path=video_path,
                captions_json_path=captions_json,
                words=words,
                output_path=output_path,
                style_name=style_name,
                time_offset=time_offset,
                c_style=c_style,
                width=width,
                height=height,
                duration=duration,
                work_dir=work_dir,
            )

        # Keep captions and srt next to the output video
        final_captions = output_path.with_name(f"{output_path.stem}.captions.json")
        if captions_json.exists():
            shutil.copyfile(captions_json, final_captions)

        pages_count = 0
        if captions_json.exists():
            try:
                cap_data = json.loads(captions_json.read_text(encoding="utf-8"))
                pages_count = len(cap_data.get("pages", []))
            except Exception:
                pass

        # Clean work directory
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

        return SubtleRenderResult(
            video_path=output_path,
            captions_json_path=final_captions if final_captions.exists() else None,
            srt_path=srt_file if srt_file.exists() else None,
            preview_path=preview_jpg if preview_jpg.exists() else None,
            style_name=style_name,
            pages_count=pages_count,
            render_mode="remotion" if remotion_success else "subtle_overlay",
        )

    async def render_subtle_overlay_burn(
        self,
        video_path: Path,
        captions_json_path: Path,
        words: list[WordTimestamp],
        output_path: Path,
        style_name: str,
        time_offset: float,
        c_style: CaptionStyle,
        width: int,
        height: int,
        duration: float,
        work_dir: Path,
    ) -> Path:
        """
        Burn animated Subtle captions onto vertical video using Pillow typography
        and FFmpeg's concat + overlay demuxer. Works on every standard FFmpeg build.
        """
        style_dict = self.get_style(style_name)

        # Font configuration from Subtle style
        font_file = (style_dict.get("font") or {}).get("file", "Montserrat-Black.ttf")
        font_path = self.fonts_dir / font_file
        if not font_path.exists():
            font_path = self.fonts_dir / "Montserrat-Bold.ttf"
        if not font_path.exists():
            font_path = self.fonts_dir / "Inter-Bold.ttf"

        size_pct = float(style_dict.get("size", 5.2))
        base_font_size = int(round((size_pct / 100.0) * width * 1.15))
        active_font_size = int(round(base_font_size * 1.10))

        font_normal = ImageFont.truetype(str(font_path), base_font_size)
        font_active = ImageFont.truetype(str(font_path), active_font_size)

        # Parse colors
        def hex_to_rgba(hex_str: str, default: tuple[int, int, int, int] = (255, 255, 255, 255)) -> tuple[int, int, int, int]:
            if not hex_str or not hex_str.startswith("#"):
                return default
            h = hex_str.lstrip("#")
            if len(h) == 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
            return default

        primary_hex = style_dict.get("color", "#FFFFFF")
        active_hex = style_dict.get("activeColor", "#C8FF2E")
        if isinstance(active_hex, dict):
            active_hex = active_hex.get("fallback", "#F5F258")

        color_normal = hex_to_rgba(primary_hex, (255, 255, 255, 255))
        color_active = hex_to_rgba(active_hex, (200, 255, 46, 255))
        color_shadow = (0, 0, 0, 190)

        # Position (percentage from top)
        pos_y_pct = float((style_dict.get("position") or {}).get("y", 65.0))
        target_y = int(round((pos_y_pct / 100.0) * height))
        is_upper = style_dict.get("case") == "upper"

        # Build list of timed events from captions.json or words
        events = []
        if captions_json_path.exists():
            try:
                cap_data = json.loads(captions_json_path.read_text(encoding="utf-8"))
                for page in cap_data.get("pages", []):
                    p_words = page.get("words", [])
                    if not p_words:
                        continue
                    for active_idx, aw in enumerate(p_words):
                        s_sec = max(0.0, aw["startMs"] / 1000.0)
                        e_sec = max(s_sec + 0.05, aw["endMs"] / 1000.0)
                        events.append((s_sec, e_sec, p_words, active_idx))
            except Exception as e:
                logger.warning("Error parsing captions.json for overlay burn: %s", e)

        # Fallback if no events from captions.json
        if not events and words:
            adj = [w for w in words if (w.end - time_offset) >= 0.0]
            for i in range(0, len(adj), 4):
                grp = adj[i : i + 4]
                p_words = [
                    {
                        "text": w.word,
                        "startMs": int((w.start - time_offset) * 1000),
                        "endMs": int((w.end - time_offset) * 1000),
                        "emphasis": False,
                    }
                    for w in grp
                ]
                for active_idx, aw in enumerate(p_words):
                    s_sec = max(0.0, aw["startMs"] / 1000.0)
                    e_sec = max(s_sec + 0.05, aw["endMs"] / 1000.0)
                    events.append((s_sec, e_sec, p_words, active_idx))

        frames_dir = work_dir / "burn_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        empty_frame = frames_dir / "empty.png"
        Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(empty_frame)

        # Generate each frame and concat list
        concat_entries = []
        last_t = 0.0

        for idx, (s_sec, e_sec, p_words, active_idx) in enumerate(events):
            if s_sec > last_t:
                gap_dur = round(s_sec - last_t, 3)
                if gap_dur >= 0.03:
                    concat_entries.append((empty_frame.name, gap_dur))

            frame_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(frame_img)

            # Measure full line width
            word_boxes = []
            for j, w in enumerate(p_words):
                txt = w["text"].upper() if is_upper else w["text"]
                f = font_active if j == active_idx else font_normal
                bbox = draw.textbbox((0, 0), txt, font=f)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                word_boxes.append((txt, tw, th, f, j == active_idx, bool(w.get("emphasis"))))

            space_w = base_font_size // 3
            total_w = sum(wb[1] for wb in word_boxes) + space_w * (len(word_boxes) - 1)
            start_x = max(40, (width - total_w) // 2)

            curr_x = start_x
            for txt, tw, th, f, is_act, is_emph in word_boxes:
                col = color_active if (is_act or is_emph) else color_normal
                # Soft drop shadow
                draw.text((curr_x + 3, target_y + 3), txt, font=f, fill=color_shadow)
                draw.text((curr_x, target_y), txt, font=f, fill=col)
                curr_x += tw + space_w

            frame_path = frames_dir / f"f_{idx:04d}.png"
            frame_img.save(frame_path)

            event_dur = max(0.05, round(e_sec - s_sec, 3))
            concat_entries.append((frame_path.name, event_dur))
            last_t = e_sec

        # Trailing empty frame if needed
        if duration > last_t:
            concat_entries.append((empty_frame.name, round(duration - last_t, 3)))

        # Write concat.txt
        concat_txt = frames_dir / "concat.txt"
        lines = ["ffconcat version 1.0"]
        for fname, dur in concat_entries:
            lines.append(f"file '{fname}'")
            lines.append(f"duration {dur:.3f}")
        # Repeat final entry per concat demuxer spec
        if concat_entries:
            lines.append(f"file '{concat_entries[-1][0]}'")

        concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # FFmpeg composite command using overlay
        burn_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(video_path),
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0[v]",
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        logger.info("Executing Subtle overlay burn with %d entries...", len(concat_entries))
        proc = await asyncio.create_subprocess_exec(
            *burn_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.error("Subtle overlay burn failed: %s", err_msg)
            raise RuntimeError(f"Subtle overlay burn failed: {err_msg}")

        return output_path

    def generate_subtle_ass(
        self,
        captions_json_path: Path,
        words: list[WordTimestamp],
        output_path: Path,
        style_name: str,
        time_offset: float,
        c_style: CaptionStyle,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        """
        Generate an ASS subtitle file formatted matching Subtle's styling parameters
        (font family, font size, primary color, active highlight color, shadow, position).
        """
        style_dict = self.get_style(style_name)

        font_family = (style_dict.get("font") or {}).get("family", c_style.font or "Montserrat ExtraBold")
        size_pct = float(style_dict.get("size", 4.5))
        font_size = int(round((size_pct / 100.0) * width * 1.05))

        def hex_to_ass(hex_str: str, default: str = "&H00FFFFFF") -> str:
            if not hex_str or not hex_str.startswith("#"):
                return default
            h = hex_str.lstrip("#")
            if len(h) == 6:
                r, g, b = h[0:2], h[2:4], h[4:6]
                return f"&H00{b}{g}{r}".upper()
            return default

        primary_hex = style_dict.get("color", "#FFFFFF")
        active_hex = style_dict.get("activeColor", "#C8FF2E")
        if isinstance(active_hex, dict):
            active_hex = active_hex.get("fallback", "#F5F258")

        ass_primary = hex_to_ass(primary_hex, c_style.primary_color)
        ass_highlight = hex_to_ass(active_hex, c_style.highlight_color)
        ass_outline = "&H00000000"

        pos_y_pct = float((style_dict.get("position") or {}).get("y", 65.0))
        margin_v = int(round((1.0 - (pos_y_pct / 100.0)) * height))
        margin_v = max(180, min(height - 200, margin_v))

        is_upper = style_dict.get("case") == "upper"

        ass_header = f"""[Script Info]
Title: ClipDeck Subtle Captions ({style_name})
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{font_size},{ass_primary},&H000000FF,{ass_outline},&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: list[str] = []

        def _fmt_time(sec: float) -> str:
            hrs = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            secs = int(sec % 60)
            cs = int(round((sec - int(sec)) * 100))
            if cs >= 100:
                secs += 1
                cs = 0
            return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"

        if captions_json_path.exists():
            try:
                cap_data = json.loads(captions_json_path.read_text(encoding="utf-8"))
                for page in cap_data.get("pages", []):
                    page_words = page.get("words", [])
                    if not page_words:
                        continue
                    for active_idx, active_w in enumerate(page_words):
                        w_start = _fmt_time(active_w["startMs"] / 1000.0)
                        w_end = _fmt_time(active_w["endMs"] / 1000.0)
                        line_parts = []
                        for j, w in enumerate(page_words):
                            txt = w["text"].upper() if is_upper else w["text"]
                            if j == active_idx:
                                line_parts.append(f"{{\\c{ass_highlight}&\\fscx112\\fscy112}}{txt}{{\\r}}")
                            elif w.get("emphasis"):
                                line_parts.append(f"{{\\c{ass_highlight}&}}{txt}{{\\r}}")
                            else:
                                line_parts.append(f"{{\\c{ass_primary}&}}{txt}")
                        events.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{' '.join(line_parts)}")
            except Exception as e:
                logger.warning("Error reading captions_json for ASS events: %s", e)

        if not events and words:
            adj = [w for w in words if (w.end - time_offset) >= 0.0]
            for i in range(0, len(adj), 4):
                grp = adj[i : i + 4]
                for active_idx, active_w in enumerate(grp):
                    s = _fmt_time(max(0.0, active_w.start - time_offset))
                    e = _fmt_time(max(0.0, active_w.end - time_offset))
                    parts = []
                    for j, w in enumerate(grp):
                        t = w.word.upper() if is_upper else w.word
                        if j == active_idx:
                            parts.append(f"{{\\c{ass_highlight}&\\fscx112\\fscy112}}{t}{{\\r}}")
                        else:
                            parts.append(f"{{\\c{ass_primary}&}}{t}")
                    events.append(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{' '.join(parts)}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = ass_header + "\n".join(events) + "\n"
        output_path.write_text(content, encoding="utf-8")
        return output_path

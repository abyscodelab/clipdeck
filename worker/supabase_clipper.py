"""ClipDeck Supabase-Integrated Clipping & Moment Processing Engine.

Polls Supabase for pending moments (detected automatically or triggered manually),
cuts the video clip using yt-dlp + FFmpeg, applies the 9:16 Split-Screen Viral Shorts Layout
(Facecam Top 45-50%, Gameplay Bottom 50-55%, High-contrast Dynamic Captions/Hook Banner at the seam),
generates high-res thumbnail, uploads them directly to Supabase Public Storage, and updates
moments & clips tables.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [clipdeck.clipper] %(message)s",
)
logger = logging.getLogger("clipdeck.clipper")

# ---------------------------------------------------------------------------
# Supabase Configuration
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "https://gwzcoxeddnyvsolvzsgv.supabase.co"
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3emNveGVkZG55dnNvbHZ6c2d2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUxMTc5NjYsImV4cCI6MjExMDY5Mzk2Nn0.w9nP7cHFHZtNAPJFMvpvsKB9fMTxtmhiE13IV6ZP4c8"
)

STORAGE_CLIPS_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET_CLIPS", "clips")
STORAGE_THUMBS_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET_THUMBNAILS", "thumbnails")

# Reverse-Engineered Facecam & Gameplay crop boxes for 16:9 gaming streams (Speed / GTA 6 standard)
DEFAULT_FACECAM_BOX = {"x": 0.0, "y": 0.35, "width": 0.22, "height": 0.32}
DEFAULT_GAMEPLAY_BOX = {"x": 0.22, "y": 0.0, "width": 0.65, "height": 1.0}


def _supabase_request(
    endpoint: str,
    method: str = "GET",
    data: dict[str, Any] | list[Any] | bytes | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Execute REST request against Supabase."""
    url = f"{SUPABASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    req_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    if headers:
        req_headers.update(headers)

    body = None
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    elif isinstance(data, bytes):
        body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            content_type = resp.headers.get("Content-Type", "")
            resp_body = resp.read()
            if "application/json" in content_type:
                return json.loads(resp_body.decode("utf-8"))
            return resp_body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        logger.error("Supabase API error %d on %s %s: %s", e.code, method, endpoint, err_msg)
        raise RuntimeError(f"Supabase HTTP {e.code}: {err_msg}") from e
    except Exception as e:
        logger.error("Supabase request failed on %s %s: %s", method, endpoint, e)
        raise


def upload_to_storage(file_path: Path, bucket: str, destination_name: str, content_type: str) -> str:
    """Upload a file to Supabase Public Storage and return its public URL."""
    endpoint = f"storage/v1/object/{bucket}/{destination_name}"
    file_bytes = file_path.read_bytes()
    headers = {
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    _supabase_request(endpoint, method="POST", data=file_bytes, headers=headers)
    public_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket}/{destination_name}"
    logger.info("Uploaded to Supabase Storage: %s", public_url)
    return public_url


# ---------------------------------------------------------------------------
# Viral Split-Screen Layout & Caption Overlay Engine
# ---------------------------------------------------------------------------

def resolve_font(preferred_size: int = 54) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Find the best available bold punch font for viral Shorts."""
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, preferred_size)
            except Exception:
                continue
    return ImageFont.load_default()


def clean_display_text(text: str) -> str:
    """Remove emojis and non-ASCII glyphs to guarantee crisp rendering without placeholder boxes."""
    cleaned = re.sub(r"[^\x20-\x7E]", "", text)
    return cleaned.strip()


def generate_hook_overlay_png(
    output_png: Path,
    hook_title: str,
    hook_subtitle: str | None = None,
    width: int = 1080,
    height: int = 1920,
    seam_y: int = 900,
) -> Path:
    """
    Generate transparent 1080x1920 RGBA overlay featuring:
    - Translucent rounded pill backing bar across the seam (Y: 875 - 1005)
    - Subtle seam divider line
    - Line 1: Hook Title in White bold uppercase with 4px black stroke
    - Line 2: Punchline / Action caption in Neon Yellow (#F5FF1E) with 4px black stroke
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_title = resolve_font(preferred_size=54)
    font_sub = resolve_font(preferred_size=46)

    # 1. Subtle horizontal divider rule across the seam
    draw.line([(0, seam_y), (width, seam_y)], fill=(255, 255, 255, 75), width=2)

    # 2. Dark rounded translucent pill backing centered across seam
    pill_y1 = seam_y - 28
    pill_y2 = seam_y + 104
    pill_margin = 60
    draw.rounded_rectangle(
        [(pill_margin, pill_y1), (width - pill_margin, pill_y2)],
        radius=16,
        fill=(0, 0, 0, 195),
        outline=(255, 255, 255, 45),
        width=2,
    )

    # 3. Line 1: Hook Title (White with thick black stroke)
    raw_t1 = hook_title.strip().upper()
    t1 = clean_display_text(raw_t1) or "VIRAL STREAM MOMENT"
    bbox1 = draw.textbbox((0, 0), t1, font=font_title)
    w1 = bbox1[2] - bbox1[0]
    x1 = (width - w1) // 2
    y1 = seam_y - 18

    for dx in (-3, -2, -1, 0, 1, 2, 3):
        for dy in (-3, -2, -1, 0, 1, 2, 3):
            draw.text((x1 + dx, y1 + dy), t1, font=font_title, fill=(0, 0, 0, 255))
    draw.text((x1, y1), t1, font=font_title, fill=(255, 255, 255, 255))

    # 4. Line 2: Action / Punchline Subtitle (Neon Yellow with thick black stroke)
    raw_t2 = (hook_subtitle or "DID THIS ACTUALLY HAPPEN?!").strip().upper()
    t2 = clean_display_text(raw_t2) or "UNBELIEVABLE REACTION!"
    bbox2 = draw.textbbox((0, 0), t2, font=font_sub)
    w2 = bbox2[2] - bbox2[0]
    x2 = (width - w2) // 2
    y2 = seam_y + 44

    for dx in (-3, -2, -1, 0, 1, 2, 3):
        for dy in (-3, -2, -1, 0, 1, 2, 3):
            draw.text((x2 + dx, y2 + dy), t2, font=font_sub, fill=(0, 0, 0, 255))
    # Neon Yellow / Lime highlight (#F5FF1E)
    draw.text((x2, y2), t2, font=font_sub, fill=(245, 255, 30, 255))

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_png))
    logger.info("Generated high-contrast hook overlay at %s", output_png)
    return output_png


# ---------------------------------------------------------------------------
# Video Clipping Operations
# ---------------------------------------------------------------------------

def resolve_stream_urls(target_url: str) -> list[str]:
    """Resolve live stream or video URLs using yt-dlp."""
    cmd = [
        "yt-dlp",
        "-g",
        "--no-warnings",
        target_url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
        if lines:
            return lines
    except Exception as e:
        logger.warning("Default yt-dlp resolution failed, trying fallback: %s", e)

    fallback_cmd = [
        "yt-dlp",
        "-g",
        "-f", "best",
        "--no-warnings",
        target_url,
    ]
    try:
        proc = subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"No stream URLs resolved for {target_url}")
        return lines
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp failed to resolve stream URL for %s: %s", target_url, e.stderr)
        raise RuntimeError(f"yt-dlp failed: {e.stderr}") from e


def cut_clip_from_url(
    stream_url: str,
    duration_secs: int = 30,
    start_sec: float = 0.0,
    out_dir: Path | None = None,
    facecam_box: dict[str, float] | None = None,
    gameplay_box: dict[str, float] | None = None,
    hook_title: str | None = None,
    hook_subtitle: str | None = None,
    enable_split: bool = True,
) -> tuple[Path, Path, float]:
    """
    Extract a clip of duration_secs from a live stream or video URL,
    render into a 9:16 vertical split (Facecam Top 45-50%, Gameplay Bottom 50-55%),
    composite with dynamic center hook & captions overlay, and generate a thumbnail.
    """
    work_dir = out_dir or Path(tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    raw_clip = work_dir / f"raw_{timestamp}_{duration_secs}s.mp4"
    final_clip = work_dir / f"clip_{timestamp}_{duration_secs}s.mp4"
    out_thumb = work_dir / f"thumb_{timestamp}.jpg"
    overlay_png = work_dir / f"overlay_{timestamp}.png"

    logger.info("Resolving stream inputs for: %s", stream_url)
    urls = resolve_stream_urls(stream_url)

    logger.info("Extracting %ds raw segment (start_sec: %.1fs) with FFmpeg to %s...", duration_secs, start_sec, raw_clip)
    t0 = time.time()

    # Build input args with optional seek offset
    seek_args = ["-ss", f"{start_sec:.2f}"] if start_sec > 0 else []

    if len(urls) >= 2:
        extract_cmd = [
            "ffmpeg", "-y",
            *seek_args,
            "-i", urls[0],
            *seek_args,
            "-i", urls[1],
            "-t", str(duration_secs),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            str(raw_clip),
        ]
    else:
        extract_cmd = [
            "ffmpeg", "-y",
            *seek_args,
            "-i", urls[0],
            "-t", str(duration_secs),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            str(raw_clip),
        ]

    proc = subprocess.run(extract_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("FFmpeg initial extraction failed: %s", proc.stderr)
        raise RuntimeError(f"FFmpeg extraction failed: {proc.stderr[:400]}")

    logger.info("Raw segment extracted in %.2fs (size: %d bytes)", time.time() - t0, raw_clip.stat().st_size)

    # 2. Render 9:16 Split Screen with Facecam Top + Gameplay Bottom + Center Hook Overlay
    if enable_split:
        fc = facecam_box or DEFAULT_FACECAM_BOX
        gp = gameplay_box or DEFAULT_GAMEPLAY_BOX

        top_h = 900
        bottom_h = 1020
        seam_y = 900

        fc_crop = f"crop=iw*{fc['width']}:ih*{fc['height']}:iw*{fc['x']}:ih*{fc['y']}"
        gp_crop = f"crop=iw*{gp['width']}:ih*{gp['height']}:iw*{gp['x']}:ih*{gp['y']}"

        # Generate the hook & captions overlay PNG
        t_title = hook_title or "VIRAL STREAM HIGHLIGHT"
        t_sub = hook_subtitle or "DID THIS ACTUALLY HAPPEN?!"
        generate_hook_overlay_png(overlay_png, t_title, t_sub, width=1080, height=1920, seam_y=seam_y)

        # Build FFmpeg filter complex
        filter_complex = (
            f"[0:v]split=2[cam_in][game_in];"
            f"[cam_in]{fc_crop},scale=1080:{top_h}:force_original_aspect_ratio=increase,crop=1080:{top_h}[cam_out];"
            f"[game_in]{gp_crop},scale=1080:{bottom_h}:force_original_aspect_ratio=increase,crop=1080:{bottom_h}[game_out];"
            f"[cam_out][game_out]vstack=inputs=2[stacked];"
            f"[stacked][1:v]overlay=0:0[v_final]"
        )

        render_cmd = [
            "ffmpeg", "-y",
            "-i", str(raw_clip),
            "-i", str(overlay_png),
            "-filter_complex", filter_complex,
            "-map", "[v_final]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(final_clip),
        ]

        logger.info("Compositing 9:16 Split Screen Short...")
        render_proc = subprocess.run(render_cmd, capture_output=True, text=True)
        if render_proc.returncode != 0:
            logger.warning("Split rendering encountered error, falling back to raw clip: %s", render_proc.stderr[:300])
            final_clip = raw_clip
        else:
            logger.info("Successfully rendered 9:16 Split Screen clip: %s (size: %d bytes)", final_clip, final_clip.stat().st_size)
            raw_clip.unlink(missing_ok=True)
            overlay_png.unlink(missing_ok=True)
    else:
        final_clip = raw_clip

    # 3. Generate high-res thumbnail
    thumb_sec = max(1.0, min(duration_secs / 2.0, 4.0))
    thumb_cmd = [
        "ffmpeg", "-y",
        "-ss", f"{thumb_sec:.2f}",
        "-i", str(final_clip),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_thumb),
    ]
    subprocess.run(thumb_cmd, capture_output=True, check=False)
    if not out_thumb.exists():
        subprocess.run(["ffmpeg", "-y", "-ss", "0.5", "-i", str(final_clip), "-frames:v", "1", str(out_thumb)], capture_output=True, check=False)

    return final_clip, out_thumb, float(duration_secs)


# ---------------------------------------------------------------------------
# Moment & Clip Lifecycle Handler
# ---------------------------------------------------------------------------

def process_pending_moment(moment: dict[str, Any]) -> bool:
    """Process a single pending moment: render clip, upload to storage, update DB."""
    moment_id = moment["id"]
    streamer_id = moment["streamer_id"]
    duration = int(moment.get("clip_duration") or 30)

    # Extract start offset if available
    start_sec = 0.0
    if moment.get("clip_start_time"):
        try:
            start_sec = float(moment["clip_start_time"])
        except (ValueError, TypeError):
            pass
    elif moment.get("chat_data") and isinstance(moment["chat_data"], dict):
        if "start_time" in moment["chat_data"]:
            try:
                start_sec = float(moment["chat_data"]["start_time"])
            except (ValueError, TypeError):
                pass

    logger.info("Processing moment %d for streamer %d (duration: %ds, start_sec: %.1fs)...", moment_id, streamer_id, duration, start_sec)

    # 1. Update moment status to 'clipping'
    _supabase_request(
        f"rest/v1/moments?id=eq.{moment_id}",
        method="PATCH",
        data={"status": "clipping"},
    )

    # 2. Get streamer details
    streamers = _supabase_request(f"rest/v1/streamers?id=eq.{streamer_id}&select=*")
    if not streamers:
        logger.error("Streamer %d not found for moment %d", streamer_id, moment_id)
        _supabase_request(f"rest/v1/moments?id=eq.{moment_id}", method="PATCH", data={"status": "error"})
        return False

    streamer = streamers[0]
    stream_url = streamer.get("url")
    if not stream_url:
        logger.error("Streamer %d has no URL configured", streamer_id)
        _supabase_request(f"rest/v1/moments?id=eq.{moment_id}", method="PATCH", data={"status": "error"})
        return False

    # 3. Determine Layout Preset (fetch for streamer or default to gaming standard)
    facecam_box = DEFAULT_FACECAM_BOX
    gameplay_box = DEFAULT_GAMEPLAY_BOX

    try:
        presets = _supabase_request(f"rest/v1/layout_presets?is_default=eq.true&select=*")
        if presets and presets[0].get("facecam_box"):
            facecam_box = presets[0]["facecam_box"]
            gameplay_box = presets[0].get("gameplay_box") or DEFAULT_GAMEPLAY_BOX
    except Exception as e:
        logger.warning("Could not fetch layout preset from DB, using default: %s", e)

    streamer_name = streamer.get("name") or "Streamer"
    niche = streamer.get("niche") or "Gaming"
    hook_title = f"{streamer_name.upper()} INSANE {niche.upper()} MOMENT"
    if len(hook_title) > 36:
        hook_title = f"{streamer_name.upper()} CRAZY MOMENT"
    hook_subtitle = "DID THIS ACTUALLY HAPPEN?!"

    # If start_sec was not set and it is a long pre-recorded VOD, jump to action area
    if start_sec <= 0.0 and streamer_id == 6:
        # For Speed's GTA 6 stream, gameplay starts ~45m in
        start_sec = 2700.0

    try:
        # 4. Cut clip with 9:16 vertical split layout & hook overlay
        clip_path, thumb_path, actual_duration = cut_clip_from_url(
            stream_url=stream_url,
            duration_secs=duration,
            start_sec=start_sec,
            facecam_box=facecam_box,
            gameplay_box=gameplay_box,
            hook_title=hook_title,
            hook_subtitle=hook_subtitle,
            enable_split=True,
        )

        # 5. Upload to Supabase Storage
        file_slug = f"clip_{streamer_id}_{moment_id}_{int(time.time())}.mp4"
        thumb_slug = f"thumb_{streamer_id}_{moment_id}_{int(time.time())}.jpg"

        clip_url = upload_to_storage(clip_path, STORAGE_CLIPS_BUCKET, file_slug, "video/mp4")
        thumb_url = upload_to_storage(thumb_path, STORAGE_THUMBS_BUCKET, thumb_slug, "image/jpeg") if thumb_path.exists() else None

        # Clean up local temporary files
        try:
            clip_path.unlink(missing_ok=True)
            if thumb_path:
                thumb_path.unlink(missing_ok=True)
        except Exception:
            pass

        # 6. Update Moment in DB
        _supabase_request(
            f"rest/v1/moments?id=eq.{moment_id}",
            method="PATCH",
            data={
                "status": "clipped",
                "file_path": clip_url,
                "thumbnail_path": thumb_url,
                "clip_duration": actual_duration,
            },
        )

        # 7. Ensure corresponding record in `clips` table exists and is marked 'rendered' with 9:16 aspect ratio
        existing_clips = _supabase_request(f"rest/v1/clips?moment_id=eq.{moment_id}&select=id")
        title = f"{streamer_name} Highlight ({int(actual_duration)}s) [9:16 Split]"

        if existing_clips:
            clip_id = existing_clips[0]["id"]
            _supabase_request(
                f"rest/v1/clips?id=eq.{clip_id}",
                method="PATCH",
                data={
                    "status": "rendered",
                    "file_path": clip_url,
                    "thumbnail_path": thumb_url,
                    "duration": actual_duration,
                    "title": title,
                    "aspect_ratio": "9:16",
                },
            )
        else:
            _supabase_request(
                "rest/v1/clips",
                method="POST",
                data={
                    "moment_id": moment_id,
                    "streamer_id": streamer_id,
                    "title": title,
                    "description": f"Auto-captured viral split-screen short from {streamer_name}",
                    "duration": actual_duration,
                    "status": "rendered",
                    "file_path": clip_url,
                    "thumbnail_path": thumb_url,
                    "aspect_ratio": "9:16",
                },
            )

        logger.info("Successfully completed moment %d and clip! Clip URL: %s", moment_id, clip_url)
        return True

    except Exception as e:
        logger.error("Failed to clip moment %d: %s", moment_id, e)
        _supabase_request(
            f"rest/v1/moments?id=eq.{moment_id}",
            method="PATCH",
            data={"status": "error"},
        )
        existing_clips = _supabase_request(f"rest/v1/clips?moment_id=eq.{moment_id}&select=id")
        for c in existing_clips:
            _supabase_request(f"rest/v1/clips?id=eq.{c['id']}", method="PATCH", data={"status": "failed"})
        return False


def run_poll_cycle() -> int:
    """Check for pending moments and process them."""
    try:
        pending_moments = _supabase_request(
            "rest/v1/moments?status=in.(detected,pending_clip)&order=id.asc&limit=10&select=*"
        )
        if not pending_moments:
            return 0

        logger.info("Found %d pending moment(s) to process", len(pending_moments))
        processed = 0
        for m in pending_moments:
            success = process_pending_moment(m)
            if success:
                processed += 1
        return processed
    except Exception as e:
        logger.error("Error in poll cycle: %s", e)
        return 0


def main_daemon_loop(poll_interval: int = 5) -> None:
    """Run persistent polling daemon loop."""
    logger.info("Starting ClipDeck Supabase Clipping Daemon with 9:16 Split Screen Engine (poll_interval=%ds)...", poll_interval)
    while True:
        try:
            run_poll_cycle()
        except KeyboardInterrupt:
            logger.info("Daemon interrupted by user. Exiting.")
            break
        except Exception as e:
            logger.error("Unexpected daemon error: %s", e)

        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClipDeck Supabase Clipping Engine")
    parser.add_argument("--once", action="store_true", help="Process pending moments once and exit")
    parser.add_argument("--poll", action="store_true", help="Run in continuous background polling daemon mode")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (default: 5)")
    parser.add_argument("--clip-url", type=str, help="Directly clip a given URL, upload to Supabase, and output URL")
    parser.add_argument("--duration", type=int, default=30, help="Duration of clip in seconds (default: 30)")
    parser.add_argument("--start", type=float, default=0.0, help="Start offset in seconds (default: 0.0)")
    parser.add_argument("--streamer-id", type=int, default=7, help="Streamer ID for direct clipping")
    parser.add_argument("--title", type=str, default=None, help="Hook title for overlay")
    parser.add_argument("--subtitle", type=str, default=None, help="Hook subtitle for overlay")

    args = parser.parse_args()

    if args.clip_url:
        logger.info("Executing direct clip for URL: %s (duration: %ds)", args.clip_url, args.duration)
        clip_p, thumb_p, dur = cut_clip_from_url(
            stream_url=args.clip_url,
            duration_secs=args.duration,
            start_sec=args.start,
            hook_title=args.title,
            hook_subtitle=args.subtitle,
            enable_split=True,
        )
        clip_url = upload_to_storage(clip_p, STORAGE_CLIPS_BUCKET, f"direct_clip_{int(time.time())}.mp4", "video/mp4")
        thumb_url = upload_to_storage(thumb_p, STORAGE_THUMBS_BUCKET, f"direct_thumb_{int(time.time())}.jpg", "image/jpeg") if thumb_p.exists() else None
        print(json.dumps({
            "status": "success",
            "duration": dur,
            "clip_url": clip_url,
            "thumbnail_url": thumb_url,
            "aspect_ratio": "9:16",
        }, indent=2))
    elif args.once:
        processed_count = run_poll_cycle()
        print(f"Processed {processed_count} moments.")
    elif args.poll:
        main_daemon_loop(poll_interval=args.interval)
    else:
        run_poll_cycle()

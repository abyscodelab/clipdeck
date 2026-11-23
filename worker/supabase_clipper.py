"""ClipDeck Supabase-Integrated Clipping & Moment Processing Engine.

Polls Supabase for pending moments (detected automatically or triggered manually),
cuts the video clip using yt-dlp + FFmpeg, generates high-res thumbnail,
uploads them directly to Supabase Public Storage, and updates moments & clips tables.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

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
        with urllib.request.urlopen(req, timeout=30) as resp:
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
# Video Clipping Operations
# ---------------------------------------------------------------------------

def resolve_stream_urls(target_url: str) -> list[str]:
    """Resolve live stream or video URLs using yt-dlp."""
    # First attempt: default best stream
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

    # Fallback attempt with generic best format
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
    out_dir: Path | None = None,
) -> tuple[Path, Path, float]:
    """Extract a clip of duration_secs from a live stream or video URL, plus a thumbnail."""
    work_dir = out_dir or Path(tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    out_clip = work_dir / f"clip_{timestamp}_{duration_secs}s.mp4"
    out_thumb = work_dir / f"thumb_{timestamp}.jpg"

    logger.info("Resolving stream inputs for: %s", stream_url)
    urls = resolve_stream_urls(stream_url)

    logger.info("Extracting %ds clip with FFmpeg to %s...", duration_secs, out_clip)
    t0 = time.time()

    # Build FFmpeg command with fast re-encoding for high web compatibility
    if len(urls) >= 2:
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", urls[0],
            "-i", urls[1],
            "-t", str(duration_secs),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_clip),
        ]
    else:
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", urls[0],
            "-t", str(duration_secs),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_clip),
        ]

    proc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("FFmpeg clip failed: %s", proc.stderr)
        raise RuntimeError(f"FFmpeg failed: {proc.stderr[:400]}")

    elapsed = time.time() - t0
    logger.info("FFmpeg clip generated in %.2fs (size: %d bytes)", elapsed, out_clip.stat().st_size)

    # Generate Thumbnail
    thumb_sec = max(1.0, min(duration_secs / 2.0, 5.0))
    thumb_cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{thumb_sec:.2f}",
        "-i", str(out_clip),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_thumb),
    ]
    subprocess.run(thumb_cmd, capture_output=True, check=False)
    if not out_thumb.exists():
        logger.warning("Thumbnail generation fallback to 0.5s")
        subprocess.run(["ffmpeg", "-y", "-ss", "0.5", "-i", str(out_clip), "-frames:v", "1", str(out_thumb)], capture_output=True, check=False)

    return out_clip, out_thumb, float(duration_secs)


# ---------------------------------------------------------------------------
# Moment & Clip Lifecycle Handler
# ---------------------------------------------------------------------------

def process_pending_moment(moment: dict[str, Any]) -> bool:
    """Process a single pending moment: render clip, upload to storage, update DB."""
    moment_id = moment["id"]
    streamer_id = moment["streamer_id"]
    duration = int(moment.get("clip_duration") or 30)

    logger.info("Processing moment %d for streamer %d (duration: %ds)...", moment_id, streamer_id, duration)

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

    try:
        # 3. Cut clip & generate thumbnail
        clip_path, thumb_path, actual_duration = cut_clip_from_url(stream_url, duration_secs=duration)

        # 4. Upload to Supabase Storage
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

        # 5. Update Moment in DB
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

        # 6. Ensure corresponding record in `clips` table exists and is marked 'rendered'
        existing_clips = _supabase_request(f"rest/v1/clips?moment_id=eq.{moment_id}&select=id")
        title = f"{streamer.get('name', 'Streamer')} Highlight ({int(actual_duration)}s)"

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
                    "description": f"Auto-captured highlight from {streamer.get('name', 'streamer')}",
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
        # Also update any rendering clip
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
    logger.info("Starting ClipDeck Supabase Clipping Daemon (poll_interval=%ds)...", poll_interval)
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
    parser.add_argument("--streamer-id", type=int, default=7, help="Streamer ID for direct clipping")

    args = parser.parse_args()

    if args.clip_url:
        logger.info("Executing direct clip for URL: %s (duration: %ds)", args.clip_url, args.duration)
        clip_p, thumb_p, dur = cut_clip_from_url(args.clip_url, duration_secs=args.duration)
        clip_url = upload_to_storage(clip_p, STORAGE_CLIPS_BUCKET, f"direct_clip_{int(time.time())}.mp4", "video/mp4")
        thumb_url = upload_to_storage(thumb_p, STORAGE_THUMBS_BUCKET, f"direct_thumb_{int(time.time())}.jpg", "image/jpeg") if thumb_p.exists() else None
        print(json.dumps({
            "status": "success",
            "duration": dur,
            "clip_url": clip_url,
            "thumbnail_url": thumb_url,
        }, indent=2))
    elif args.once:
        processed_count = run_poll_cycle()
        print(f"Processed {processed_count} moments.")
    elif args.poll:
        main_daemon_loop(poll_interval=args.interval)
    else:
        # Default: process once
        run_poll_cycle()

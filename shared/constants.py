"""Shared constants for the ClipDeck worker system."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_MEDIA_PATH = Path("/data/clipdeck/media")
RING_BUFFER_DIR = "ring_buffers"
CLIPS_DIR = "clips"
THUMBNAILS_DIR = "thumbnails"

# ---------------------------------------------------------------------------
# Ring buffer defaults
# ---------------------------------------------------------------------------
SEGMENT_DURATION_SECS: int = 2
MAX_RING_BUFFER_AGE_SECS: int = 15 * 60  # 15 minutes
RING_BUFFER_CLEANUP_INTERVAL_SECS: int = 10
TOTAL_DISK_CAP_BYTES: int = 50 * 1024 * 1024 * 1024  # 50 GB

# ---------------------------------------------------------------------------
# Hype detector defaults
# ---------------------------------------------------------------------------
EWMA_ALPHA: float = 0.3
BASELINE_WINDOW_SECS: int = 600       # 10 min sliding window
BASELINE_MIN_SECS: int = 300          # need at least 5 min for stable baseline
HYPE_THRESHOLD: float = 65.0
COOLDOWN_SECS: float = 60.0
MERGE_WINDOW_SECS: float = 15.0
CLIP_PRE_SECS: float = 35.0
CLIP_POST_SECS: float = 10.0
PEAK_DECLINE_SECS: int = 3
MAD_EPSILON: float = 0.01
MAD_TO_STD: float = 1.4826

# ---------------------------------------------------------------------------
# Signal weights (defaults)
# ---------------------------------------------------------------------------
DEFAULT_SIGNAL_WEIGHTS: dict[str, float] = {
    "chat_velocity_zscore": 0.35,
    "emote_density": 0.25,
    "copypasta_ratio": 0.15,
    "sub_gift_burst": 0.15,
    "caps_ratio": 0.10,
}

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
AUDIO_SEGMENT_SECS: float = 2.0
AUDIO_MAX_BONUS: float = 20.0

# ---------------------------------------------------------------------------
# Live poller
# ---------------------------------------------------------------------------
LIVE_POLL_INTERVAL_SECS: int = 60

# ---------------------------------------------------------------------------
# Platform chat
# ---------------------------------------------------------------------------
TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6697  # TLS
TWITCH_IRC_PORT_PLAIN = 6667
TWITCH_HELIX_BASE = "https://api.twitch.tv/helix"

KICK_PUSHER_HOST = "ws-us2.pusher.com"
KICK_PUSHER_KEY = "eb1d5f283081a78b932c"  # public key
KICK_API_BASE = "https://kick.com/api/v2"

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_CHAT_POLL_SECS: int = 5

# ---------------------------------------------------------------------------
# Redis / ARQ
# ---------------------------------------------------------------------------
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

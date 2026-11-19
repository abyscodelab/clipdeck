"""Signal definitions and detector configuration for the hype engine.

This module defines the emote/token sets that signal hype in chat, plus the
``DetectorConfig`` dataclass that bundles every tuneable knob.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

from clipdeck.shared import constants


# ---------------------------------------------------------------------------
# Hype tokens — emotes & unicode that indicate excitement
# ---------------------------------------------------------------------------

HYPE_EMOTES: set[str] = {
    # -- BTTV / 7TV / FFZ popular emotes --
    "KEKW", "LUL", "LULW", "OMEGALUL",
    "POGGERS", "PogChamp", "Pog", "PogU", "POGGIES",
    "W", "WWWWW", "Ws",
    "L", "LLLL",
    "monkaS", "monkaW", "MONKA",
    "Sadge", "Sadeg",
    "LETSGO", "LETSGOO", "LETS GO",
    "EZ", "Clap", "EZClap",
    "Jebaited", "COPIUM", "HOPIUM",
    "catJAM", "pepeJAM", "pepeDS",
    "HYPERS", "PagMan", "PagChomp",
    "Chatting", "BASED",
    # -- clip-related --
    "CLIP", "CLIP IT", "CLIPPED", "clip it",
    # -- question flood --
    "???", "?????", "????",
}

HYPE_UNICODE: set[str] = {
    "💀", "😂", "🤣", "😭", "🔥",
    "⁉️", "❗", "‼️",
    "🏆", "👑", "🎉", "😱",
    "💯", "⚡",
}

# Pre-compiled pattern for efficient matching
_HYPE_EMOTE_PATTERN: re.Pattern[str] = re.compile(
    r"\b(" + "|".join(re.escape(e) for e in sorted(HYPE_EMOTES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_HYPE_UNICODE_SET: frozenset[str] = frozenset(HYPE_UNICODE)


def contains_hype_token(text: str) -> bool:
    """Return True if *text* contains at least one hype emote or unicode."""
    if _HYPE_EMOTE_PATTERN.search(text):
        return True
    return any(ch in _HYPE_UNICODE_SET for ch in text)


def count_hype_tokens(text: str) -> int:
    """Return the number of hype tokens found in *text*."""
    count = len(_HYPE_EMOTE_PATTERN.findall(text))
    count += sum(1 for ch in text if ch in _HYPE_UNICODE_SET)
    return count


# ---------------------------------------------------------------------------
# Detector configuration
# ---------------------------------------------------------------------------

@dataclass
class DetectorConfig:
    """All tuneable parameters for the ``HypeDetector``.

    Every field has a sane default.  Streamers can override via their
    per-streamer config JSON stored in the DB.
    """

    # -- EWMA / baseline --------------------------------------------------
    ewma_alpha: float = constants.EWMA_ALPHA
    baseline_window_secs: int = constants.BASELINE_WINDOW_SECS
    baseline_min_secs: int = constants.BASELINE_MIN_SECS
    mad_epsilon: float = constants.MAD_EPSILON
    mad_to_std: float = constants.MAD_TO_STD

    # -- Signal weights (must sum to ~1.0) ---------------------------------
    signal_weights: dict[str, float] = field(
        default_factory=lambda: dict(constants.DEFAULT_SIGNAL_WEIGHTS),
    )

    # -- Thresholds --------------------------------------------------------
    hype_threshold: float = constants.HYPE_THRESHOLD
    cooldown_secs: float = constants.COOLDOWN_SECS
    merge_window_secs: float = constants.MERGE_WINDOW_SECS

    # -- Clip window -------------------------------------------------------
    clip_pre_secs: float = constants.CLIP_PRE_SECS
    clip_post_secs: float = constants.CLIP_POST_SECS
    peak_decline_secs: int = constants.PEAK_DECLINE_SECS

    # -- Audio bonus -------------------------------------------------------
    audio_max_bonus: float = constants.AUDIO_MAX_BONUS

    # -- Caps detection ----------------------------------------------------
    caps_min_length: int = 4       # ignore very short messages for caps ratio
    caps_threshold: float = 0.60   # fraction of chars that are uppercase

    # -- Copypasta detection -----------------------------------------------
    copypasta_window_secs: float = 10.0
    copypasta_min_length: int = 8  # ignore short duplicates

    # -- Sub/gift burst detection ------------------------------------------
    gift_burst_window_secs: float = 10.0

    # -- Custom emote overrides (streamer-specific) ------------------------
    extra_hype_emotes: set[str] = field(default_factory=set)
    ignored_emotes: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Output data structures
# ---------------------------------------------------------------------------

class MomentTrigger(NamedTuple):
    """Describes a detected hype moment to be clipped."""

    start_time: float
    end_time: float
    peak_score: float
    peak_time: float
    top_messages: list[dict]  # [{username, text, timestamp}, ...]
    signals_at_peak: dict[str, float]


@dataclass(slots=True)
class HypeScore:
    """Current hype score snapshot returned by the detector."""

    score: float
    signals: dict[str, float]
    triggered_moment: MomentTrigger | None = None


@dataclass(slots=True)
class ChatStatsBucket:
    """Data to persist to the ``chat_stats_bucket`` DB table."""

    timestamp: float
    messages_per_second: float
    hype_score: float
    top_emotes: dict[str, int]
    signals: dict[str, float]
    caps_ratio: float
    copypasta_ratio: float

"""HypeDetector — the core hype detection engine for ClipDeck.

One instance per monitored stream.  The worker calls ``feed_messages()``
every second with new chat messages and optionally ``feed_audio()`` with
loudness data.  ``get_current_score()`` returns the latest score and any
triggered clip moments.

Algorithm overview
------------------
1. Sliding window of per-second message counts (last 600 s).
2. EWMA of messages-per-second (alpha = 0.3).
3. Rolling baseline (median of last 300-600 s).
4. Rolling MAD → robust standard deviation.
5. Z-score = (ewma − baseline) / (1.4826 × MAD + ε).
6. Five weighted chat signals + optional audio bonus → 0-100 score.
7. Trigger on threshold crossing → wait for peak → emit ``MomentTrigger``.
"""

from __future__ import annotations

import collections
import logging
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field

from clipdeck.shared.detection.signals import (
    ChatStatsBucket,
    DetectorConfig,
    HypeScore,
    MomentTrigger,
    contains_hype_token,
    count_hype_tokens,
)
from clipdeck.shared.platforms.base import ChatMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _median(values: list[float]) -> float:
    """Return the median of *values*, or 0.0 if empty."""
    if not values:
        return 0.0
    return statistics.median(values)


def _mad(values: list[float], median_val: float) -> float:
    """Median Absolute Deviation."""
    if not values:
        return 0.0
    return statistics.median([abs(v - median_val) for v in values])


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# HypeDetector
# ---------------------------------------------------------------------------

class HypeDetector:
    """Stateful per-stream hype detector.

    Parameters
    ----------
    streamer_id:
        Database ID of the streamer being monitored.
    config:
        ``DetectorConfig`` with all tuneable parameters.
    """

    def __init__(self, streamer_id: int, config: DetectorConfig | None = None) -> None:
        self.streamer_id = streamer_id
        self.cfg = config or DetectorConfig()

        # -- Per-second message counts (ring buffer of last N seconds) -----
        self._window_size: int = self.cfg.baseline_window_secs  # 600 s
        self._msg_counts: collections.deque[float] = collections.deque(
            maxlen=self._window_size,
        )
        self._tick: int = 0  # how many seconds we've processed

        # -- EWMA state ----------------------------------------------------
        self._ewma: float = 0.0

        # -- Signal accumulators -------------------------------------------
        # Recent messages for copypasta detection (timestamp, text_hash)
        self._recent_texts: collections.deque[tuple[float, str]] = collections.deque(
            maxlen=2000,
        )
        # Sub/gift events within burst window
        self._gift_events: collections.deque[tuple[float, int]] = collections.deque(
            maxlen=500,
        )
        # Emote counter for stats
        self._emote_counter: Counter[str] = Counter()

        # -- Audio state ---------------------------------------------------
        self._audio_rms_history: collections.deque[float] = collections.deque(
            maxlen=self._window_size,
        )
        self._last_audio_rms: float = 0.0
        self._audio_bonus: float = 0.0

        # -- Trigger state machine -----------------------------------------
        self._last_trigger_time: float = 0.0
        self._in_potential_moment: bool = False
        self._peak_score: float = 0.0
        self._peak_time: float = 0.0
        self._peak_signals: dict[str, float] = {}
        self._decline_ticks: int = 0
        self._moment_messages: list[dict] = []

        # -- Latest score --------------------------------------------------
        self._current_score: float = 0.0
        self._current_signals: dict[str, float] = {}
        self._pending_moment: MomentTrigger | None = None

        # -- Last stats bucket (for DB persistence) ------------------------
        self._last_stats: ChatStatsBucket | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed_messages(self, messages: list[ChatMessage], timestamp: float) -> None:
        """Feed new chat messages for the current second.

        Called once per second by the detection loop.
        """
        self._tick += 1
        now = timestamp
        msg_count = len(messages)
        self._msg_counts.append(float(msg_count))

        # -- Update EWMA --------------------------------------------------
        alpha = self.cfg.ewma_alpha
        self._ewma = alpha * msg_count + (1 - alpha) * self._ewma

        # -- Accumulate per-message signals --------------------------------
        hype_msg_count = 0
        caps_msg_count = 0
        copypasta_count = 0
        total_eligible = 0
        emote_counts: Counter[str] = Counter()

        # Expire old copypasta window entries
        copypasta_cutoff = now - self.cfg.copypasta_window_secs
        while self._recent_texts and self._recent_texts[0][0] < copypasta_cutoff:
            self._recent_texts.popleft()

        # Build set of recent text for quick copypasta lookup
        recent_text_set = {t for _, t in self._recent_texts}

        for msg in messages:
            text = msg.text.strip()
            if not text:
                continue
            total_eligible += 1

            # Hype emote detection
            if contains_hype_token(text):
                hype_msg_count += 1
                n_tokens = count_hype_tokens(text)
                emote_counts["_hype_total"] += n_tokens

            # Caps detection
            if len(text) >= self.cfg.caps_min_length:
                alpha_chars = [c for c in text if c.isalpha()]
                if alpha_chars:
                    upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                    if upper_ratio >= self.cfg.caps_threshold:
                        caps_msg_count += 1

            # Copypasta detection
            normalized = text.lower().strip()
            if len(normalized) >= self.cfg.copypasta_min_length:
                if normalized in recent_text_set:
                    copypasta_count += 1
                self._recent_texts.append((now, normalized))

            # Sub/gift accumulation
            if msg.sub_gift_count > 0:
                self._gift_events.append((now, msg.sub_gift_count))
            if msg.bits > 0:
                self._gift_events.append((now, max(1, msg.bits // 100)))

        self._emote_counter += emote_counts

        # -- Compute signals -----------------------------------------------
        safe_total = max(total_eligible, 1)

        emote_density = hype_msg_count / safe_total
        caps_ratio = caps_msg_count / safe_total
        copypasta_ratio = copypasta_count / safe_total

        # Sub/gift burst: total gifts in last N seconds
        gift_cutoff = now - self.cfg.gift_burst_window_secs
        while self._gift_events and self._gift_events[0][0] < gift_cutoff:
            self._gift_events.popleft()
        total_gifts = sum(count for _, count in self._gift_events)
        # Normalize gift burst to 0-1 (10+ gifts in window = 1.0)
        sub_gift_burst = _clamp(total_gifts / 10.0, 0.0, 1.0)

        # Chat velocity z-score
        velocity_zscore = self._compute_velocity_zscore()
        # Normalize z-score to 0-1 range (z=0 → 0, z=5+ → 1)
        velocity_signal = _clamp(velocity_zscore / 5.0, 0.0, 1.0)

        # -- Weighted combination ------------------------------------------
        weights = self.cfg.signal_weights
        raw_score = (
            weights.get("chat_velocity_zscore", 0.35) * velocity_signal
            + weights.get("emote_density", 0.25) * emote_density
            + weights.get("copypasta_ratio", 0.15) * copypasta_ratio
            + weights.get("sub_gift_burst", 0.15) * sub_gift_burst
            + weights.get("caps_ratio", 0.10) * caps_ratio
        )

        # Scale to 0-100 and add audio bonus
        score = _clamp(raw_score * 100.0 + self._audio_bonus)

        self._current_score = score
        self._current_signals = {
            "chat_velocity_zscore": round(velocity_zscore, 3),
            "velocity_signal": round(velocity_signal, 3),
            "emote_density": round(emote_density, 3),
            "caps_ratio": round(caps_ratio, 3),
            "copypasta_ratio": round(copypasta_ratio, 3),
            "sub_gift_burst": round(sub_gift_burst, 3),
            "audio_bonus": round(self._audio_bonus, 3),
            "messages_per_second": round(self._ewma, 2),
        }

        # -- Collect top messages for moment snapshot ----------------------
        if score > self.cfg.hype_threshold * 0.7:
            # Keep interesting messages around peak
            for msg in messages:
                if contains_hype_token(msg.text) or len(msg.text) > 5:
                    self._moment_messages.append({
                        "username": msg.username,
                        "text": msg.text,
                        "timestamp": msg.timestamp,
                    })
            # Cap stored messages
            if len(self._moment_messages) > 200:
                self._moment_messages = self._moment_messages[-100:]

        # -- Trigger state machine -----------------------------------------
        self._pending_moment = None
        self._update_trigger_state(score, now)

        # -- Build stats bucket for DB -------------------------------------
        top_emotes = dict(self._emote_counter.most_common(10))
        self._last_stats = ChatStatsBucket(
            timestamp=now,
            messages_per_second=round(self._ewma, 2),
            hype_score=round(score, 1),
            top_emotes=top_emotes,
            signals=dict(self._current_signals),
            caps_ratio=round(caps_ratio, 3),
            copypasta_ratio=round(copypasta_ratio, 3),
        )

    def feed_audio(self, rms: float, timestamp: float) -> None:
        """Feed audio loudness measurement from a segment.

        Parameters
        ----------
        rms:
            RMS loudness in dB (negative values; closer to 0 = louder).
        timestamp:
            Segment timestamp.
        """
        self._audio_rms_history.append(rms)
        self._last_audio_rms = rms

        if len(self._audio_rms_history) < 10:
            self._audio_bonus = 0.0
            return

        # Compute baseline audio level
        rms_values = list(self._audio_rms_history)
        audio_median = _median(rms_values)
        audio_mad = _mad(rms_values, audio_median)
        robust_std = self.cfg.mad_to_std * audio_mad + self.cfg.mad_epsilon

        # Audio z-score (note: louder = less negative, so spike = rms > median)
        audio_z = (rms - audio_median) / robust_std

        # Map z-score > 2 to bonus points (0-20)
        if audio_z > 2.0:
            self._audio_bonus = _clamp(
                (audio_z - 2.0) * (self.cfg.audio_max_bonus / 3.0),
                0.0,
                self.cfg.audio_max_bonus,
            )
        else:
            # Decay audio bonus
            self._audio_bonus = max(0.0, self._audio_bonus * 0.8)

    def get_current_score(self) -> HypeScore:
        """Return the current hype score and any triggered moment."""
        return HypeScore(
            score=round(self._current_score, 1),
            signals=dict(self._current_signals),
            triggered_moment=self._pending_moment,
        )

    def get_stats_bucket(self) -> ChatStatsBucket | None:
        """Return the latest stats bucket for DB persistence."""
        return self._last_stats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_velocity_zscore(self) -> float:
        """Compute z-score of current EWMA against rolling baseline."""
        counts = list(self._msg_counts)
        n = len(counts)
        if n < self.cfg.baseline_min_secs:
            # Not enough data for a stable baseline
            return 0.0

        # Use last baseline_window_secs (or whatever we have)
        window = counts[-self.cfg.baseline_window_secs:]
        baseline_median = _median(window)
        baseline_mad = _mad(window, baseline_median)
        robust_std = self.cfg.mad_to_std * baseline_mad + self.cfg.mad_epsilon

        z = (self._ewma - baseline_median) / robust_std
        return max(z, 0.0)  # Only positive spikes matter

    def _update_trigger_state(self, score: float, now: float) -> None:
        """State machine for peak detection and moment triggering.

        States:
        1. IDLE — waiting for score to cross threshold
        2. POTENTIAL — score above threshold, tracking peak
        3. TRIGGERED — peak confirmed, emit moment
        """
        threshold = self.cfg.hype_threshold
        cooldown = self.cfg.cooldown_secs

        # Check cooldown
        if now - self._last_trigger_time < cooldown:
            return

        if not self._in_potential_moment:
            # -- IDLE: check if we should start tracking -------------------
            if score >= threshold:
                self._in_potential_moment = True
                self._peak_score = score
                self._peak_time = now
                self._peak_signals = dict(self._current_signals)
                self._decline_ticks = 0
                logger.info(
                    "Streamer %d: potential moment started (score=%.1f)",
                    self.streamer_id, score,
                )
        else:
            # -- POTENTIAL: track peak -------------------------------------
            if score >= self._peak_score:
                # Still rising or at same level
                self._peak_score = score
                self._peak_time = now
                self._peak_signals = dict(self._current_signals)
                self._decline_ticks = 0
            else:
                self._decline_ticks += 1

            if self._decline_ticks >= self.cfg.peak_decline_secs:
                # Peak confirmed!  Emit moment.
                start_time = self._peak_time - self.cfg.clip_pre_secs
                end_time = self._peak_time + self.cfg.clip_post_secs

                # Check merge: if this moment starts within merge_window of
                # the last trigger's end time, we'd need the caller to merge.
                # We signal that by emitting anyway; the caller handles merge.

                # Pick top messages around peak
                peak_window_start = self._peak_time - 15.0
                peak_window_end = self._peak_time + 5.0
                top_msgs = [
                    m for m in self._moment_messages
                    if peak_window_start <= m["timestamp"] <= peak_window_end
                ]
                # Sort by proximity to peak, take top 20
                top_msgs.sort(key=lambda m: abs(m["timestamp"] - self._peak_time))
                top_msgs = top_msgs[:20]

                self._pending_moment = MomentTrigger(
                    start_time=start_time,
                    end_time=end_time,
                    peak_score=self._peak_score,
                    peak_time=self._peak_time,
                    top_messages=top_msgs,
                    signals_at_peak=self._peak_signals,
                )

                logger.info(
                    "Streamer %d: MOMENT TRIGGERED (peak=%.1f at %.1f, window=%.1f-%.1f)",
                    self.streamer_id,
                    self._peak_score,
                    self._peak_time,
                    start_time,
                    end_time,
                )

                self._last_trigger_time = now
                self._in_potential_moment = False
                self._peak_score = 0.0
                self._decline_ticks = 0
                self._moment_messages.clear()

            # Abandon if score drops below threshold and we haven't peaked
            elif score < threshold * 0.5 and self._decline_ticks > 0:
                logger.debug(
                    "Streamer %d: moment abandoned (score dropped to %.1f)",
                    self.streamer_id, score,
                )
                self._in_potential_moment = False
                self._decline_ticks = 0

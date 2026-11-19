"""Audio analysis module for detecting stream audio loudness and spikes.

Uses FFmpeg's `volumedetect` audio filter to extract mean volume (RMS proxy)
and peak volume (max_volume) from recorded media segments (.ts files).
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches FFmpeg volumedetect filter output lines:
# [Parsed_volumedetect_0 @ ...] mean_volume: -24.3 dB
# [Parsed_volumedetect_0 @ ...] max_volume: -3.1 dB
_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?[\d.]+)\s*dB")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?[\d.]+)\s*dB")


@dataclass(slots=True)
class AudioMetrics:
    """Metrics extracted from analyzing a segment's audio track."""

    rms_db: float  # Mean volume in dB (e.g. -24.0, negative)
    peak_db: float  # Max volume in dB (e.g. -2.0, negative)
    is_spike: bool = False
    duration: float = 0.0


class AudioAnalyzer:
    """Analyzes audio loudness from media segments."""

    def __init__(self, spike_threshold_db: float = -12.0) -> None:
        """
        Parameters
        ----------
        spike_threshold_db:
            If peak_db exceeds this value (e.g. louder than -12 dB),
            it is marked as a potential audio spike.
        """
        self.spike_threshold_db = spike_threshold_db

    async def analyze_segment_async(self, segment_path: Path) -> AudioMetrics:
        """Run FFmpeg volumedetect asynchronously on segment_path."""
        if not segment_path.exists():
            logger.warning("Segment file does not exist: %s", segment_path)
            return AudioMetrics(rms_db=-99.0, peak_db=-99.0, is_spike=False)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(segment_path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            output = stderr.decode("utf-8", errors="replace")
            return self._parse_output(output)
        except Exception as e:
            logger.error("Error running volumedetect on %s: %s", segment_path, e)
            return AudioMetrics(rms_db=-99.0, peak_db=-99.0, is_spike=False)

    def analyze_segment(self, segment_path: Path) -> AudioMetrics:
        """Synchronous version of analyze_segment."""
        if not segment_path.exists():
            logger.warning("Segment file does not exist: %s", segment_path)
            return AudioMetrics(rms_db=-99.0, peak_db=-99.0, is_spike=False)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(segment_path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return self._parse_output(res.stderr)
        except Exception as e:
            logger.error("Error running volumedetect synchronously on %s: %s", segment_path, e)
            return AudioMetrics(rms_db=-99.0, peak_db=-99.0, is_spike=False)

    def _parse_output(self, output: str) -> AudioMetrics:
        mean_match = _MEAN_VOLUME_RE.search(output)
        max_match = _MAX_VOLUME_RE.search(output)

        rms_db = float(mean_match.group(1)) if mean_match else -99.0
        peak_db = float(max_match.group(1)) if max_match else -99.0
        is_spike = peak_db > self.spike_threshold_db

        return AudioMetrics(
            rms_db=rms_db,
            peak_db=peak_db,
            is_spike=is_spike,
        )

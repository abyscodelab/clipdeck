"""EDL Generator: Produces strict, machine-executable Edit Decision Lists using LLMs."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from clipdeck.shared.ai.base import AIProvider
from clipdeck.shared.ai.edl_schema import EditDecisionList, MomentScoreResult
from clipdeck.shared.ai.playbook_engine import Playbook, PlaybookEngine
from clipdeck.shared.transcription.base import TranscriptResult

logger = logging.getLogger(__name__)


def _clean_json_markdown(text: str) -> str:
    """Strip markdown code fence ```json ... ``` wrapper if present."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


async def generate_edl(
    ai_provider: AIProvider,
    score_result: MomentScoreResult,
    transcript: TranscriptResult,
    chat_messages: list[dict],
    streamer_name: str,
    playbooks: list[Playbook] | None = None,
    layout_type: str = "blurred_bg",
    max_retries: int = 2,
) -> EditDecisionList:
    """Generate a complete EditDecisionList with validation and auto-retry on schema errors."""
    system_prompt, _ = PlaybookEngine.merge_playbooks(playbooks or [])

    # Identify potential silence / dead-air pauses from word timestamps
    detected_pauses = []
    if transcript.words:
        for i in range(len(transcript.words) - 1):
            curr_w = transcript.words[i]
            next_w = transcript.words[i + 1]
            pause_len = next_w.start - curr_w.end
            if pause_len > 0.7:  # Playbook rule: cut dead air > 0.7s
                detected_pauses.append(
                    {"start": round(curr_w.end, 2), "end": round(next_w.start, 2), "duration": round(pause_len, 2)}
                )

    user_prompt = f"""
Generate an Edit Decision List (EDL) for a 9:16 vertical short (TikTok/Reels/Shorts).

STREAMER: @{streamer_name}
VIRALITY CATEGORY: {score_result.category}
SUGGESTED IN/OUT: {score_result.best_in:.1f}s to {score_result.best_out:.1f}s
DETECTED DEAD-AIR GAPS (>0.7s): {json.dumps(detected_pauses[:10])}
DESIRED LAYOUT: {layout_type}

TRANSCRIPT WITH TIMESTAMPS:
\"\"\"{transcript.text}\"\"\"

EDITING RULES:
1. Target final clip length: 15 to 60 seconds.
2. Hook in first 2 seconds! Provide a catchy `hook_text` (all caps, punchy).
3. Cut dead air over 0.7 seconds using `cuts`.
4. Include 1-2 zoom punches on climax moments using `zoom_punches`.
5. Write compelling, high-CTR `title`, `description` (credit @{streamer_name}), and 5-8 `hashtags`.
6. Provide platform-specific titles and descriptions in `per_platform` (keys: 'tiktok', 'youtube_shorts', 'instagram_reels').

Respond ONLY with a valid JSON object matching the EditDecisionList schema:
{{
  "trim": {{ "in_point": float, "out_point": float }},
  "cuts": [ {{ "start": float, "end": float, "reason": "string" }} ],
  "layout": {{ "type": "{layout_type}" }},
  "hook_text": "string or null",
  "hook_duration": 2.5,
  "captions": {{
    "font": "Montserrat ExtraBold",
    "font_size": 48,
    "primary_color": "&H00FFFFFF",
    "highlight_color": "&H0000FFFF",
    "outline_color": "&H00000000",
    "position": "bottom"
  }},
  "zoom_punches": [ {{ "timestamp": float, "scale": 1.15, "duration": 1.0 }} ],
  "title": "string",
  "description": "string",
  "hashtags": ["#tag1", "#tag2", ...],
  "per_platform": {{
    "tiktok": {{ "title": "string", "description": "string", "hashtags": ["string"] }},
    "youtube_shorts": {{ "title": "string", "description": "string", "hashtags": ["string"] }},
    "instagram_reels": {{ "title": "string", "description": "string", "hashtags": ["string"] }}
  }}
}}
"""

    current_prompt = user_prompt
    for attempt in range(max_retries + 1):
        completion = await ai_provider.complete(
            prompt=current_prompt,
            system_prompt=system_prompt,
            json_mode=True,
            temperature=0.2,
        )
        cleaned_json = _clean_json_markdown(completion.content)

        try:
            data = json.loads(cleaned_json)
            # Ensure layout type matches
            if "layout" not in data or not isinstance(data["layout"], dict):
                data["layout"] = {"type": layout_type}
            else:
                data["layout"]["type"] = layout_type

            edl = EditDecisionList(**data)
            logger.info("Successfully validated EDL (attempt %d)", attempt + 1)
            return edl

        except Exception as err:
            logger.warning("EDL validation failed on attempt %d: %s", attempt + 1, err)
            if attempt < max_retries:
                current_prompt = (
                    f"{user_prompt}\n\n"
                    f"PREVIOUS ATTEMPT FAILED WITH VALIDATION ERROR:\n{err}\n"
                    f"Please fix the error and output strictly valid JSON conforming to the schema."
                )
            else:
                # Fallback deterministic EDL
                logger.error("Max retries exceeded for EDL generation. Generating fallback EDL.")
                return _create_fallback_edl(score_result, streamer_name, layout_type)


def _create_fallback_edl(
    score_result: MomentScoreResult,
    streamer_name: str,
    layout_type: str,
) -> EditDecisionList:
    """Create a safe, deterministic EDL if LLM JSON generation fails."""
    in_pt = max(0.0, score_result.best_in)
    out_pt = max(in_pt + 15.0, score_result.best_out)

    return EditDecisionList(
        trim={"in_point": in_pt, "out_point": out_pt},
        cuts=[],
        layout={"type": layout_type},
        hook_text="WAIT FOR IT...",
        hook_duration=2.5,
        zoom_punches=[],
        title=f"INSANE Moment with @{streamer_name}!",
        description=f"Can't believe this happened live! 🎥 @{streamer_name}",
        hashtags=["#streamer", "#twitch", "#gaming", "#fyp", "#viral"],
        per_platform={
            "tiktok": {
                "title": f"INSANE Moment with @{streamer_name}!",
                "description": f"🎥 @{streamer_name} #streamer #fyp",
                "hashtags": ["#streamer", "#fyp"],
            }
        },
    )

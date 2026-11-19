"""Moment Scoring Engine: Evaluates moments for virality and rule compliance."""

from __future__ import annotations

import json
import logging
from typing import Any

from clipdeck.shared.ai.base import AIProvider
from clipdeck.shared.ai.edl_schema import MomentScoreResult
from clipdeck.shared.ai.playbook_engine import Playbook, PlaybookEngine
from clipdeck.shared.transcription.base import TranscriptResult

logger = logging.getLogger(__name__)


async def score_moment(
    ai_provider: AIProvider,
    transcript: TranscriptResult,
    chat_messages: list[dict],
    hype_metrics: dict[str, Any],
    streamer_name: str,
    playbooks: list[Playbook] | None = None,
) -> MomentScoreResult:
    """Evaluate a moment using transcript, chat reaction, and merged playbooks."""
    system_prompt, hard_rules = PlaybookEngine.merge_playbooks(playbooks or [])

    # Format chat messages summary
    chat_summary = "\n".join(
        f"[{m.get('username', 'user')}]: {m.get('text', '')}"
        for m in chat_messages[:25]
    )

    # Format transcript summary
    transcript_summary = transcript.text or "(No spoken dialogue detected)"

    # Programmatic pre-check for hard rule violations
    programmatic_violations = PlaybookEngine.check_rule_violations(
        transcript_text=transcript_summary,
        chat_text=" ".join(m.get("text", "") for m in chat_messages),
        hard_rules=hard_rules,
    )

    user_prompt = f"""
Evaluate the following stream moment for virality, storytelling hook, and brand safety.

STREAMER: @{streamer_name}
HYPE METRICS:
- Peak Score: {hype_metrics.get('peak_score', 'N/A')}
- Chat Velocity Z-Score: {hype_metrics.get('chat_velocity_zscore', 'N/A')}
- Emote Density: {hype_metrics.get('emote_density', 'N/A')}

TRANSCRIPT:
\"\"\"{transcript_summary}\"\"\"

TOP AUDIENCE CHAT MESSAGES:
\"\"\"{chat_summary}\"\"\"

Task:
1. Determine if this moment should be kept (keep: boolean). Reject if boring, dead air, or violates hard rules.
2. Rate virality potential 0 to 100.
3. Categorize into one of: clutch, funny, rage, wholesome, hot_take, chat_wild, reaction.
4. Identify optimal in-point (best_in) and out-point (best_out) in seconds (target 15-60s duration).
5. State applied rules and any violations.

Respond ONLY with a JSON object matching this schema:
{{
  "keep": boolean,
  "virality_score": float (0-100),
  "reason": "string",
  "category": "string",
  "best_in": float,
  "best_out": float,
  "playbook_rules_applied": ["string"],
  "rule_violations": ["string"]
}}
"""

    try:
        completion = await ai_provider.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=True,
            temperature=0.2,
        )
        data = json.loads(completion.content)
        result = MomentScoreResult(**data)

        # Merge programmatic violations
        if programmatic_violations:
            result.rule_violations.extend(programmatic_violations)
            result.keep = False
            result.virality_score = min(result.virality_score, 10.0)

        return result

    except Exception as e:
        logger.error("Scoring LLM failed: %s. Using heuristic fallback.", e)
        # Safe fallback based on hype score
        peak = float(hype_metrics.get("peak_score", 65.0))
        keep = peak >= 65.0 and not programmatic_violations
        return MomentScoreResult(
            keep=keep,
            virality_score=round(peak, 1),
            reason=f"Heuristic fallback scoring based on peak hype {peak}",
            category="chat_wild" if peak >= 70.0 else "funny",
            best_in=0.0,
            best_out=min(30.0, transcript.duration or 30.0),
            playbook_rules_applied=["heuristic_score"],
            rule_violations=programmatic_violations,
        )

"""Playbook Engine: Compiles, merges, and validates multi-tiered editing playbooks.

Playbook hierarchy:
1. Global (brand safety, default pacing, hard bans)
2. Category (gaming vs just-chatting vs esports)
3. Streamer (creator preferences, catchphrases, camera positions)
4. Target (TikTok vs YouTube Shorts vs Instagram Reels)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

HARD_BAN_KEYWORDS = [
    "stake.com", "gambling", "roobet", "crypto casino",
    "doxx", "leak", "address", "phone number",
    "loading screen", "brb", "afk", "technical difficulties",
]


@dataclass
class Playbook:
    """A playbook layer with instructions, hard rules, and metadata."""

    id: str
    name: str
    level: str  # global, category, streamer, target
    content_markdown: str
    hard_rules: list[str] = field(default_factory=list)
    guidelines: list[str] = field(default_factory=list)


class PlaybookEngine:
    """Merges playbook layers and verifies editorial compliance."""

    @staticmethod
    def extract_rules(markdown: str) -> tuple[list[str], list[str]]:
        """Parse markdown into hard rules (under 'What NOT to Clip' / 'Hard Rules') and general guidelines."""
        hard_rules: list[str] = []
        guidelines: list[str] = []

        in_hard_rules = False
        for line in markdown.splitlines():
            line_str = line.strip()
            lower = line_str.lower()
            if "what not to clip" in lower or "hard rule" in lower or "never" in lower:
                in_hard_rules = True
                continue
            elif line_str.startswith("#") and in_hard_rules:
                in_hard_rules = False

            if line_str.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
                rule_text = re.sub(r"^[-*0-9.]+\s*", "", line_str)
                if in_hard_rules or "no " in lower or "never " in lower or "do not " in lower:
                    hard_rules.append(rule_text)
                else:
                    guidelines.append(rule_text)

        return hard_rules, guidelines

    @classmethod
    def merge_playbooks(cls, playbooks: list[Playbook]) -> tuple[str, list[str]]:
        """
        Merge playbooks in hierarchy order: Global -> Category -> Streamer -> Target.
        Returns:
            (merged_system_prompt, all_hard_rules)
        """
        # Order by precedence
        order_map = {"global": 0, "category": 1, "streamer": 2, "target": 3}
        sorted_playbooks = sorted(
            playbooks, key=lambda p: order_map.get(p.level.lower(), 99)
        )

        all_hard_rules: list[str] = []
        guidelines_by_level: dict[str, list[str]] = {}

        for p in sorted_playbooks:
            p_hard, p_guides = cls.extract_rules(p.content_markdown)
            all_hard_rules.extend(p.hard_rules or p_hard)
            guidelines_by_level[p.name] = p.guidelines or p_guides

        # Deduplicate hard rules while preserving order
        seen_rules = set()
        deduped_hard: list[str] = []
        for r in all_hard_rules:
            norm = r.lower().strip()
            if norm not in seen_rules:
                seen_rules.add(norm)
                deduped_hard.append(r)

        # Build delimited system prompt
        prompt_parts = [
            "You are ClipDeck's Lead Video Editor and Social Growth Strategist.",
            "Your job is to transform raw stream highlights into viral 9:16 short-form videos.",
            "",
            "CRITICAL: You MUST strictly enforce the following HARD RULES. If any hard rule is violated, the moment must be rejected.",
            "<hard_rules>",
        ]
        for r in deduped_hard:
            prompt_parts.append(f"- {r}")
        prompt_parts.append("</hard_rules>")
        prompt_parts.append("")

        for section_name, lines in guidelines_by_level.items():
            prompt_parts.append(f"### Playbook: {section_name}")
            for l in lines:
                prompt_parts.append(f"- {l}")
            prompt_parts.append("")

        return "\n".join(prompt_parts), deduped_hard

    @classmethod
    def check_rule_violations(
        cls,
        transcript_text: str,
        chat_text: str,
        hard_rules: list[str],
    ) -> list[str]:
        """Programmatic check for obvious hard-rule violations."""
        violations: list[str] = []
        combined = f"{transcript_text} {chat_text}".lower()

        for kw in HARD_BAN_KEYWORDS:
            if kw in combined:
                violations.append(f"Prohibited content keyword detected: '{kw}'")

        return violations

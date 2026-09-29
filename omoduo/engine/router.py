"""Task shape router and intent heuristics for omoduo."""

from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class RoutingDecision:
    primary_engine: str  # "claude" | "agy" | "both"
    consult_engine: Optional[str]  # "claude" | "agy" | None
    reason: str
    clean_prompt: str

class TaskRouter:
    """Heuristic router deciding whether Claude, Antigravity, or both handle a prompt."""

    # Keywords suggesting large context exploration, repo search, or Gemini strengths
    AGY_PATTERNS = [
        r"\b(find all|search codebase|grep|where (is|are)|how (does|do)|explain flow)\b",
        r"\b(summarize (the )?repo|codebase overview|architecture of|scan)\b",
        r"\b(documentation|docs|read (the )?specs?|audit whole repo)\b",
    ]

    # Keywords suggesting surgical coding, bug fixing, test fulfillment, or Claude strengths
    CLAUDE_PATTERNS = [
        r"\b(refactor|fix (this )?(bug|error|issue|traceback)|patch)\b",
        r"\b(write (a )?(unit )?test|implement function|fix typo|clean up)\b",
        r"\b(type ?check|typing|edge case|regex|parse(r)?)\b",
    ]

    # Keywords suggesting cooperative spec/review, TDD, or user asking both models to work together
    DUAL_PATTERNS = [
        r"\b(work together|pair up|team up|collaborate|cooperate|joint|dual)\b",
        r"\b(both of you|you both|together)\b",
        r"\b(plan and implement|write and review|red-?team|critique|cross-?check)\b",
    ]

    def route(self, prompt: str, last_engine: str | None = None) -> RoutingDecision:
        stripped = prompt.strip()

        # 1. Check explicit manual prefixes
        if stripped.startswith("@claude "):
            return RoutingDecision(
                primary_engine="claude",
                consult_engine=None,
                reason="Explicit @claude prefix",
                clean_prompt=stripped[8:].strip(),
            )
        if stripped.startswith("@agy ") or stripped.startswith("@gemini "):
            prefix_len = 5 if stripped.startswith("@agy ") else 8
            return RoutingDecision(
                primary_engine="agy",
                consult_engine=None,
                reason="Explicit @agy prefix",
                clean_prompt=stripped[prefix_len:].strip(),
            )
        if stripped.startswith("@both ") or stripped.startswith("@dual "):
            prefix_len = 6 if stripped.startswith("@both ") else 6
            return RoutingDecision(
                primary_engine="both",
                consult_engine=None,
                reason="Explicit @both prefix",
                clean_prompt=stripped[prefix_len:].strip(),
            )
        if stripped.startswith("@remote ") or stripped.startswith("@local "):
            prefix_len = 8 if stripped.startswith("@remote ") else 7
            return RoutingDecision(
                primary_engine="remote",
                consult_engine=None,
                reason="Explicit @remote prefix",
                clean_prompt=stripped[prefix_len:].strip(),
            )
        if stripped.startswith("@all ") or stripped.startswith("@compare "):
            prefix_len = 5 if stripped.startswith("@all ") else 9
            return RoutingDecision(
                primary_engine="all",
                consult_engine=None,
                reason="Explicit @all prefix (concurrent 3-way comparison)",
                clean_prompt=stripped[prefix_len:].strip(),
            )
        if stripped.startswith("@duo "):
            return RoutingDecision(
                primary_engine="duo",
                consult_engine=None,
                reason="Explicit @duo prefix (Antigravity + remote agent staged collaboration)",
                clean_prompt=stripped[5:].strip(),
            )

        lower = stripped.lower()

        # 2. Check for dual / cooperative requests
        for pat in self.DUAL_PATTERNS:
            if re.search(pat, lower):
                return RoutingDecision(
                    primary_engine="both",
                    consult_engine=None,
                    reason="Dual collaboration requested",
                    clean_prompt=stripped,
                )

        # 3. Check for Antigravity (Gemini) exploration/context patterns
        for pat in self.AGY_PATTERNS:
            if re.search(pat, lower):
                return RoutingDecision(
                    primary_engine="agy",
                    consult_engine=None,
                    reason="Matched codebase exploration / context search heuristic",
                    clean_prompt=stripped,
                )

        # 4. Check for Claude surgical code/refactoring patterns
        for pat in self.CLAUDE_PATTERNS:
            if re.search(pat, lower):
                return RoutingDecision(
                    primary_engine="claude",
                    consult_engine=None,
                    reason="Matched surgical refactoring / code repair heuristic",
                    clean_prompt=stripped,
                )

        # 5. Follow-up / context stickiness: if prompt is brief conversation, stick with last active engine
        if last_engine in ("claude", "agy", "both", "remote", "all", "duo") and len(stripped.split()) < 8:
            return RoutingDecision(
                primary_engine=last_engine,
                consult_engine=None,
                reason=f"Follow-up turn continuation with {last_engine}",
                clean_prompt=stripped,
            )

        # 6. Default fallback: Claude for general coding with Antigravity as advisor
        return RoutingDecision(
            primary_engine="claude",
            consult_engine=None,
            reason="General task - routed to Claude",
            clean_prompt=stripped,
        )

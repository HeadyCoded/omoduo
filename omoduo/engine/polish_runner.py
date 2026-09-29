"""LAN Ollama-backed 'rant to prompt' polish pass for omoduo.

Turns a rough, rambling brain-dump into a handful of clean candidate
prompts via the free/unlimited remote rig (no tokens spent against Claude
or Antigravity until the user picks one and it's actually submitted).
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

OLLAMA_URL = "http://192.168.1.82:11434/api/chat"
DEFAULT_MODEL = "qwen-noxin-14b"

SYSTEM_PROMPT = (
    "You turn a rough, rambling brain-dump into clean, cohesive prompts for a team "
    "of AI coding assistants (Claude Code, Google Antigravity, and a local remote "
    "agent). Given the user's rant, produce exactly {n} distinct, well-structured "
    "prompt options that each capture their intent and could be sent standalone.\n\n"
    'Respond with ONLY a JSON object of this exact shape, nothing else:\n'
    '{{"options": ["first prompt text", "second prompt text", "third prompt text"]}}\n\n'
    "The \"options\" array must contain exactly {n} plain strings. Do not add any "
    "other keys, do not nest objects, do not add commentary or markdown fences."
)


class PolishError(Exception):
    """Raised when the local model is unreachable or returns unusable output."""


@dataclass
class PolishRunner:
    """Sends a rant to a local Ollama model and returns candidate prompts."""

    model: str = DEFAULT_MODEL
    base_url: str = OLLAMA_URL
    n_options: int = 3
    timeout: float = 120.0

    async def polish(self, rant: str) -> list[str]:
        return await asyncio.to_thread(self._polish_sync, rant)

    def _polish_sync(self, rant: str) -> list[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(n=self.n_options)},
                {"role": "user", "content": rant},
            ],
            "stream": False,
            "format": "json",
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise PolishError(
                f"Could not reach the LAN Ollama rig at {self.base_url} ({e.reason}). "
                f"Is the Windows rig on and Ollama running there?"
            ) from e
        except TimeoutError as e:
            raise PolishError(
                f"Local model timed out after {self.timeout:.0f}s. Try a shorter rant "
                f"or a smaller model."
            ) from e

        if "error" in body:
            raise PolishError(f"Ollama error: {body['error']}")

        content = body.get("message", {}).get("content", "")
        return self._parse_options(content)

    def _parse_options(self, content: str) -> list[str]:
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = None

        if parsed is not None:
            options = self._extract_option_strings(parsed)
            if options:
                return options
            raise PolishError(
                "Local model returned JSON in an unexpected shape (no usable option strings)."
            )

        # Content wasn't valid JSON at all -- model ignored the format instruction.
        # Fall back to splitting numbered/bulleted plain-text lines.
        options = []
        for line in content.splitlines():
            cleaned = re.sub(r"^\s*(?:\d+[\.\)]|-|\*)\s*", "", line.strip()).strip()
            if cleaned:
                options.append(cleaned)

        if not options:
            raise PolishError("Local model returned no usable prompt options.")
        return options

    @staticmethod
    def _extract_option_strings(parsed) -> list[str]:
        """Pulls a flat list of option strings out of parsed JSON, whatever shape it arrived in.

        Prefers an explicit "options" key (the schema we ask for); falls back to the
        first list-valued key for models that use a different key name; rejects
        non-string entries rather than stringifying them (a small model under strict
        JSON grammar can emit nested {} garbage that stringifies into junk options).
        """
        if isinstance(parsed, list):
            candidates = parsed
        elif isinstance(parsed, dict):
            candidates = parsed.get("options")
            if not isinstance(candidates, list):
                candidates = next((v for v in parsed.values() if isinstance(v, list)), [])
        else:
            candidates = []

        return [item.strip() for item in candidates if isinstance(item, str) and item.strip()]

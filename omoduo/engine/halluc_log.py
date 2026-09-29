"""Lightweight structured log of flagged remote-agent hallucinations.

Written as JSONL (one JSON object per line) so it's easy to grep, parse, or
later feed into strengthening the remote agent's Modelfile/conventions --
the whole point of this app during the remote-agent training window.
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "omoduo" / "hallucination-log.jsonl"


def log_hallucination(prompt: str, response: str, note: str = "") -> Path:
    """Appends a flagged hallucination entry. Returns the log file path."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "response": response,
        "note": note,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return LOG_PATH

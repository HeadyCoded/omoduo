"""Async runner for the LAN-hosted remote agent (aider against the Windows rig).

Unlike ClaudeRunner/AgyRunner, aider has no structured stream-json protocol --
it's a plain-text CLI. Rather than reverse-engineer its text into fake
structured tool events, this streams its stdout close to verbatim: a genuine
"terminal style view" of what the remote agent is doing, which is also more
honest about what it actually is (a weaker, less-supervised engine).
"""

from __future__ import annotations
import asyncio
import os
import re
from pathlib import Path
from typing import AsyncGenerator

from rich.markup import escape

from omoduo.engine.events import RunnerEvent

OLLAMA_API_BASE = "http://192.168.1.82:11434"
OLLAMA_HOST = "192.168.1.82"
OLLAMA_PORT = 11434
DEFAULT_MODEL = "ollama/qwen-noxin-14b"

# Matches ~/, /, ./, ../ style paths, or bare filenames with a common extension.
_PATH_TOKEN_RE = re.compile(
    r"(?:~|\.{1,2})?/[^\s,;:()\[\]{}\"']+"
    r"|\b[\w.-]+\.(?:md|py|txt|json|ya?ml|toml|cfg|ini|sh)\b"
)
MAX_AUTO_READ_FILES = 8


def extract_file_paths(prompt: str, cwd: str | None = None, limit: int = MAX_AUTO_READ_FILES) -> list[str]:
    """Finds file paths mentioned in the prompt that exist on disk.

    Unlike Claude Code/Antigravity (arbitrary filesystem read tools), aider only ever
    sees files explicitly added to its chat session. Without this, a prompt like "look
    at X.md" gives the remote agent nothing to look at and it just acknowledges with a
    bare "Ok." instead of actually answering.
    """
    base = Path(cwd) if cwd else Path.cwd()
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATH_TOKEN_RE.finditer(prompt):
        token = match.group(0).rstrip(".,;:!?)")
        candidate = Path(token).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved)
        if resolved.is_file() and key not in seen:
            seen.add(key)
            found.append(key)
        if len(found) >= limit:
            break
    return found


async def check_rig_reachable(host: str = OLLAMA_HOST, port: int = OLLAMA_PORT, timeout: float = 3.0) -> bool:
    """Quick TCP reachability check for the LAN Ollama rig -- doesn't need a full request."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


class RemoteRunner:
    """Invokes aider headlessly against the LAN Ollama rig, streaming raw stdout."""

    def __init__(self, model: str = DEFAULT_MODEL, api_base: str = OLLAMA_API_BASE):
        self.model = model
        self.api_base = api_base
        self._current_process: asyncio.subprocess.Process | None = None

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[RunnerEvent, None]:
        """Runs aider --message headlessly, yielding each stdout line as a work event."""
        read_paths = extract_file_paths(prompt, cwd)
        cmd = ["aider", "--model", self.model, "--yes", "--no-auto-commits"]
        for path in read_paths:
            cmd += ["--read", path]
        cmd += ["--message", prompt]
        env = {**os.environ, "OLLAMA_API_BASE": self.api_base}

        if read_paths:
            names = ", ".join(Path(p).name for p in read_paths)
            yield RunnerEvent(f"[auto-attached {len(read_paths)} referenced file(s): {escape(names)}]", kind="work")

        collected: list[str] = []
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._current_process = process

            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace").rstrip("\n")
                if not line.strip():
                    continue
                collected.append(line)
                yield RunnerEvent(escape(line), kind="work")

            await process.wait()
            if process.returncode not in (0, None) and process.returncode != -15:
                yield RunnerEvent(
                    f"[remote agent exited with status {process.returncode}]",
                    kind="error",
                )

        except FileNotFoundError:
            yield RunnerEvent(
                "[remote agent unavailable: 'aider' not found on PATH]", kind="error"
            )
        except Exception as e:  # noqa: BLE001
            yield RunnerEvent(f"[remote agent error: {e}]", kind="error")
        finally:
            self._current_process = None

        final_text = "\n".join(collected).strip()
        yield RunnerEvent(final_text, kind="final", final_text=final_text)

    def cancel(self):
        """Terminates the in-flight aider subprocess, if any."""
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()

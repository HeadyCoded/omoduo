"""Async runner for Claude Code execution with persistent session and permissions."""

import asyncio
import uuid
from typing import AsyncGenerator

class ClaudeRunner:
    """Invokes Claude Code in print/headless mode with session continuity and permissions."""

    def __init__(self, binary_path: str = "claude"):
        self.binary_path = binary_path
        self._current_process: asyncio.subprocess.Process | None = None
        self.session_id: str = str(uuid.uuid4())
        self.has_started: bool = False

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[str, None]:
        """Runs claude -p with session continuity and auto-approved permissions."""
        cmd = [self.binary_path, "--dangerously-skip-permissions"]

        if not self.has_started:
            cmd.extend(["--session-id", self.session_id])
            self.has_started = True
        else:
            cmd.extend(["--resume", self.session_id])

        cmd.extend(["-p", prompt])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._current_process = process

            # Read stdout chunk by chunk
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode(errors="replace")

            # Check stderr for any notices/warnings
            stderr_out = await process.stderr.read()
            if stderr_out:
                text = stderr_out.decode(errors="replace").strip()
                # filter internal harmless session banners
                if text and "Session:" not in text:
                    yield f"\n[stderr] {text}"

            await process.wait()

        except asyncio.CancelledError:
            if self._current_process and self._current_process.returncode is None:
                self._current_process.terminate()
            raise
        except Exception as e:
            yield f"\n[Claude Error: {e}]"
        finally:
            self._current_process = None

    def cancel(self):
        """Terminates active process if running."""
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()

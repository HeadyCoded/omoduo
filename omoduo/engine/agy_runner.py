"""Async runner for Antigravity (agy) CLI execution with permissions."""

import asyncio
from typing import AsyncGenerator

class AgyRunner:
    """Invokes Antigravity CLI in print/headless mode with permissions and streaming."""

    def __init__(self, binary_path: str = "agy"):
        self.binary_path = binary_path
        self._current_process: asyncio.subprocess.Process | None = None

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[str, None]:
        """Runs agy -p with auto-approved permissions."""
        cmd = [self.binary_path, "--dangerously-skip-permissions", "-p", prompt]

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
                if text:
                    yield f"\n[stderr] {text}"

            await process.wait()

        except asyncio.CancelledError:
            if self._current_process and self._current_process.returncode is None:
                self._current_process.terminate()
            raise
        except Exception as e:
            yield f"\n[Antigravity Error: {e}]"
        finally:
            self._current_process = None

    def cancel(self):
        """Terminates active process if running."""
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()

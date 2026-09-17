"""Async runner for Antigravity (agy) CLI execution with conversation continuity and stream-json."""

from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator

from rich.markup import escape

from omoduo.engine.events import RunnerEvent, format_agy_tool, format_tool_snippet


class AgyRunner:
    """Invokes Antigravity CLI in print/headless mode with permissions, continuity, and streaming."""

    def __init__(self, binary_path: str = "agy"):
        self.binary_path = binary_path
        self._current_process: asyncio.subprocess.Process | None = None
        self.conversation_id: str | None = None

    def reset_session(self) -> None:
        """Resets conversation ID tracking."""
        self.conversation_id = None

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[RunnerEvent, None]:
        """Runs agy -p with stream-json, auto-approved permissions, and conversation continuity."""
        cmd = [
            self.binary_path,
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
        ]

        if self.conversation_id:
            cmd.extend(["--conversation", self.conversation_id])

        cmd.extend(["-p", prompt])

        accumulated_text: list[str] = []
        final_emitted: bool = False

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._current_process = process

            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                raw_line = line_bytes.decode(errors="replace").strip()
                if not raw_line:
                    continue

                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    yield RunnerEvent(escape(raw_line), kind="work")
                    continue

                event = data.get("event")

                if event == "init":
                    cid = data.get("conversation_id")
                    if cid:
                        self.conversation_id = cid

                elif event == "step_update":
                    su = data.get("step_update", {})
                    step_type = su.get("step_type")
                    state = su.get("state")

                    if step_type == "tool":
                        tool_name = su.get("tool_name", "")
                        tool_info = su.get("tool_info", {})
                        params = tool_info.get("parameters", {})

                        if state == "ACTIVE":
                            summary = format_agy_tool(tool_name, params)
                            yield RunnerEvent(
                                f"[bold #7dcfff]>>> {summary}[/]",
                                kind="tool_call",
                                tool_name=tool_name,
                                tool_input=params,
                            )
                        elif state == "DONE":
                            out = tool_info.get("output", "")
                            snippet = format_tool_snippet(out)
                            if snippet:
                                yield RunnerEvent(
                                    snippet,
                                    kind="tool_result",
                                    tool_name=tool_name,
                                    tool_output=str(out),
                                )

                    elif step_type == "agent_response":
                        delta = su.get("text_delta", "")
                        if delta:
                            accumulated_text.append(delta)
                            yield RunnerEvent(
                                escape(delta),
                                kind="delta",
                            )

                elif event == "result":
                    res = data.get("result", {})
                    cid = res.get("conversation_id") or data.get("conversation_id")
                    if cid:
                        self.conversation_id = cid

                    response = res.get("response", "")
                    if not response and accumulated_text:
                        response = "".join(accumulated_text)

                    final_emitted = True
                    yield RunnerEvent(
                        escape(response),
                        kind="final",
                        final_text=response,
                    )

            stderr_out = await process.stderr.read()
            if stderr_out:
                text = stderr_out.decode(errors="replace").strip()
                if text:
                    yield RunnerEvent(f"[dim]\\[stderr] {escape(text)}[/]", kind="work")

            await process.wait()

        except asyncio.CancelledError:
            if self._current_process and self._current_process.returncode is None:
                self._current_process.terminate()
            raise
        except Exception as e:
            yield RunnerEvent(f"[bold red]Antigravity Error: {escape(str(e))}[/]", kind="error")
        finally:
            self._current_process = None
            if not final_emitted and accumulated_text:
                fallback = "".join(accumulated_text).strip()
                yield RunnerEvent(escape(fallback), kind="final", final_text=fallback)

    def cancel(self):
        """Terminates active process if running."""
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()

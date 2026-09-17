"""Async runner for Claude Code execution with persistent session, stream-json, and permissions."""

from __future__ import annotations
import asyncio
import json
import uuid
from typing import AsyncGenerator

from rich.markup import escape

from omoduo.engine.events import RunnerEvent, format_claude_tool, format_tool_snippet


class ClaudeRunner:
    """Invokes Claude Code in print/headless mode with session continuity, stream-json, and permissions."""

    def __init__(self, binary_path: str = "claude"):
        self.binary_path = binary_path
        self._current_process: asyncio.subprocess.Process | None = None
        self.session_id: str = str(uuid.uuid4())
        self.has_started: bool = False

    def reset_session(self) -> None:
        """Resets conversation session UUID."""
        self.session_id = str(uuid.uuid4())
        self.has_started = False

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[RunnerEvent, None]:
        """Runs claude -p with session continuity, stream-json, and auto-approved permissions."""
        cmd = [
            self.binary_path,
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]

        starting_new_session = not self.has_started
        if starting_new_session:
            cmd.extend(["--session-id", self.session_id])
        else:
            cmd.extend(["--resume", self.session_id])

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
            # Only commit to "session started" once the process actually launched -
            # otherwise a launch failure permanently strands us on --resume for a
            # session that was never created.
            if starting_new_session:
                self.has_started = True

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

                msg_type = data.get("type")

                if msg_type == "system":
                    sid = data.get("session_id")
                    if sid:
                        self.session_id = sid

                elif msg_type == "stream_event":
                    ev = data.get("event", {})
                    ev_type = ev.get("type")

                    if ev_type == "content_block_start":
                        block = ev.get("content_block", {})
                        # tool_use blocks are announced from the full "assistant"
                        # message below instead, once the tool name AND its
                        # input are known - avoids a duplicate, less-informative
                        # "Tool: X" line for every call.
                        if block.get("type") == "thinking":
                            yield RunnerEvent(
                                "[dim italic]thinking...[/]",
                                kind="thinking",
                            )

                    elif ev_type == "content_block_delta":
                        delta = ev.get("delta", {})
                        delta_type = delta.get("type")
                        if delta_type == "thinking_delta":
                            thought = delta.get("thinking", "")
                            if thought.strip():
                                yield RunnerEvent(
                                    f"[dim italic]{escape(thought.strip())}[/]",
                                    kind="thinking",
                                )
                        elif delta_type == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                accumulated_text.append(chunk)
                                yield RunnerEvent(
                                    escape(chunk),
                                    kind="delta",
                                )

                elif msg_type == "assistant":
                    message = data.get("message", {})
                    for block in message.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "")
                            tool_input = block.get("input", {})
                            summary = format_claude_tool(name, tool_input)
                            yield RunnerEvent(
                                f"[bold #ff9e64]>>> {summary}[/]",
                                kind="tool_call",
                                tool_name=name,
                                tool_input=tool_input,
                            )

                elif msg_type == "user":
                    tool_res = data.get("tool_use_result")
                    if tool_res and isinstance(tool_res, dict):
                        stdout = tool_res.get("stdout", "")
                        snippet = format_tool_snippet(stdout)
                        if snippet:
                            yield RunnerEvent(
                                snippet,
                                kind="tool_result",
                                tool_output=stdout,
                            )

                elif msg_type == "result":
                    sid = data.get("session_id")
                    if sid:
                        self.session_id = sid
                    result_text = data.get("result", "")
                    if not result_text and accumulated_text:
                        result_text = "".join(accumulated_text)
                    final_emitted = True
                    yield RunnerEvent(
                        escape(result_text),
                        kind="final",
                        final_text=result_text,
                    )

            stderr_out = await process.stderr.read()
            if stderr_out:
                text = stderr_out.decode(errors="replace").strip()
                if text and "Session:" not in text:
                    yield RunnerEvent(f"[dim]\\[stderr] {escape(text)}[/]", kind="work")

            await process.wait()

        except asyncio.CancelledError:
            if self._current_process and self._current_process.returncode is None:
                self._current_process.terminate()
            raise
        except Exception as e:
            yield RunnerEvent(f"[bold red]Claude Error: {escape(str(e))}[/]", kind="error")
        finally:
            self._current_process = None
            if not final_emitted and accumulated_text:
                fallback = "".join(accumulated_text).strip()
                yield RunnerEvent(escape(fallback), kind="final", final_text=fallback)

    def cancel(self):
        """Terminates active process if running."""
        if self._current_process and self._current_process.returncode is None:
            self._current_process.terminate()

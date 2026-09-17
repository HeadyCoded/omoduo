"""Orchestrator coordinating TaskRouter, ClaudeRunner, and AgyRunner."""

from __future__ import annotations
import asyncio
from typing import Callable, Any

from omoduo.engine.router import TaskRouter, RoutingDecision
from omoduo.engine.claude_runner import ClaudeRunner
from omoduo.engine.agy_runner import AgyRunner
from omoduo.engine.events import RunnerEvent


class Orchestrator:
    """Coordinates dual engines, conversation memory, state locks, and event streaming."""

    def __init__(
        self,
        router: TaskRouter | None = None,
        claude_runner: ClaudeRunner | None = None,
        agy_runner: AgyRunner | None = None,
    ):
        self.router = router or TaskRouter()
        self.claude_runner = claude_runner or ClaudeRunner()
        self.agy_runner = agy_runner or AgyRunner()
        self.is_busy = False
        self._lock = asyncio.Lock()
        self.last_engine: str | None = None
        self.history: list[dict[str, str]] = []  # [{"speaker": ..., "text": ...}]

    def _build_contextual_prompt(self, prompt: str) -> str:
        """Injects recent conversation turns so engines have full session memory."""
        if not self.history:
            return prompt

        # Include up to the last 8 messages
        recent = self.history[-8:]
        lines = []
        for item in recent:
            spk = item["speaker"]
            txt = item["text"]
            # Keep snippets concise to avoid token explosion
            snippet = txt if len(txt) < 800 else txt[:800] + "... [trimmed]"
            lines.append(f"{spk}: {snippet}")

        context_block = "\n".join(lines)
        return (
            f"[Prior Conversation History in this session]:\n"
            f"{context_block}\n\n"
            f"[Current User Request]:\n"
            f"{prompt}"
        )

    async def execute_turn(
        self,
        prompt: str,
        cwd: str | None,
        on_status_change: Callable[[str, str], None],  # (engine, status)
        on_claude_chunk: Callable[[str], None],
        on_agy_chunk: Callable[[str], None],
        on_conversation_chunk: Callable[[str, str], None],  # (speaker, text)
    ):
        """Executes a full user turn with memory injection, routing, and real-time streaming."""
        async with self._lock:
            self.is_busy = True
            decision: RoutingDecision = self.router.route(prompt, last_engine=self.last_engine)
            self.last_engine = decision.primary_engine

            # Record user input in conversation memory
            self.history.append({"speaker": "User", "text": prompt})

            # Prepare contextual prompt
            contextual_prompt = self._build_contextual_prompt(decision.clean_prompt)

            try:
                if decision.primary_engine == "claude":
                    on_status_change("claude", "Running")
                    on_status_change("agy", "Idle")
                    on_conversation_chunk("system", f"Routed to Claude: {decision.reason}")

                    claude_work: list[str] = []
                    final_reply = ""

                    async for event in self.claude_runner.stream(contextual_prompt, cwd=cwd):
                        kind = getattr(event, "kind", "work")
                        if kind == "tool_call":
                            tool = getattr(event, "tool_name", "")
                            on_status_change("claude", f"Tool: {tool}" if tool else "Tool")
                            on_claude_chunk(str(event))
                        elif kind in ("tool_result", "thinking", "work"):
                            on_claude_chunk(str(event))
                        elif kind == "delta":
                            on_status_change("claude", "Responding")
                        elif kind == "final":
                            final_reply = getattr(event, "final_text", str(event))
                            on_claude_chunk(str(event))
                        elif kind == "error":
                            on_claude_chunk(str(event))
                        else:
                            on_claude_chunk(str(event))

                        if not final_reply and isinstance(event, str):
                            claude_work.append(str(event))

                    reply = final_reply.strip() or "".join(claude_work).strip()
                    self.history.append({"speaker": "Claude", "text": reply})
                    on_conversation_chunk("Claude", reply)
                    on_status_change("claude", "Finished")

                elif decision.primary_engine == "agy":
                    on_status_change("agy", "Running")
                    on_status_change("claude", "Idle")
                    on_conversation_chunk("system", f"Routed to Antigravity: {decision.reason}")

                    agy_work: list[str] = []
                    final_reply = ""

                    async for event in self.agy_runner.stream(contextual_prompt, cwd=cwd):
                        kind = getattr(event, "kind", "work")
                        if kind == "tool_call":
                            tool = getattr(event, "tool_name", "")
                            on_status_change("agy", f"Tool: {tool}" if tool else "Tool")
                            on_agy_chunk(str(event))
                        elif kind in ("tool_result", "thinking", "work"):
                            on_agy_chunk(str(event))
                        elif kind == "delta":
                            on_status_change("agy", "Responding")
                        elif kind == "final":
                            final_reply = getattr(event, "final_text", str(event))
                            on_agy_chunk(str(event))
                        elif kind == "error":
                            on_agy_chunk(str(event))
                        else:
                            on_agy_chunk(str(event))

                        if not final_reply and isinstance(event, str):
                            agy_work.append(str(event))

                    reply = final_reply.strip() or "".join(agy_work).strip()
                    self.history.append({"speaker": "Antigravity", "text": reply})
                    on_conversation_chunk("Antigravity", reply)
                    on_status_change("agy", "Finished")

                elif decision.primary_engine == "both":
                    on_conversation_chunk(
                        "system",
                        "Collaborative turn: Antigravity drafting spec/frames, then Claude implementing...",
                    )

                    # Stage 1: Antigravity
                    on_status_change("agy", "Running (Stage 1)")
                    on_status_change("claude", "Waiting")
                    agy_stage_prompt = (
                        f"{contextual_prompt}\n\n"
                        "[Collaboration Note]: You are Stage 1 (Architect / Asset Designer). Provide the complete spec, design, or ASCII frames so Claude can package and implement it in Stage 2."
                    )
                    agy_work = []
                    agy_final_reply = ""
                    async for event in self.agy_runner.stream(agy_stage_prompt, cwd=cwd):
                        kind = getattr(event, "kind", "work")
                        if kind == "tool_call":
                            tool = getattr(event, "tool_name", "")
                            on_status_change("agy", f"Stage 1: {tool}" if tool else "Stage 1: Tool")
                            on_agy_chunk(str(event))
                        elif kind in ("tool_result", "thinking", "work"):
                            on_agy_chunk(str(event))
                        elif kind == "final":
                            agy_final_reply = getattr(event, "final_text", str(event))
                            on_agy_chunk(str(event))
                        elif kind == "error":
                            on_agy_chunk(str(event))
                        else:
                            on_agy_chunk(str(event))

                        if not agy_final_reply and isinstance(event, str):
                            agy_work.append(str(event))

                    on_status_change("agy", "Complete")
                    agy_result = agy_final_reply.strip() or "".join(agy_work).strip()

                    # Stage 2: Claude with Antigravity's context
                    on_status_change("claude", "Running (Stage 2)")
                    claude_stage_prompt = (
                        f"{contextual_prompt}\n\n"
                        f"[Context and Assets from Antigravity]:\n{agy_result}\n\n"
                        "[Collaboration Note]: You are Stage 2 (Implementer / Packager). Take Antigravity's spec and assets above and write the code, create files, and deliver the working application as requested."
                    )
                    claude_work = []
                    claude_final_reply = ""
                    async for event in self.claude_runner.stream(claude_stage_prompt, cwd=cwd):
                        kind = getattr(event, "kind", "work")
                        if kind == "tool_call":
                            tool = getattr(event, "tool_name", "")
                            on_status_change("claude", f"Stage 2: {tool}" if tool else "Stage 2: Tool")
                            on_claude_chunk(str(event))
                        elif kind in ("tool_result", "thinking", "work"):
                            on_claude_chunk(str(event))
                        elif kind == "final":
                            claude_final_reply = getattr(event, "final_text", str(event))
                            on_claude_chunk(str(event))
                        elif kind == "error":
                            on_claude_chunk(str(event))
                        else:
                            on_claude_chunk(str(event))

                        if not claude_final_reply and isinstance(event, str):
                            claude_work.append(str(event))

                    on_status_change("claude", "Complete")
                    reply = claude_final_reply.strip() or "".join(claude_work).strip()
                    self.history.append({"speaker": "Claude & Antigravity", "text": reply})
                    on_conversation_chunk("Claude & Antigravity", reply)

            finally:
                self.is_busy = False

    def cancel_active(self):
        """Cancels running subprocesses."""
        self.claude_runner.cancel()
        self.agy_runner.cancel()
        self.is_busy = False

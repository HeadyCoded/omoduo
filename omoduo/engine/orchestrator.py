"""Orchestrator coordinating TaskRouter, ClaudeRunner, and AgyRunner."""

from __future__ import annotations
import asyncio
from typing import Callable, Any

from omoduo.engine.router import TaskRouter, RoutingDecision
from omoduo.engine.claude_runner import ClaudeRunner
from omoduo.engine.agy_runner import AgyRunner
from omoduo.engine.remote_runner import RemoteRunner
from omoduo.engine.events import RunnerEvent
from omoduo.engine import team

HISTORY_WINDOW = 24  # was 8 -- too aggressive for a multi-day training/comparison session


class Orchestrator:
    """Coordinates dual engines, conversation memory, state locks, and event streaming."""

    def __init__(
        self,
        router: TaskRouter | None = None,
        claude_runner: ClaudeRunner | None = None,
        agy_runner: AgyRunner | None = None,
        remote_runner: RemoteRunner | None = None,
    ):
        self.router = router or TaskRouter()
        self.claude_runner = claude_runner or ClaudeRunner()
        self.agy_runner = agy_runner or AgyRunner()
        self.remote_runner = remote_runner or RemoteRunner()
        self.is_busy = False
        self._lock = asyncio.Lock()
        self.last_engine: str | None = None
        self.history: list[dict[str, str]] = []  # [{"speaker": ..., "text": ...}]

    def _build_contextual_prompt(self, prompt: str) -> str:
        """Injects recent conversation turns + team-awareness preamble."""
        if not self.history:
            return team.build_prompt(prompt)

        recent = self.history[-HISTORY_WINDOW:]
        lines = []
        for item in recent:
            spk = item["speaker"]
            txt = item["text"]
            # Keep snippets concise to avoid token explosion
            snippet = txt if len(txt) < 800 else txt[:800] + "... [trimmed]"
            lines.append(f"{spk}: {snippet}")

        context_block = "\n".join(lines)
        contextual = (
            f"[Prior Conversation History in this session]:\n"
            f"{context_block}\n\n"
            f"[Current User Request]:\n"
            f"{prompt}"
        )
        return team.build_prompt(contextual)

    async def execute_turn(
        self,
        prompt: str,
        cwd: str | None,
        on_status_change: Callable[[str, str], None],  # (engine, status)
        on_claude_chunk: Callable[[str], None],
        on_agy_chunk: Callable[[str], None],
        on_remote_chunk: Callable[[str], None],
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
                    on_status_change("remote", "Idle")
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
                    on_status_change("remote", "Idle")
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
                    on_status_change("remote", "Idle")
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

                elif decision.primary_engine == "remote":
                    on_status_change("remote", "Running")
                    on_status_change("claude", "Idle")
                    on_status_change("agy", "Idle")
                    on_conversation_chunk("system", f"Routed to remote agent: {decision.reason}")

                    reply = await self._run_single(
                        "remote", self.remote_runner, contextual_prompt, cwd,
                        on_status_change, on_remote_chunk,
                    )
                    self.history.append({"speaker": "Remote Agent", "text": reply})
                    on_conversation_chunk("Remote Agent", reply)
                    on_status_change("remote", "Finished")

                elif decision.primary_engine == "all":
                    on_conversation_chunk(
                        "system",
                        "Comparison turn: sending the same prompt to Claude, Antigravity, "
                        "and the remote agent concurrently -- compare their answers to spot "
                        "hallucination or drift.",
                    )
                    on_status_change("claude", "Running")
                    on_status_change("agy", "Running")
                    on_status_change("remote", "Running")

                    results = await asyncio.gather(
                        self._run_single("claude", self.claude_runner, contextual_prompt, cwd,
                                          on_status_change, on_claude_chunk),
                        self._run_single("agy", self.agy_runner, contextual_prompt, cwd,
                                          on_status_change, on_agy_chunk),
                        self._run_single("remote", self.remote_runner, contextual_prompt, cwd,
                                          on_status_change, on_remote_chunk),
                        return_exceptions=True,
                    )
                    for name, result in zip(("Claude", "Antigravity", "Remote Agent"), results):
                        text = f"[error: {result}]" if isinstance(result, Exception) else result
                        self.history.append({"speaker": name, "text": text})
                        on_conversation_chunk(name, text)

                    on_status_change("claude", "Complete")
                    on_status_change("agy", "Complete")
                    on_status_change("remote", "Complete")

                elif decision.primary_engine == "duo":
                    on_conversation_chunk(
                        "system",
                        "Duo turn (future-team rehearsal): Antigravity drafting spec/frames, "
                        "then the remote agent implementing...",
                    )
                    on_status_change("agy", "Running (Stage 1)")
                    on_status_change("remote", "Waiting")
                    on_status_change("claude", "Idle")

                    agy_stage_prompt = (
                        f"{contextual_prompt}\n\n"
                        "[Collaboration Note]: You are Stage 1 (Architect / Asset Designer). "
                        "Provide the complete spec, design, or ASCII frames so the remote agent "
                        "can implement it in Stage 2."
                    )
                    agy_result = await self._run_single(
                        "agy", self.agy_runner, agy_stage_prompt, cwd,
                        on_status_change, on_agy_chunk, label_prefix="Stage 1: ",
                    )
                    on_status_change("agy", "Complete")

                    remote_stage_prompt = (
                        f"{contextual_prompt}\n\n"
                        f"[Context and Assets from Antigravity]:\n{agy_result}\n\n"
                        "[Collaboration Note]: You are Stage 2 (Implementer). Take Antigravity's "
                        "spec and assets above and write the code, create files, and deliver the "
                        "working result as requested. If anything in Stage 1's spec looks wrong "
                        "or impossible, say so rather than implementing it anyway."
                    )
                    on_status_change("remote", "Running (Stage 2)")
                    remote_result = await self._run_single(
                        "remote", self.remote_runner, remote_stage_prompt, cwd,
                        on_status_change, on_remote_chunk, label_prefix="Stage 2: ",
                    )
                    on_status_change("remote", "Complete")

                    self.history.append({"speaker": "Antigravity & Remote Agent", "text": remote_result})
                    on_conversation_chunk("Antigravity & Remote Agent", remote_result)

            finally:
                self.is_busy = False

    async def _run_single(
        self,
        engine: str,
        runner,
        prompt: str,
        cwd: str | None,
        on_status_change: Callable[[str, str], None],
        on_chunk: Callable[[str], None],
        label_prefix: str = "",
    ) -> str:
        """Streams one runner's events to its pane/status, returns the accumulated reply.

        Shared by the remote/all/duo branches so their event-kind handling doesn't
        triple the same block the claude/agy/both branches above already have
        (left untouched since they're the existing, already-tested code paths).
        """
        work: list[str] = []
        final_reply = ""
        async for event in runner.stream(prompt, cwd=cwd):
            kind = getattr(event, "kind", "work")
            if kind == "tool_call":
                tool = getattr(event, "tool_name", "")
                on_status_change(engine, f"{label_prefix}Tool: {tool}" if tool else f"{label_prefix}Tool")
                on_chunk(str(event))
            elif kind in ("tool_result", "thinking", "work"):
                on_chunk(str(event))
            elif kind == "delta":
                on_status_change(engine, f"{label_prefix}Responding")
            elif kind == "final":
                final_reply = getattr(event, "final_text", str(event))
                on_chunk(str(event))
            elif kind == "error":
                on_chunk(str(event))
            else:
                on_chunk(str(event))

            if not final_reply and isinstance(event, str):
                work.append(str(event))

        return final_reply.strip() or "".join(work).strip()

    def cancel_active(self):
        """Cancels running subprocesses."""
        self.claude_runner.cancel()
        self.agy_runner.cancel()
        self.remote_runner.cancel()
        self.is_busy = False

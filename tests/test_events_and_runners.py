"""Tests for RunnerEvent, tool formatting, ClaudeRunner, AgyRunner, and collaborative flow."""

import asyncio
from typing import AsyncGenerator
from omoduo.engine.events import (
    RunnerEvent,
    format_claude_tool,
    format_agy_tool,
    format_tool_snippet,
)
from omoduo.engine.claude_runner import ClaudeRunner
from omoduo.engine.agy_runner import AgyRunner
from omoduo.engine.orchestrator import Orchestrator
from omoduo.engine.router import TaskRouter


def test_runner_event_string_subclass():
    ev = RunnerEvent(
        "[bold]>>> [Bash][/] pytest",
        kind="tool_call",
        tool_name="Bash",
        tool_input={"command": "pytest"},
    )
    assert isinstance(ev, str)
    assert ev.kind == "tool_call"
    assert ev.tool_name == "Bash"
    assert "pytest" in ev
    assert ev.startswith("[bold]")


def test_format_claude_tool():
    # Bash
    res = format_claude_tool("Bash", {"command": "git status --short"})
    assert res == "> git status --short"

    # Edit / Read / Write with full path
    res = format_claude_tool("Edit", {"file_path": "/home/noxin/Work/omoduo/omoduo/app.py"})
    assert res == "[Edit] app.py"

    # Grep
    res = format_claude_tool("Grep", {"pattern": "TaskRouter"})
    assert res == "grep: TaskRouter"

    # Unknown
    res = format_claude_tool("CustomTool", {})
    assert res == "[CustomTool]"


def test_format_agy_tool():
    # run_command
    res = format_agy_tool("run_command", {"CommandLine": "cargo build --release"})
    assert res == "> cargo build --release"

    # view_file / replace_file_content
    res = format_agy_tool("view_file", {"AbsolutePath": "/home/noxin/Work/omoduo/omoduo/theme.py"})
    assert res == "[view] theme.py"

    res = format_agy_tool("replace_file_content", {"TargetFile": "/path/to/main.rs"})
    assert res == "[edit] main.rs"

    # grep_search
    res = format_agy_tool("grep_search", {"Query": "def stream"})
    assert res == "grep: def stream"


def test_format_tool_snippet():
    raw = "line 1\nline 2\nline 3\nline 4"
    snippet = format_tool_snippet(raw, max_lines=2)
    assert "line 1 | line 2" in snippet
    assert "[dim]" in snippet

    empty = format_tool_snippet("")
    assert empty == ""


def test_claude_runner_command_generation():
    runner = ClaudeRunner(binary_path="mock-claude")
    initial_id = runner.session_id

    # Verify session reset
    runner.reset_session()
    assert runner.session_id != initial_id
    assert not runner.has_started


def test_agy_runner_command_generation():
    runner = AgyRunner(binary_path="mock-agy")
    assert runner.conversation_id is None

    runner.conversation_id = "test-conv-1234"
    runner.reset_session()
    assert runner.conversation_id is None


def test_orchestrator_collaborative_both_route():
    class MockStage1AgyRunner:
        def __init__(self):
            self.invoked_prompts = []

        async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[RunnerEvent, None]:
            self.invoked_prompts.append(prompt)
            yield RunnerEvent("[>>> grep_search: audio]", kind="tool_call", tool_name="grep_search")
            yield RunnerEvent("Here is the architectural audio spec.", kind="final", final_text="Here is the architectural audio spec.")

        def cancel(self):
            pass

    class MockStage2ClaudeRunner:
        def __init__(self):
            self.invoked_prompts = []

        async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[RunnerEvent, None]:
            self.invoked_prompts.append(prompt)
            yield RunnerEvent("[>>> [Edit] audio.py]", kind="tool_call", tool_name="Edit")
            yield RunnerEvent("Implemented the audio pipeline.", kind="final", final_text="Implemented the audio pipeline.")

        def cancel(self):
            pass

    async def _test():
        agy_runner = MockStage1AgyRunner()
        claude_runner = MockStage2ClaudeRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(),
            claude_runner=claude_runner,
            agy_runner=agy_runner,
        )

        statuses = []
        claude_chunks = []
        agy_chunks = []
        convo_chunks = []

        await orchestrator.execute_turn(
            prompt="@both collaborate on the audio pipeline",
            cwd="/tmp",
            on_status_change=lambda eng, st: statuses.append((eng, st)),
            on_claude_chunk=lambda ch: claude_chunks.append(ch),
            on_agy_chunk=lambda ch: agy_chunks.append(ch),
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        # Stage 1 Antigravity must be invoked first
        assert len(agy_runner.invoked_prompts) == 1
        assert "Stage 1 (Architect / Asset Designer)" in agy_runner.invoked_prompts[0]
        assert len(agy_chunks) == 2

        # Stage 2 Claude must be invoked with Antigravity's context
        assert len(claude_runner.invoked_prompts) == 1
        assert "Context and Assets from Antigravity" in claude_runner.invoked_prompts[0]
        assert "Here is the architectural audio spec." in claude_runner.invoked_prompts[0]
        assert len(claude_chunks) == 2

        # Final unified response
        assert any(spk == "Claude & Antigravity" for spk, _ in convo_chunks)
        final_msg = [tx for spk, tx in convo_chunks if spk == "Claude & Antigravity"][0]
        assert final_msg == "Implemented the audio pipeline."

    asyncio.run(_test())


def test_claude_stream_ndjson_parsing():
    import json

    runner = ClaudeRunner()
    raw_lines = [
        json.dumps({"type": "system", "session_id": "session-xyz-1"}),
        json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "Let's check the repo"}}}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]}}),
        json.dumps({"type": "user", "tool_use_result": {"stdout": "total 42\nfile1\nfile2"}}),
        json.dumps({"type": "result", "result": "Finished refactor."}),
    ]

    class FakeStdout:
        def __init__(self, lines):
            self.lines = [l.encode() + b"\n" for l in lines]
            self.idx = 0

        async def readline(self):
            if self.idx >= len(self.lines):
                return b""
            line = self.lines[self.idx]
            self.idx += 1
            return line

    class FakeStderr:
        async def read(self):
            return b""

    class FakeProcess:
        def __init__(self, lines):
            self.stdout = FakeStdout(lines)
            self.stderr = FakeStderr()
            self.returncode = 0

        async def wait(self):
            return 0

    async def _test():
        # Patch create_subprocess_exec
        orig_exec = asyncio.create_subprocess_exec

        async def mock_exec(*args, **kwargs):
            return FakeProcess(raw_lines)

        asyncio.create_subprocess_exec = mock_exec
        try:
            events = []
            async for ev in runner.stream("test prompt"):
                events.append(ev)

            assert runner.session_id == "session-xyz-1"
            assert any(e.kind == "thinking" and "Let's check the repo" in e for e in events)
            assert any(e.kind == "tool_call" and e.tool_name == "Bash" for e in events)
            assert any(e.kind == "tool_result" for e in events)
            assert any(e.kind == "final" and e.final_text == "Finished refactor." for e in events)
        finally:
            asyncio.create_subprocess_exec = orig_exec

    asyncio.run(_test())


def test_agy_stream_ndjson_parsing():
    import json

    runner = AgyRunner()
    raw_lines = [
        json.dumps({"event": "init", "conversation_id": "conv-agy-999"}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "state": "ACTIVE", "tool_name": "grep_search", "tool_info": {"parameters": {"Query": "TODO"}}}}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "state": "DONE", "tool_name": "grep_search", "tool_info": {"output": "main.py:10: TODO fix"}}}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "agent_response", "state": "ACTIVE", "text_delta": "Found 1 TODO."}}),
        json.dumps({"event": "result", "result": {"response": "Found 1 TODO.", "status": "SUCCESS"}}),
    ]

    class FakeStdout:
        def __init__(self, lines):
            self.lines = [l.encode() + b"\n" for l in lines]
            self.idx = 0

        async def readline(self):
            if self.idx >= len(self.lines):
                return b""
            line = self.lines[self.idx]
            self.idx += 1
            return line

    class FakeStderr:
        async def read(self):
            return b""

    class FakeProcess:
        def __init__(self, lines):
            self.stdout = FakeStdout(lines)
            self.stderr = FakeStderr()
            self.returncode = 0

        async def wait(self):
            return 0

    async def _test():
        orig_exec = asyncio.create_subprocess_exec

        async def mock_exec(*args, **kwargs):
            return FakeProcess(raw_lines)

        asyncio.create_subprocess_exec = mock_exec
        try:
            events = []
            async for ev in runner.stream("test search"):
                events.append(ev)

            assert runner.conversation_id == "conv-agy-999"
            assert any(e.kind == "tool_call" and e.tool_name == "grep_search" for e in events)
            assert any(e.kind == "tool_result" and "main.py" in e.tool_output for e in events)
            assert any(e.kind == "delta" and "Found 1 TODO." in e for e in events)
            assert any(e.kind == "final" and e.final_text == "Found 1 TODO." for e in events)
        finally:
            asyncio.create_subprocess_exec = orig_exec

    asyncio.run(_test())


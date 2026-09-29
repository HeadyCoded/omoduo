"""Tests for Orchestrator coordinating execution, memory, and UI callbacks."""

import asyncio
from typing import AsyncGenerator
from omoduo.engine.orchestrator import Orchestrator
from omoduo.engine.router import TaskRouter

class MockClaudeRunner:
    def __init__(self):
        self.invoked_prompts = []

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[str, None]:
        self.invoked_prompts.append(prompt)
        yield "Claude working...\n"
        yield "Claude completed refactor."

    def cancel(self):
        pass

class MockAgyRunner:
    def __init__(self):
        self.invoked_prompts = []

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[str, None]:
        self.invoked_prompts.append(prompt)
        yield "Antigravity searching...\n"
        yield "Found 3 files matching pattern."

    def cancel(self):
        pass

class MockRemoteRunner:
    def __init__(self):
        self.invoked_prompts = []

    async def stream(self, prompt: str, cwd: str | None = None) -> AsyncGenerator[str, None]:
        self.invoked_prompts.append(prompt)
        yield "remote: applying edit...\n"
        yield "remote done."

    def cancel(self):
        pass

def test_orchestrator_claude_route():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
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
            prompt="refactor the parser function",
            cwd="/tmp",
            on_status_change=lambda eng, st: statuses.append((eng, st)),
            on_claude_chunk=lambda ch: claude_chunks.append(ch),
            on_agy_chunk=lambda ch: agy_chunks.append(ch),
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        assert len(claude_runner.invoked_prompts) == 1
        assert len(agy_runner.invoked_prompts) == 0
        assert len(claude_chunks) == 2
        assert len(agy_chunks) == 0
        assert any(spk == "Claude" for spk, _ in convo_chunks)

    asyncio.run(_test())

def test_orchestrator_agy_route():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
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
            prompt="search codebase for database models",
            cwd="/tmp",
            on_status_change=lambda eng, st: statuses.append((eng, st)),
            on_claude_chunk=lambda ch: claude_chunks.append(ch),
            on_agy_chunk=lambda ch: agy_chunks.append(ch),
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        assert len(claude_runner.invoked_prompts) == 0
        assert len(agy_runner.invoked_prompts) == 1
        assert len(claude_chunks) == 0
        assert len(agy_chunks) == 2
        assert any(spk == "Antigravity" for spk, _ in convo_chunks)

    asyncio.run(_test())

def test_orchestrator_multi_turn_history():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(),
            claude_runner=claude_runner,
            agy_runner=agy_runner,
        )

        # Turn 1: User asks initial prompt
        await orchestrator.execute_turn(
            prompt="Make an application called OffGrump",
            cwd="/tmp",
            on_status_change=lambda eng, st: None,
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: None,
        )

        # Turn 2: User asks follow up
        await orchestrator.execute_turn(
            prompt="can you help me do it?",
            cwd="/tmp",
            on_status_change=lambda eng, st: None,
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: None,
        )

        # Turn 2 prompt MUST contain Turn 1 context
        second_prompt = claude_runner.invoked_prompts[1]
        assert "OffGrump" in second_prompt
        assert "Prior Conversation History" in second_prompt

    asyncio.run(_test())

def test_orchestrator_remote_route():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
        remote_runner = MockRemoteRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(),
            claude_runner=claude_runner,
            agy_runner=agy_runner,
            remote_runner=remote_runner,
        )

        statuses = []
        remote_chunks = []
        convo_chunks = []

        await orchestrator.execute_turn(
            prompt="@remote add a get_version function",
            cwd="/tmp",
            on_status_change=lambda eng, st: statuses.append((eng, st)),
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: remote_chunks.append(ch),
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        assert remote_runner.invoked_prompts
        assert not claude_runner.invoked_prompts
        assert not agy_runner.invoked_prompts
        assert ("remote", "Running") in statuses
        assert ("remote", "Finished") in statuses
        assert any(spk == "Remote Agent" for spk, _ in convo_chunks)

    asyncio.run(_test())

def test_orchestrator_all_route_dispatches_to_all_three():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
        remote_runner = MockRemoteRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(),
            claude_runner=claude_runner,
            agy_runner=agy_runner,
            remote_runner=remote_runner,
        )

        convo_chunks = []

        await orchestrator.execute_turn(
            prompt="@all what does this repo do?",
            cwd="/tmp",
            on_status_change=lambda eng, st: None,
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        assert claude_runner.invoked_prompts
        assert agy_runner.invoked_prompts
        assert remote_runner.invoked_prompts
        speakers = {spk for spk, _ in convo_chunks}
        assert {"Claude", "Antigravity", "Remote Agent"}.issubset(speakers)

    asyncio.run(_test())

def test_orchestrator_duo_route_stages_agy_then_remote():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
        remote_runner = MockRemoteRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(),
            claude_runner=claude_runner,
            agy_runner=agy_runner,
            remote_runner=remote_runner,
        )

        convo_chunks = []

        await orchestrator.execute_turn(
            prompt="@duo build a settings screen",
            cwd="/tmp",
            on_status_change=lambda eng, st: None,
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: convo_chunks.append((spk, tx)),
        )

        assert not claude_runner.invoked_prompts
        assert agy_runner.invoked_prompts
        assert remote_runner.invoked_prompts
        # Remote's stage-2 prompt must carry Antigravity's stage-1 output forward
        assert "Context and Assets from Antigravity" in remote_runner.invoked_prompts[0]
        assert any(spk == "Antigravity & Remote Agent" for spk, _ in convo_chunks)

    asyncio.run(_test())

def test_team_preamble_present_in_every_prompt():
    async def _test():
        claude_runner = MockClaudeRunner()
        agy_runner = MockAgyRunner()
        orchestrator = Orchestrator(
            router=TaskRouter(), claude_runner=claude_runner, agy_runner=agy_runner
        )

        await orchestrator.execute_turn(
            prompt="@claude do a thing",
            cwd="/tmp",
            on_status_change=lambda eng, st: None,
            on_claude_chunk=lambda ch: None,
            on_agy_chunk=lambda ch: None,
            on_remote_chunk=lambda ch: None,
            on_conversation_chunk=lambda spk, tx: None,
        )

        prompt_sent = claude_runner.invoked_prompts[0]
        assert "dangerously-skip-permissions" in prompt_sent
        assert "Team context" in prompt_sent

    asyncio.run(_test())

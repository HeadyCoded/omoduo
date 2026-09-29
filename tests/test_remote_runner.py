"""Tests for RemoteRunner (aider against the LAN Ollama rig) and the hallucination log."""

import asyncio
import json
import tempfile
from pathlib import Path

from omoduo.engine.remote_runner import RemoteRunner, extract_file_paths
from omoduo.engine.halluc_log import log_hallucination
import omoduo.engine.halluc_log as halluc_log_module


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


class FakeProcess:
    def __init__(self, lines, returncode=0):
        self.stdout = FakeStdout(lines)
        self.returncode = returncode

    async def wait(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15


def test_remote_runner_streams_lines_and_final():
    runner = RemoteRunner()
    raw_lines = ["Added foo.py to the chat.", "Applied edit to foo.py", ""]

    async def mock_exec(*args, **kwargs):
        return FakeProcess(raw_lines)

    orig_exec = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = mock_exec
    try:
        async def _test():
            events = []
            async for ev in runner.stream("fix the bug", cwd="/tmp"):
                events.append(ev)
            return events

        events = asyncio.run(_test())
    finally:
        asyncio.create_subprocess_exec = orig_exec

    work_events = [e for e in events if getattr(e, "kind", "") == "work"]
    final_events = [e for e in events if getattr(e, "kind", "") == "final"]
    assert len(work_events) == 2
    assert "Applied edit to foo.py" in str(work_events[1])
    assert len(final_events) == 1
    assert "Applied edit to foo.py" in final_events[0].final_text


def test_remote_runner_reports_nonzero_exit():
    runner = RemoteRunner()

    async def mock_exec(*args, **kwargs):
        return FakeProcess(["some output"], returncode=1)

    orig_exec = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = mock_exec
    try:
        async def _test():
            events = []
            async for ev in runner.stream("do a thing"):
                events.append(ev)
            return events

        events = asyncio.run(_test())
    finally:
        asyncio.create_subprocess_exec = orig_exec

    error_events = [e for e in events if getattr(e, "kind", "") == "error"]
    assert error_events
    assert "status 1" in str(error_events[0])


def test_remote_runner_missing_binary_yields_error_not_exception():
    runner = RemoteRunner()

    async def mock_exec(*args, **kwargs):
        raise FileNotFoundError("aider not found")

    orig_exec = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = mock_exec
    try:
        async def _test():
            events = []
            async for ev in runner.stream("do a thing"):
                events.append(ev)
            return events

        events = asyncio.run(_test())
    finally:
        asyncio.create_subprocess_exec = orig_exec

    assert any(getattr(e, "kind", "") == "error" for e in events)


def test_extract_file_paths_finds_absolute_and_home_paths(tmp_path):
    real_file = tmp_path / "CONVENTIONS.md"
    real_file.write_text("stuff")
    prompt = f"Look at {real_file} and also the per-project CONVENTIONS.md files"

    found = extract_file_paths(prompt, cwd=str(tmp_path))

    assert found == [str(real_file)]


def test_extract_file_paths_ignores_nonexistent_paths(tmp_path):
    prompt = "Look at /this/path/does/not/exist.md please"

    found = extract_file_paths(prompt, cwd=str(tmp_path))

    assert found == []


def test_extract_file_paths_dedupes_and_caps_at_limit(tmp_path):
    paths = []
    for i in range(10):
        f = tmp_path / f"file{i}.md"
        f.write_text("x")
        paths.append(str(f))
    prompt = "check " + " ".join(paths + [paths[0]])

    found = extract_file_paths(prompt, cwd=str(tmp_path), limit=8)

    assert len(found) == 8
    assert len(set(found)) == 8


def test_remote_runner_passes_read_flags_for_referenced_files(tmp_path):
    real_file = tmp_path / "notes.md"
    real_file.write_text("stuff")
    runner = RemoteRunner()
    captured_cmd = {}

    async def mock_exec(*args, **kwargs):
        captured_cmd["args"] = args
        return FakeProcess(["Ok."])

    orig_exec = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = mock_exec
    try:
        async def _test():
            events = []
            async for ev in runner.stream(f"look at {real_file}", cwd=str(tmp_path)):
                events.append(ev)
            return events

        events = asyncio.run(_test())
    finally:
        asyncio.create_subprocess_exec = orig_exec

    cmd = captured_cmd["args"]
    assert "--read" in cmd
    assert str(real_file) in cmd
    work_events = [e for e in events if getattr(e, "kind", "") == "work"]
    assert any("auto-attached" in str(e) for e in work_events)


def test_log_hallucination_writes_jsonl(monkeypatch, tmp_path):
    log_path = tmp_path / "hallucination-log.jsonl"
    monkeypatch.setattr(halluc_log_module, "LOG_PATH", log_path)

    returned_path = log_hallucination("what does clamp do", "an invented API description", note="bad")

    assert returned_path == log_path
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["prompt"] == "what does clamp do"
    assert entry["response"] == "an invented API description"
    assert entry["note"] == "bad"
    assert "timestamp" in entry

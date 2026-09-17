"""Structured event models and tool formatters for runner streams."""

from __future__ import annotations
from typing import Any

from rich.markup import escape


class RunnerEvent(str):
    """A string subclass carrying structured metadata from engine stream events.

    Inheriting from `str` preserves full backward-compatibility with any consumer
    expecting raw text chunks, while exposing rich attributes like `kind`,
    `tool_name`, and `final_text`.
    """

    kind: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    final_text: str

    def __new__(
        cls,
        content: str = "",
        kind: str = "work",
        tool_name: str = "",
        tool_input: dict[str, Any] | None = None,
        tool_output: str = "",
        final_text: str = "",
    ):
        obj = super().__new__(cls, content)
        obj.kind = kind
        obj.tool_name = tool_name
        obj.tool_input = tool_input or {}
        obj.tool_output = tool_output
        obj.final_text = final_text
        return obj


def format_tool_snippet(output: Any, max_lines: int = 2, max_len: int = 75) -> str:
    """Formats a concise preview snippet of tool output."""
    if not output:
        return ""
    text = str(output).strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    preview_lines = lines[:max_lines]
    joined = " | ".join(preview_lines)
    if len(joined) > max_len:
        joined = joined[: max_len - 3] + "..."
    return f"[dim]  | {escape(joined)}[/]"


def format_claude_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Formats Claude Code tool calls for Tokyo Night terminal display."""
    safe_name = escape(name)
    if name == "Bash":
        cmd = tool_input.get("command", "")
        return f"> {escape(cmd[:65])}"
    if name in ("Edit", "Read", "Write"):
        fp = tool_input.get("file_path") or tool_input.get("path") or ""
        short = fp.split("/")[-1] if fp else ""
        return f"[{safe_name}] {escape(short)}"
    if name in ("Grep", "Glob"):
        pat = tool_input.get("pattern", "")
        return f"{name.lower()}: {escape(pat[:35])}"
    if name == "Task":
        desc = tool_input.get("description", "")
        return f"task: {escape(desc[:40])}"
    if name == "WebSearch":
        q = tool_input.get("query", "")
        return f"search: {escape(q[:40])}"
    if name == "WebFetch":
        url = tool_input.get("url", "")
        return f"fetch: {escape(url[:50])}"
    return f"[{safe_name}]"


def format_agy_tool(name: str, params: dict[str, Any]) -> str:
    """Formats Antigravity CLI tool calls for Tokyo Night terminal display."""
    safe_name = escape(name)
    if name == "run_command":
        cmd = params.get("CommandLine", "")
        return f"> {escape(cmd[:65])}"
    if name in ("view_file", "write_to_file", "replace_file_content"):
        path = params.get("TargetFile") or params.get("AbsolutePath") or ""
        short = path.split("/")[-1] if path else ""
        action = "view" if name == "view_file" else "edit" if name == "replace_file_content" else "write"
        return f"[{action}] {escape(short)}"
    if name == "grep_search":
        q = params.get("Query", "")
        return f"grep: {escape(q[:35])}"
    if name == "find_by_name":
        p = params.get("Pattern", "")
        return f"find: {escape(p[:35])}"
    if name == "list_dir":
        d = params.get("DirectoryPath", "")
        short = d.split("/")[-1] if d else ""
        return f"ls: {escape(short)}"
    return f"[{safe_name}]"

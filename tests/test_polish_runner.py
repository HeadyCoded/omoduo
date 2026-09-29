"""Tests for PolishRunner: rant -> candidate prompt parsing and error handling."""

import asyncio
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from omoduo.engine.polish_runner import PolishError, PolishRunner


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_polish_parses_json_array():
    async def _test():
        runner = PolishRunner()
        body = {"message": {"content": json.dumps(["Option one", "Option two", "Option three"])}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            return await runner.polish("rambling idea about a dashboard")

    assert asyncio.run(_test()) == ["Option one", "Option two", "Option three"]


def test_polish_parses_object_wrapped_array():
    async def _test():
        runner = PolishRunner()
        body = {"message": {"content": json.dumps({"options": ["A", "B"]})}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            return await runner.polish("idea")

    assert asyncio.run(_test()) == ["A", "B"]


def test_polish_falls_back_to_numbered_lines():
    async def _test():
        runner = PolishRunner()
        content = "1. First option\n2. Second option\n- Third option"
        body = {"message": {"content": content}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            return await runner.polish("idea")

    assert asyncio.run(_test()) == ["First option", "Second option", "Third option"]


def test_polish_strips_markdown_fences():
    async def _test():
        runner = PolishRunner()
        content = '```json\n["A", "B"]\n```'
        body = {"message": {"content": content}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            return await runner.polish("idea")

    assert asyncio.run(_test()) == ["A", "B"]


def test_polish_raises_on_unreachable_ollama():
    async def _test():
        runner = PolishRunner()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            await runner.polish("idea")

    with pytest.raises(PolishError, match="Could not reach the LAN Ollama rig"):
        asyncio.run(_test())


def test_polish_raises_on_empty_content():
    async def _test():
        runner = PolishRunner()
        body = {"message": {"content": "   "}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            await runner.polish("idea")

    with pytest.raises(PolishError, match="no usable prompt options"):
        asyncio.run(_test())


def test_polish_raises_on_malformed_nested_json():
    """Regression: llama3.2:3b under strict JSON grammar sometimes emits a single
    long sentence as an object key mapped to {}, plus junk {} keys, instead of a
    clean options array. This must raise, not silently return the raw JSON blob
    as one garbage 'option'."""

    async def _test():
        runner = PolishRunner()
        content = json.dumps(
            {
                "Fix the double TTS reads and add a Spotify overlay.": {},
                "{}": {},
            }
        )
        body = {"message": {"content": content}}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            await runner.polish("idea")

    with pytest.raises(PolishError, match="unexpected shape"):
        asyncio.run(_test())


def test_polish_raises_on_ollama_error_field():
    async def _test():
        runner = PolishRunner()
        body = {"error": "model 'llama3.2:3b' not found"}
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            await runner.polish("idea")

    with pytest.raises(PolishError, match="model 'llama3.2:3b' not found"):
        asyncio.run(_test())

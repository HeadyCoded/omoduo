"""Tests for the ConversationPane's prompt input widget."""

import asyncio

from textual import events
from textual.app import App, ComposeResult

from omoduo.widgets.conversation import ConversationPane, PromptInput


class _HarnessApp(App):
    def compose(self) -> ComposeResult:
        self.pane = ConversationPane(id="conversation-pane")
        yield self.pane


def test_prompt_input_paste_keeps_full_multiline_text():
    async def _run():
        app = _HarnessApp()
        async with app.run_test() as pilot:
            input_field = app.pane.input_field
            input_field.focus()
            paste_text = "@claude line one\nline two\nline three"
            input_field.post_message(events.Paste(paste_text))
            await pilot.pause()
            return input_field.value

    value = asyncio.run(_run())
    assert value == "@claude line one line two line three"


def test_prompt_input_paste_single_line_unaffected():
    async def _run():
        app = _HarnessApp()
        async with app.run_test() as pilot:
            input_field = app.pane.input_field
            input_field.focus()
            input_field.post_message(events.Paste("just one line"))
            await pilot.pause()
            return input_field.value

    value = asyncio.run(_run())
    assert value == "just one line"


def test_conversation_pane_uses_prompt_input_subclass():
    pane = ConversationPane(id="conversation-pane")
    assert isinstance(pane.input_field, PromptInput)

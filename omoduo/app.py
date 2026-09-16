"""Main Textual application for omoduo."""

import os
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Static, Input

from omoduo.theme import APP_CSS, TOKYO_NIGHT
from omoduo.widgets.work_pane import WorkPane
from omoduo.widgets.conversation import ConversationPane
from omoduo.widgets.status_bar import StatusBar
from omoduo.engine.orchestrator import Orchestrator

class OmoduoApp(App):
    """3-pane terminal dual-agent orchestrator."""

    CSS = APP_CSS
    TITLE = "omoduo // dual-agent terminal"

    BINDINGS = [
        Binding("escape", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_panes", "Clear Work Panes", show=True),
    ]

    def __init__(self, orchestrator: Orchestrator | None = None, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator = orchestrator or Orchestrator()
        self.claude_pane = WorkPane(
            "Claude Code",
            accent_color=TOKYO_NIGHT["claude_accent"],
            id="claude-pane",
            classes="work-pane",
        )
        self.conversation_pane = ConversationPane(id="conversation-pane")
        self.agy_pane = WorkPane(
            "Antigravity",
            accent_color=TOKYO_NIGHT["agy_accent"],
            id="agy-pane",
            classes="work-pane",
        )
        self.status_bar = StatusBar(id="status-bar")

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #7aa2f7]omoduo[/] [dim]// dual-agent terminal orchestrator (Claude + Antigravity)[/]",
            id="header-bar",
        )
        with Horizontal(id="main-container"):
            yield self.claude_pane
            yield self.conversation_pane
            yield self.agy_pane
        yield self.status_bar

    def on_mount(self):
        """Focus the input field on start."""
        self.conversation_pane.input_field.focus()
        self.conversation_pane.post_system_message("Ready. Type a prompt or prefix with @claude, @agy, or @both.")

    async def on_input_submitted(self, event: Input.Submitted):
        """Triggered when the user hits Enter in the conversation input box."""
        prompt = event.value.strip()
        if not prompt or self.orchestrator.is_busy:
            return

        event.input.value = ""
        self.conversation_pane.post_user_message(prompt)

        # Clear both work panes at start of new turn so only active engine shows work
        self.claude_pane.clear_pane()
        self.agy_pane.clear_pane()

        # Run background worker for non-blocking UI streaming
        self.run_worker(self._run_turn(prompt), exclusive=True)

    async def _run_turn(self, prompt: str):
        """Worker executing turn through orchestrator."""
        def on_status_change(engine: str, status: str):
            if engine == "claude":
                self.claude_pane.set_status(status)
            elif engine == "agy":
                self.agy_pane.set_status(status)
            self.status_bar.update_engine(engine, status)

        def on_claude_chunk(chunk: str):
            self.claude_pane.append_text(chunk)

        def on_agy_chunk(chunk: str):
            self.agy_pane.append_text(chunk)

        def on_conversation_chunk(speaker: str, text: str):
            if speaker == "system":
                self.conversation_pane.post_system_message(text)
            else:
                self.conversation_pane.post_assistant_message(speaker, text)

        await self.orchestrator.execute_turn(
            prompt=prompt,
            cwd=os.getcwd(),
            on_status_change=on_status_change,
            on_claude_chunk=on_claude_chunk,
            on_agy_chunk=on_agy_chunk,
            on_conversation_chunk=on_conversation_chunk,
        )

    def action_clear_panes(self):
        """Action for Ctrl+L shortcut."""
        self.claude_pane.clear_pane()
        self.agy_pane.clear_pane()
        self.conversation_pane.post_system_message("Work panes cleared.")

def run():
    app = OmoduoApp()
    app.run()

if __name__ == "__main__":
    run()

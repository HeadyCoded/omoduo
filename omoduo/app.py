"""Main Textual application for omoduo."""

import os
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Static, Input

from omoduo.theme import APP_CSS, TOKYO_NIGHT
from omoduo.widgets.work_pane import WorkPane
from omoduo.widgets.conversation import ConversationPane
from omoduo.widgets.status_bar import StatusBar
from omoduo.widgets.polish_screen import PolishScreen
from omoduo.engine.orchestrator import Orchestrator
from omoduo.engine.remote_runner import check_rig_reachable
from omoduo.engine.halluc_log import log_hallucination

REMOTE_REPLY_SPEAKERS = ("Remote Agent", "Antigravity & Remote Agent")


class OmoduoApp(App):
    """4-pane terminal orchestrator: Claude, Antigravity, a LAN remote agent, and their conversation."""

    CSS = APP_CSS
    TITLE = "omoduo // team terminal"

    BINDINGS = [
        Binding("escape", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_panes", "Clear Work Panes", show=True),
        Binding("ctrl+x", "cancel_turn", "Cancel Turn", show=True),
        Binding("ctrl+r", "toggle_polish", "Rant->Prompt", show=True),
        Binding("ctrl+h", "flag_hallucination", "Flag Hallucination", show=True),
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
        self.remote_pane = WorkPane(
            "Remote Agent",
            accent_color=TOKYO_NIGHT["remote_accent"],
            id="remote-pane",
            classes="work-pane",
        )
        self.status_bar = StatusBar(id="status-bar")
        self._last_user_prompt: str = ""
        self._last_remote_reply: str = ""

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #7aa2f7]omoduo[/] [dim]// team terminal orchestrator (Claude + Antigravity + Remote Agent)[/]",
            id="header-bar",
        )
        with Horizontal(id="main-container"):
            yield self.claude_pane
            yield self.conversation_pane
            yield self.agy_pane
            yield self.remote_pane
        yield self.status_bar

    def on_mount(self):
        """Focus the input field on start, and kick off the rig reachability check."""
        self.conversation_pane.input_field.focus()
        self.conversation_pane.post_system_message(
            "Ready. Type a prompt or prefix with @claude, @agy, @remote, @both (Claude+Antigravity), "
            "@duo (Antigravity+Remote), or @all (all three, for comparison). "
            "Ctrl+R to polish a rough idea first. Ctrl+H flags the last remote-agent reply as a "
            "hallucination for later review."
        )
        self.run_worker(self._check_rig(), exclusive=False)
        self.set_interval(60, lambda: self.run_worker(self._check_rig(), exclusive=False))

    async def _check_rig(self):
        reachable = await check_rig_reachable()
        self.status_bar.set_rig_reachable(reachable)

    def on_text_selected(self, event: events.TextSelected) -> None:
        """Auto-copies a mouse-drag selection made in the conversation log, then clears it.

        RichLog gives no other way to get text out of the app -- there's no
        native terminal selection to fall back on since Textual owns the mouse.
        """
        if self.conversation_pane.log_view not in self.screen.selections:
            return
        selected_text = self.screen.get_selected_text()
        if selected_text:
            self.copy_to_clipboard(selected_text)
            self.conversation_pane.post_system_message("Selection copied to clipboard.")
        self.screen.clear_selection()

    async def on_input_submitted(self, event: Input.Submitted):
        """Triggered when the user hits Enter in the conversation input box."""
        prompt = event.value.strip()
        if not prompt or self.orchestrator.is_busy:
            return

        event.input.value = ""
        await self._submit_prompt(prompt)

    async def _submit_prompt(self, prompt: str):
        """Posts the user turn and runs it through the orchestrator."""
        self.conversation_pane.post_user_message(prompt)
        self._last_user_prompt = prompt

        # Clear all work panes at start of new turn so only active engine(s) show work
        self.claude_pane.clear_pane()
        self.agy_pane.clear_pane()
        self.remote_pane.clear_pane()

        # Run background worker for non-blocking UI streaming
        self.run_worker(self._run_turn(prompt), exclusive=True)

    def action_toggle_polish(self):
        """Opens the remote-model rant-to-prompt modal (Ctrl+R)."""
        if self.orchestrator.is_busy:
            self.conversation_pane.post_system_message(
                "Busy with a turn -- wait for it to finish before polishing a new idea."
            )
            return
        self.push_screen(PolishScreen(), callback=self._on_polish_result)

    def _on_polish_result(self, result: str | None):
        """Callback for PolishScreen: submits the chosen prompt to @all, if one was picked."""
        if not result:
            return
        prompt = result if result.startswith("@") else f"@all {result}"
        self.run_worker(self._submit_prompt(prompt), exclusive=True)

    def action_flag_hallucination(self):
        """Action for Ctrl+H: logs the last remote-agent reply as a flagged hallucination."""
        if not self._last_remote_reply:
            self.conversation_pane.post_system_message(
                "No remote-agent reply to flag yet this session."
            )
            return
        path = log_hallucination(self._last_user_prompt, self._last_remote_reply)
        self.conversation_pane.post_system_message(f"Flagged. Logged to {path}")

    async def _run_turn(self, prompt: str):
        """Worker executing turn through orchestrator."""
        def on_status_change(engine: str, status: str):
            if engine == "claude":
                self.claude_pane.set_status(status)
            elif engine == "agy":
                self.agy_pane.set_status(status)
            elif engine == "remote":
                self.remote_pane.set_status(status)
            self.status_bar.update_engine(engine, status)

        def on_claude_chunk(chunk: str):
            self.claude_pane.append_text(chunk)

        def on_agy_chunk(chunk: str):
            self.agy_pane.append_text(chunk)

        def on_remote_chunk(chunk: str):
            self.remote_pane.append_text(chunk)

        def on_conversation_chunk(speaker: str, text: str):
            if speaker == "system":
                self.conversation_pane.post_system_message(text)
            else:
                self.conversation_pane.post_assistant_message(speaker, text)
                if speaker in REMOTE_REPLY_SPEAKERS:
                    self._last_remote_reply = text

        await self.orchestrator.execute_turn(
            prompt=prompt,
            cwd=os.getcwd(),
            on_status_change=on_status_change,
            on_claude_chunk=on_claude_chunk,
            on_agy_chunk=on_agy_chunk,
            on_remote_chunk=on_remote_chunk,
            on_conversation_chunk=on_conversation_chunk,
        )

    def action_clear_panes(self):
        """Action for Ctrl+L shortcut."""
        self.claude_pane.clear_pane()
        self.agy_pane.clear_pane()
        self.remote_pane.clear_pane()
        self.conversation_pane.post_system_message("Work panes cleared.")

    def action_cancel_turn(self):
        """Action for Ctrl+X shortcut: aborts the in-flight engine turn, if any."""
        if not self.orchestrator.is_busy:
            return
        self.orchestrator.cancel_active()
        self.claude_pane.set_status("Idle")
        self.agy_pane.set_status("Idle")
        self.remote_pane.set_status("Idle")
        self.status_bar.update_engine("claude", "Idle")
        self.status_bar.update_engine("agy", "Idle")
        self.status_bar.update_engine("remote", "Idle")
        self.conversation_pane.post_system_message("Turn cancelled.")

def run():
    app = OmoduoApp()
    app.run()

if __name__ == "__main__":
    run()

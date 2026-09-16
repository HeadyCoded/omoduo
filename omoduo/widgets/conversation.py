"""Central conversation pane and input widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog, Input
from rich.text import Text
from rich.panel import Panel
from omoduo.theme import TOKYO_NIGHT

class ConversationPane(Vertical):
    """Middle panel displaying the dialogue thread and prompt input."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.header_label = Static("[bold #c0caf5]CONVERSATION[/] [dim](Middle Window)[/]", id="conv-header")
        self.log_view = RichLog(highlight=True, markup=True, wrap=True, id="conversation-log")
        self.input_field = Input(placeholder="Type your prompt... (prefix @claude, @agy, or @both to override)", id="input-box")

    def compose(self) -> ComposeResult:
        yield self.header_label
        yield self.log_view
        yield self.input_field

    def post_user_message(self, message: str):
        """Displays user message in the thread."""
        self.log_view.write(f"\n[bold {TOKYO_NIGHT['user_accent']}]You[/]: {message}")

    def post_system_message(self, message: str):
        """Displays a system/routing notice in the thread."""
        self.log_view.write(f"[dim {TOKYO_NIGHT['fg_dim']}]-- {message} --[/]")

    def post_assistant_message(self, speaker: str, message: str):
        """Displays agent response in the thread."""
        if "Claude" in speaker:
            color = TOKYO_NIGHT["claude_accent"]
        elif "Antigravity" in speaker:
            color = TOKYO_NIGHT["agy_accent"]
        else:
            color = TOKYO_NIGHT["success"]

        self.log_view.write(f"\n[bold {color}]{speaker}[/]:\n{message}\n")

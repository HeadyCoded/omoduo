"""Work response pane widget for Claude and Antigravity."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from rich.text import Text

class WorkPane(Vertical):
    """Side panel displaying the live work output of a single engine."""

    def __init__(self, engine_name: str, accent_color: str, **kwargs):
        super().__init__(**kwargs)
        self.engine_name = engine_name
        self.accent_color = accent_color
        self.header_label = Static(f"{self.engine_name} [IDLE]", id="pane-header")
        self.log_view = RichLog(highlight=True, markup=True, wrap=True)

    def compose(self) -> ComposeResult:
        yield self.header_label
        yield self.log_view

    def set_status(self, status: str):
        """Updates the header status badge."""
        color = self.accent_color if status == "Running" else "dim"
        self.header_label.update(f"[{self.accent_color}]{self.engine_name}[/] [{color}]({status})[/]")

    def append_text(self, text: str):
        """Appends output text to the work stream log."""
        self.log_view.write(text)

    def clear_pane(self):
        """Clears the stream view when idle or resetting."""
        self.log_view.clear()
        self.set_status("Idle")

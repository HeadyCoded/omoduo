"""Central conversation pane and input widget."""

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog, Input
from rich.text import Text
from rich.panel import Panel
from rich.markup import escape
from omoduo.theme import TOKYO_NIGHT


class PromptInput(Input):
    """Single-line Input that keeps the whole clipboard on paste.

    Textual's stock Input._on_paste() takes only event.text.splitlines()[0] --
    reasonable for a single-line widget in general, but it silently drops
    everything after the first line, which is exactly what a multi-paragraph
    prompt is. Joining lines with a space instead keeps every word (still
    fine to submit -- Input.value is just a string, embedded structure isn't
    needed for the text to reach an engine correctly), it just renders and
    scrolls as one long line instead of being truncated.
    """

    def _on_paste(self, event: events.Paste) -> None:
        if event.text:
            flattened = " ".join(event.text.splitlines())
            selection = self.selection
            if selection.is_empty:
                self.insert_text_at_cursor(flattened)
            else:
                self.replace(flattened, *selection)
        # Textual dispatches _on_paste from every class in the MRO independently
        # (it's not a normal method override) -- prevent_default() is what stops
        # the base Input._on_paste from *also* running and double-inserting;
        # stop() only affects bubbling to ancestor widgets, a different mechanism.
        event.prevent_default()
        event.stop()


class ConversationPane(Vertical):
    """Middle panel displaying the dialogue thread and prompt input."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.header_label = Static("[bold #c0caf5]CONVERSATION[/] [dim](Middle Window)[/]", id="conv-header")
        self.log_view = RichLog(highlight=True, markup=True, wrap=True, id="conversation-log")
        self.input_field = PromptInput(placeholder="Type your prompt... (@claude, @agy, @remote, @both, @duo, @all)", id="input-box")

    def compose(self) -> ComposeResult:
        yield self.header_label
        yield self.log_view
        yield self.input_field

    def post_user_message(self, message: str):
        """Displays user message in the thread."""
        self.log_view.write(f"\n[bold {TOKYO_NIGHT['user_accent']}]You[/]: {escape(message)}")

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

        self.log_view.write(f"\n[bold {color}]{speaker}[/]:\n{escape(message)}\n")

"""Modal screen: rant -> local-model polished prompt options -> pick one."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from omoduo.engine.polish_runner import PolishError, PolishRunner


class PolishScreen(ModalScreen[str | None]):
    """Lets the user brain-dump an idea, get N candidate prompts from a local model, pick one.

    Dismisses with the chosen prompt string, or None if cancelled. Nothing here ever
    touches Claude or Antigravity -- it's a local-only scratch pad until a pick is made.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+g", "generate", "Generate", show=True),
    ]

    def __init__(self, runner: PolishRunner | None = None, **kwargs):
        super().__init__(**kwargs)
        self.runner = runner or PolishRunner()
        self._options: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="polish-dialog"):
            yield Static(
                "[bold #bb9af7]Rant -> Prompt[/] [dim](local model, stays on this machine "
                "until you pick one -- Ctrl+G to generate, Esc to cancel)[/]",
                id="polish-header",
            )
            yield TextArea(id="rant-input")
            yield Button("Generate options (Ctrl+G)", id="generate-btn", variant="primary")
            yield Static("", id="polish-status")
            yield VerticalScroll(id="polish-options")

    def on_mount(self):
        self.query_one("#rant-input", TextArea).focus()

    def action_cancel(self):
        self.dismiss(None)

    def action_generate(self):
        self.run_worker(self._generate(), exclusive=True)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "generate-btn":
            await self._generate()
        elif button_id.startswith("opt-"):
            index = int(button_id.removeprefix("opt-"))
            self.dismiss(self._options[index])

    def on_key(self, event) -> None:
        if event.key in tuple("123456789"):
            index = int(event.key) - 1
            if 0 <= index < len(self._options):
                self.dismiss(self._options[index])
                event.stop()

    async def _generate(self) -> None:
        rant = self.query_one("#rant-input", TextArea).text.strip()
        if not rant:
            return

        status = self.query_one("#polish-status", Static)
        generate_btn = self.query_one("#generate-btn", Button)
        options_box = self.query_one("#polish-options", VerticalScroll)

        status.update("[dim]Thinking locally... (first run may need to load the model)[/]")
        generate_btn.disabled = True
        await options_box.remove_children()
        self._options = []

        try:
            options = await self.runner.polish(rant)
        except PolishError as e:
            status.update(f"[bold #f7768e]{e}[/]")
            generate_btn.disabled = False
            return

        self._options = options
        status.update("[dim]Pick one (click, or press 1-9):[/]")
        for i, option in enumerate(options):
            await options_box.mount(Button(f"{i + 1}. {option}", id=f"opt-{i}", classes="polish-option"))
        generate_btn.disabled = False

        # Move focus off the rant TextArea, which otherwise swallows digit keys as
        # text input rather than letting them bubble up as pick-an-option shortcuts.
        if options:
            self.query_one("#opt-0", Button).focus()

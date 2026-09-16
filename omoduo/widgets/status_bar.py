"""Status bar widget displaying project directory and engine status."""

import os
import subprocess
from textual.app import ComposeResult
from textual.widgets import Static
from omoduo.theme import TOKYO_NIGHT

class StatusBar(Static):
    """Bottom bar showing current workspace and engine states."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.claude_status = "Idle"
        self.agy_status = "Idle"
        self.cwd = os.getcwd()
        self.branch = self._get_git_branch()

    def _get_git_branch(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout.strip() or "no-git"
        except Exception:
            return "no-git"

    def render(self) -> str:
        claude_color = TOKYO_NIGHT["claude_accent"] if self.claude_status != "Idle" else TOKYO_NIGHT["fg_dim"]
        agy_color = TOKYO_NIGHT["agy_accent"] if self.agy_status != "Idle" else TOKYO_NIGHT["fg_dim"]

        return (
            f"[dim]{self.cwd}[/] "
            f"([bold #7aa2f7]{self.branch}[/])  |  "
            f"Claude: [{claude_color}]{self.claude_status}[/]  |  "
            f"Antigravity: [{agy_color}]{self.agy_status}[/]  |  "
            f"[dim]ESC: quit[/]"
        )

    def update_engine(self, engine: str, status: str):
        if engine == "claude":
            self.claude_status = status
        elif engine == "agy":
            self.agy_status = status
        self.refresh()

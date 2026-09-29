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
        self.remote_status = "Idle"
        self.rig_reachable: bool | None = None  # None = not checked yet
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
        remote_color = TOKYO_NIGHT["remote_accent"] if self.remote_status != "Idle" else TOKYO_NIGHT["fg_dim"]

        if self.rig_reachable is None:
            rig_badge = "[dim]rig: checking...[/]"
        elif self.rig_reachable:
            rig_badge = f"[{TOKYO_NIGHT['success']}]rig: up[/]"
        else:
            rig_badge = f"[{TOKYO_NIGHT['error']}]rig: unreachable[/]"

        return (
            f"[dim]{self.cwd}[/] "
            f"([bold #7aa2f7]{self.branch}[/])  |  "
            f"Claude: [{claude_color}]{self.claude_status}[/]  |  "
            f"Antigravity: [{agy_color}]{self.agy_status}[/]  |  "
            f"Remote: [{remote_color}]{self.remote_status}[/] ({rig_badge})  |  "
            f"[dim]ESC: quit[/]"
        )

    def update_engine(self, engine: str, status: str):
        if engine == "claude":
            self.claude_status = status
        elif engine == "agy":
            self.agy_status = status
        elif engine == "remote":
            self.remote_status = status
        self.refresh()

    def set_rig_reachable(self, reachable: bool):
        self.rig_reachable = reachable
        self.refresh()

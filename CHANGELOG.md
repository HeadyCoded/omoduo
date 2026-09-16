# Changelog

All notable changes to `omoduo` will be documented in this file.

## [0.1.0] - 2026-09-16

### Added
- Initial release of `omoduo`: Native 3-pane terminal dual-agent TUI for Omarchy.
- `TaskRouter`: Rule-based intent and keyword heuristics supporting `@claude`, `@agy`, and `@both` overrides.
- `ClaudeRunner` and `AgyRunner`: Asynchronous subprocess runners streaming live stdout/stderr with `--dangerously-skip-permissions` for uninterrupted file writing.
- Persistent `--session-id` and `--resume` tracking in `ClaudeRunner` to maintain model memory across turns.
- `Orchestrator`: Multi-turn conversational memory injection, state locking, turn budgets, and staged collaboration passes.
- `TaskRouter`: Expanded `DUAL_PATTERNS` to catch "work together", "pair up", "team up", and conversational stickiness for follow-up questions.
- Tokyo Night styling matching Omarchy desktop scheme.
- 3-pane Textual UI layout:
  - Left pane: `Claude Code` work response.
  - Middle pane: Unified conversation thread and input bar.
  - Right pane: `Antigravity` work response.
- `StatusBar` displaying current working directory, active git branch, and engine telemetry.
- Symlinked entrypoint `/home/noxin/.local/bin/omoduo`.
- Desktop entry `~/.local/share/applications/omoduo.desktop` for system app drawer integration.
- Test suite with 7 passing tests across router and orchestrator flows.

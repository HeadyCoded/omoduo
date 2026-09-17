# Changelog

All notable changes to `omoduo` will be documented in this file.

## [0.2.0] - 2026-09-16

### Fixed
- Upgraded `ClaudeRunner` and `AgyRunner` from plaintext buffering to `--output-format stream-json` with live NDJSON stream parsing.
- Added `--verbose` flag to `ClaudeRunner` print mode (required upstream by Claude Code when using `stream-json`).
- Added persistent `conversation_id` tracking and `--conversation` resume support to `AgyRunner` across turns.
- Resolved pane duplication: side work panes now stream live tool invocations (`Bash`, `Edit`, `Read`, `grep_search`, `run_command`), thinking traces, and file snippets, while the central conversation pane receives the clean synthesized markdown response.
- Fixed collaborative `@both` multi-stage execution: Stage 1 (Antigravity) spec and assets are passed cleanly to Stage 2 (Claude) without raw JSON or tool execution clutter.
- Fixed Rich markup injection: any tool output, thinking text, or assistant reply containing bracketed words (e.g. `[stderr]`, `[ 50%]`, `[INFO]`) was being silently swallowed by `RichLog`'s markup parser since raw text was interpolated into markup strings unescaped. All dynamic text is now passed through `rich.markup.escape()` before display.
- Fixed a `ClaudeRunner` session bug where `has_started` was flipped to `True` before the subprocess actually launched; a failed first launch (e.g. missing binary) permanently stranded every later turn on `--resume` for a session that was never created.
- Removed a duplicate tool-call announcement in `ClaudeRunner`: partial `content_block_start` stream events and the full `assistant` message both announced the same tool call, so every call showed up twice in the work pane. Now only the full `assistant` event (which carries the actual command/path) announces it.
- Wired up `Orchestrator.cancel_active()` to a new `Ctrl+X` binding — previously the cancel plumbing existed but nothing in the UI called it, so a hung turn could only be stopped by quitting the whole app.

### Added
- `omoduo.engine.events`: Introduced `RunnerEvent` (a transparent `str` subclass) and Tokyo Night tool formatters for both Claude and Antigravity.
- Added 9 new unit tests covering `RunnerEvent`, tool call formatters, runner session state, collaborative `@both` orchestration, and NDJSON line parsing.
- `Ctrl+X` keybinding to cancel an in-flight engine turn.

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

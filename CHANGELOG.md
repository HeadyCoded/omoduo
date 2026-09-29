# Changelog

All notable changes to `omoduo` will be documented in this file.

## [Unreleased]

### Added
- **Fourth pane: the remote agent.** A new `RemoteRunner` (`omoduo/engine/remote_runner.py`) drives `aider` headlessly against a LAN-hosted Ollama rig, streamed close to verbatim into a new "Remote Agent" pane -- unlike Claude/Antigravity's structured tool-call events, aider has no such protocol, so this is a genuine plain-text terminal view rather than a reformatted summary.
- **New routing prefixes**: `@remote`/`@local` (remote agent only), `@duo` (staged Antigravity-then-remote-agent collaboration, rehearsing the team shape for once Claude Code access ends), `@all`/`@compare` (concurrent 3-way dispatch to all engines, for side-by-side comparison -- read-only/analysis prompts only, since all three share one working directory).
- **Team-awareness preamble** (`omoduo/engine/team.py`): every prompt sent to any engine now opens with a short briefing on the other two engines' roles and access levels -- notably that Antigravity runs with `--dangerously-skip-permissions` (no confirmation before edits/commands), so the others have context for unexplained file changes.
- **Hallucination log** (`omoduo/engine/halluc_log.py`): `Ctrl+H` flags the most recent remote-agent reply, appended as JSONL to `~/.local/share/omoduo/hallucination-log.jsonl` for later use tightening the remote agent's Modelfile/conventions.
- Status bar now shows the remote engine's status and whether the LAN rig is currently reachable (checked on mount and every 60s).
- Conversation history window raised from the last 8 messages to 24 -- 8 was dropping context too aggressively for a multi-turn training/comparison session.

### Changed
- Rant -> Prompt (`Ctrl+R`) now targets the LAN rig's `qwen-noxin-14b` (hardened, anti-hallucination system prompt) instead of a generic local `llama3.2:3b`, and auto-submits picks as `@all` instead of `@both` so the remote agent is included by default.

### Fixed
- **Pasting a multi-line prompt into the main input box silently truncated it to one line.** Textual's stock `Input._on_paste()` only keeps `event.text.splitlines()[0]` -- reasonable for a single-line widget in general, but it drops everything after the first line without any error, which is exactly what a multi-paragraph prompt hits. Added a `PromptInput` subclass (`omoduo/widgets/conversation.py`) that joins pasted lines with spaces instead of truncating, so the full text survives (it renders/scrolls as one long line, which doesn't affect what's actually sent to an engine). Along the way: Textual dispatches `_on_paste` from every class in the MRO independently rather than as a normal override, so the fix also needed `event.prevent_default()` (not just `event.stop()`, which only affects bubbling between widgets) to stop the base `Input` handler from *also* firing and double-inserting the text.
- **`RemoteRunner` couldn't see files a prompt referenced.** Unlike Claude/Antigravity's arbitrary filesystem read tools, aider only sees files explicitly added to its chat session. A prompt like `@all Look at ~/Work/CONVENTIONS.md` gave Claude and Antigravity real answers but left the remote agent nothing to look at, so it just replied `"Ok."` -- indistinguishable from the pane hanging. Fixed by having `remote_runner.extract_file_paths()` scan the prompt for existing file paths (`~/`, absolute, or bare-with-extension) and pass each as `--read` before invoking aider, so `@all` comparisons are apples-to-apples. Note: this doesn't fix vague "look at X" phrasing getting a bare acknowledgment even with the file attached -- that needs an explicit ask ("summarize X", "list issues in Y"); an attempted prompt-nudge to fix this generically backfired (the model hallucinated a fake edit to unrelated, unattached files instead), so it was reverted and left as a "phrase remote prompts as explicit questions" habit instead of a code fix.
- Two leftover `print("DEBUG ...")` calls in `app.py`'s text-selection handler -- raw prints inside a full-screen Textual app can leak into the terminal's alternate screen buffer and visually corrupt the display.
- `_submit_prompt`'s pane-clearing only knew about the Claude/Antigravity panes, which would have left stale remote-agent output on screen across unrelated turns once the third pane existed.
- `PolishRunner` schema/parsing: `llama3.2:3b` under Ollama's strict JSON grammar sometimes emitted a malformed nested object (one giant sentence as an object key mapped to `{}`, plus junk `{}` keys) instead of a clean array. The old parser silently swallowed this and returned the raw JSON blob as a single garbage "option." Fixed by requesting an explicit `{"options": [...]}` schema in the prompt and making the parser reject non-string / wrongly-shaped JSON with a clear `PolishError` instead of guessing.
- `PolishScreen` keyboard shortcuts: focus stayed on the rant `TextArea` after options rendered, so pressing `1`-`9` typed a digit into the box instead of picking an option (only clicking worked). Fixed by moving focus to the first option button once results render.

### Added
- **Rant -> Prompt (`Ctrl+R`)**: New `PolishScreen` modal backed by `omoduo.engine.polish_runner.PolishRunner`. Sends a rough brain-dumped idea to a local Ollama model (default `llama3.2:3b`), which returns several distinct cleaned-up prompt options; picking one (click or `1`-`9`) auto-submits it as `@both <choice>`. Fully local and optional -- direct typed input in the main box is unaffected, and nothing is sent to Claude or Antigravity until a choice is made.
- `PolishRunner._parse_options`: robust parsing of the local model's response -- handles a bare JSON array, a JSON object wrapping a list, markdown code fences the model added anyway, and a numbered/bulleted plain-text fallback if it ignores the JSON instruction entirely.
- 7 new unit tests covering JSON parsing, fallback parsing, and error paths (unreachable Ollama, empty output, Ollama-reported error) in `tests/test_polish_runner.py`.

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

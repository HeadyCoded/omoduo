# omoduo

A lightweight, native terminal TUI orchestrator pairing **Claude Code**,
**Antigravity (Gemini)**, and a **LAN-hosted remote coding agent** side-by-side
on Omarchy.

Built with Python's [Textual](https://github.com/Textualize/textual) framework.

```
+----------+--------------------------------+----------+----------+
| [CLAUDE] |      [UNIFIED CONVERSATION]     | [AGY]    | [REMOTE] |
|          |                                  |          |          |
| Live     | Central back-and-forth log.     | Live     | Live     |
| tool     | Dispatches tasks and synthesizes| tool     | terminal |
| calls.   | responses.                      | calls.   | output.  |
|          |                                  |          |          |
| (Blank   | [Input prompt box...]           | (Blank   | (Blank   |
| if idle) |                                  | if idle) | if idle) |
+----------+--------------------------------+----------+----------+
| Engine: Running | CWD / Git branch | Engine: Idle | rig: up      |
+----------+--------------------------------+----------+----------+
```

![omoduo Terminal Screenshot](omoduo_active.png)

## Features

- **4-Pane Layout**: The central conversation pane is flanked by live
  streaming work windows for Claude, Antigravity, and the remote agent. If
  an engine isn't called for a turn, its window stays blank.
- **Autonomous Intent Routing**: Classifies tasks by shape:
  - Repo exploration, architecture scans, and broad searches route to **Antigravity**.
  - Surgical code edits, bug fixes, test generation, and strict typing route to **Claude Code**.
  - Cooperative multi-stage tasks trigger a staged collaboration pass.
- **Manual Overrides**: Prefix prompts to override routing:
  - `@claude`, `@agy`, `@remote` (or `@local`) -- send to one engine only.
  - `@both` -- staged Antigravity-then-Claude collaboration (the original pairing).
  - `@duo` -- staged Antigravity-then-remote-agent collaboration (rehearsing
    the team shape for once Claude Code access ends).
  - `@all` (or `@compare`) -- sends the same prompt to all three engines
    **concurrently**, for side-by-side comparison. Read-only/analysis
    prompts only -- all three share the same working directory, so a
    concurrent file-editing task risks them clobbering each other's edits.
- **Team awareness**: every prompt sent to any engine is prefixed with a
  short briefing on what the other two engines are and their access level
  -- notably that Antigravity runs with `--dangerously-skip-permissions`
  (no confirmation before edits/commands), so the others understand why
  files might change without an explicit approval step.
- **Remote agent training loop**: `Ctrl+H` flags the most recent remote-agent
  reply as a hallucination, logged to
  `~/.local/share/omoduo/hallucination-log.jsonl` for later use tightening
  the remote agent's Modelfile/conventions.
- **Rant -> Prompt (`Ctrl+R`)**: Brain-dump a rough idea into a modal; the
  remote agent (on the LAN rig, nothing sent to Claude/Antigravity yet)
  turns it into a few cohesive prompt options, you pick one, and it's
  auto-submitted as `@all` by default. Plain typed input is untouched.
- **Rig reachability**: the status bar shows whether the LAN Ollama rig is
  currently reachable, checked on startup and every 60s.
- **Tokyo Night Palette**: Designed to match the Omarchy desktop aesthetic.
- **Lightweight**: Pure terminal TUI running in ~25 MB RAM.

## Installation & Running

The runner script is symlinked to `~/.local/bin/omoduo`.

```bash
# Run directly from any terminal
omoduo

# Or run from source
cd ~/Work/omoduo
./bin/omoduo
```

## Keybindings

| Key | Action |
|---|---|
| `Enter` | Submit prompt from the input field |
| `Ctrl+R` | Open Rant -> Prompt (remote-agent polish pass) |
| `Ctrl+L` | Clear work response panes |
| `Ctrl+X` | Cancel in-flight engine turn |
| `Ctrl+H` | Flag the last remote-agent reply as a hallucination |
| `Esc` / `Ctrl+C` | Quit |

## The remote agent

The "remote" pane and `@remote`/`@duo`/`@all` routes drive
[aider](https://aider.chat) headlessly against a LAN-hosted Ollama server
(`192.168.1.82:11434` by default -- see `omoduo/engine/remote_runner.py`).
Unlike Claude/Antigravity's structured tool-call streams, aider's output is
plain text, so the remote pane shows it close to verbatim -- a genuine
terminal view of what it's doing, not a reformatted summary.

Requires `aider` installed and the LAN rig reachable. If the rig's IP ever
changes, update `OLLAMA_API_BASE`/`OLLAMA_HOST` in `remote_runner.py` and
`polish_runner.py`.

## Rant -> Prompt

`Ctrl+R` opens a scratch box. Type a rough, unstructured idea and press `Ctrl+G`
(or click Generate). The remote agent reads it and returns a few distinct,
cleaned-up prompt options -- pick one (click, or press `1`-`9`) and it's
submitted to `@all` automatically. `Esc` cancels at any point without sending
anything. This never touches Claude or Antigravity credits; it's a
LAN-only draft step.

## Running Tests

```bash
cd ~/Work/omoduo
.venv/bin/pytest -v
```

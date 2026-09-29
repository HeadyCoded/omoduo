"""Shared team-awareness preamble injected into every engine's prompt.

Each engine in the omoduo "team" has a different capability and access
level. Making every engine aware of the others' roles and access matters in
particular because Antigravity runs with --dangerously-skip-permissions
(no confirmation before file edits or shell commands) while Claude and the
remote agent operate with confirm-per-edit or narrower scope -- an engine
building on another's unexplained work should know why files may have
changed without an explicit approval step.
"""

TEAM_PREAMBLE = """\
[Team context -- you are one of three collaborators on this machine]
- Claude Code: confirmation-gated (asks before risky/destructive actions).
  Strongest general judgment of the three, but its subscription access on
  this machine is time-limited and may not be present in later sessions.
- Antigravity (Gemini-backed): runs with --dangerously-skip-permissions --
  it edits files and runs shell commands autonomously, with NO confirmation
  step. If you see files changed that you didn't expect, Antigravity likely
  made that change without asking anyone first -- this is expected behavior
  for it, not a sign something is broken.
- Remote agent (a locally-hosted open-weight model on the LAN, currently
  qwen-noxin-14b): meaningfully weaker judgment than the other two. Good for
  small, well-scoped mechanical tasks; prone to occasionally straying from
  conventions or touching files outside what it was asked to edit. Treat its
  output with more scrutiny than Claude's or Antigravity's, especially on
  multi-file or ambiguous work.

This session exists specifically to exercise and improve the remote agent
ahead of it becoming a long-term teammate to Antigravity, so surface (rather
than silently work around) anything that looks like a hallucination,
invented API, or scope overreach from it.
"""


def build_prompt(contextual_prompt: str) -> str:
    """Prepends the team-awareness preamble to an already-context-built prompt."""
    return f"{TEAM_PREAMBLE}\n{contextual_prompt}"

Model & effort currency — how magician skills should choose models and reasoning effort.

NEVER hardcode a model version in skill output (commit trailers, prompts, docs). Versions go stale. Use tier aliases (`opus`, `sonnet`, `haiku`) which always resolve to the latest of that tier, or describe the capability ("the latest coding-optimal model").

## Current tiers (as of 2026-06; verify, don't trust blindly)

- **opus** — Opus 4.8 (`claude-opus-4-8`). Recommended daily driver in Claude Code. Runs at high effort by default. Best for long autonomous runs, planning, review, orchestration.
- **fable** — Fable 5 (`claude-fable-5`). Best model for coding by a wide margin; available in Claude Code/Cowork. Prefer for heavy implementation and tool-use-intensive work.
- **sonnet** — Sonnet 4.6 (`claude-sonnet-4-6`). Balanced cost/quality for routine subagent work.
- **haiku** — Haiku 4.5 (`claude-haiku-4-5`). Fast/cheap; good for simple, well-scoped subagent tasks.

## Effort (`/effort`)

Scale reasoning effort to the task, don't leave it fixed:
- **low** — mechanical/small (single-file edit, tiny diff, format pass).
- **medium** — normal feature/bugfix work.
- **high** — large changesets, multi-component design, security review (default for Opus).
- **xhigh / max** — the longest, hardest jobs: migrations, whole-repo refactors, deep root-cause hunts. Raise with `/effort xhigh`.

## Currency rule (history/planning/orchestration skills)

When a skill picks a model or spawns subagents, and the session is on an older model than the latest available for the task, **suggest the upgrade** (e.g. "You're on an older model — Opus 4.8 / Fable 5 would handle this better. Switch with `/model`?") and let the user decide. Never switch silently. For spawned subagents, choose the tier that fits the subtask (cheap tier for narrow tasks, top tier for code/review) rather than always inheriting.

Model & effort currency — how magician skills should choose models and reasoning effort.

NEVER hardcode a model version in skill output (commit trailers, prompts, docs). Versions go stale. Use tier aliases (`opus`, `sonnet`, `haiku`) which always resolve to the latest of that tier, or describe the capability ("the latest coding-optimal model").

## Current tiers (as of 2026-07; verify, don't trust blindly)

- **opus** — Opus 4.8 (`claude-opus-4-8`). Recommended daily driver in Claude Code; top tier for hard coding, long autonomous runs, planning, review, orchestration. Runs at high effort by default.
- **fable** — Fable 5 (`claude-fable-5`). Frontier coding model; available in Claude Code/Cowork. Prefer for heavy implementation and tool-use-intensive work.
- **sonnet** — Sonnet 5 (`claude-sonnet-5`). **Claude Code's default since 2.1.197, with a 1M-token context window**; strong at coding/agents. Best balanced tier and the go-to when a task needs a very large context.
- **haiku** — Haiku 4.5 (`claude-haiku-4-5`). Fast/cheap; good for simple, well-scoped subagent tasks.

Tier aliases (`opus`/`sonnet`/`haiku`) resolve to the latest of each tier — prefer them over pinned version ids.

## Effort (`/effort`)

Scale reasoning effort to the task, don't leave it fixed:
- **low** — mechanical/small (single-file edit, tiny diff, format pass).
- **medium** — normal feature/bugfix work.
- **high** — large changesets, multi-component design, security review (default for Opus).
- **xhigh / max** — the longest, hardest jobs: migrations, whole-repo refactors, deep root-cause hunts. Raise with `/effort xhigh`.

## Value profile — models differ in *behavior*, not just capability

Anthropic's research on Claude's values across models & languages found the values a model expresses —
how cautious vs. accommodating, how rigorous vs. warm, how candid about uncertainty, how thorough —
shift by **model version** in ways not deliberately chosen: newer frontier models tend to push back
more, flag risks unprompted, hedge, and go deeper; lighter tiers lean warmer, more deferential, and
briefer. So model choice affects *tone and judgment*, not only correctness:

- **Critique / review / security / debugging** ([divine](../source-skills/divine/SKILL.md), [scrutinize](../source-skills/scrutinize/SKILL.md), [sentinel](../source-skills/sentinel/SKILL.md), [unravel](../source-skills/unravel/SKILL.md)) want the **cautious + candid + thorough** profile — prefer the top tier (`opus`), which leans that way, over a lighter tier that may soften findings.
- **Ideation / design dialogue** ([conjure](../source-skills/conjure/SKILL.md)) tolerates the warmer, briefer profiles.
- **Re-verify posture after a model bump.** A new version can shift these values, so when this file's default changes, re-check that the review/verification skills still push back as hard — don't assume a newer model is a drop-in on *behavior*. **Do NOT hardcode the research's per-version numbers** (they go stale); keep the principle. (Anthropic research: anthropic.com/research/claude-values-models-languages.)

## Currency rule (history/planning/orchestration skills)

When a skill picks a model or spawns subagents, and the session is on an older model than the latest available for the task, **suggest the upgrade** (e.g. "You're on an older model — Opus 4.8 / Fable 5 would handle this better. Switch with `/model`?") and let the user decide. Never switch silently. For spawned subagents, choose the tier that fits the subtask (cheap tier for narrow tasks, top tier for code/review) rather than always inheriting.

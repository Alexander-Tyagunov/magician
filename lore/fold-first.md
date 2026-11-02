Fold-first — the main loop and its skills do the work, and a subagent is the exception. Read this before any skill step that can call `Agent`, `Task` or `Workflow`.

Divide by context, not by problem type. A subagent buys a clean, disposable context. It costs a cold start, a spawn prompt that must carry every input, and a distilled return that drops detail. Pay that cost only when the clean context is the point.

## When a subagent is allowed

Use a subagent for one of these four reasons only:
1. **Parallel independent work.** Two or more tasks share no file and no decision, and each one needs its own context. Example: a wave of `Parallel: YES` plan tasks. Dispatch them together, in one message.
2. **Black-box verification.** The check must not see the author's reasoning. Examples: the `/divine` Phase 3 refutation at Standard depth or deeper, `magician:gatekeeper`, the `verifier` lens.
3. **Fresh-eyes review.** A large diff or a High-tier change, where a lens must not inherit the author's framing.
4. **Measured context bloat.** The context is past 80% (the status line or `/chronicle status`), and the next step reads much more than it keeps. Measure first. Never spawn on a guess.

Everything else runs in the main loop. A task you finish in a handful of tool calls never gets its own agent. Never spawn an agent to re-check work the main loop just did.

## The size threshold

A change is small when it touches 3 files or fewer and 300 changed lines or fewer (added plus deleted). Measure it, do not estimate it:
- A branch or working tree: `git diff --shortstat <base>...HEAD`, or `git diff --shortstat` for uncommitted work.
- A PR or MR: `changedFiles`, `additions` and `deletions` from `gh pr view --json`, or the numbers `glab mr view` shows.
- A diff pasted in the conversation: count its `+++` file headers and its `+` and `-` lines.

A small change runs inline:
- **`/divine` and `/scrutinize`:** run each chosen lens in the main loop. Read `${CLAUDE_PLUGIN_ROOT}/agents/<lens>.md` as a checklist. Use its Review Checklist, its recall rule and its Output Format. Skip its spawn-only sections (Context you receive, Memory). Write down the findings of one lens before you start the next. Make no `Agent` call and no patch file.
- **`/orchestrate` and `/weave`:** a plan or batch whose whole change is small runs task by task with `/ward` in the main loop.

A High-tier change dispatches its lenses fresh at any size ([`lore/review.md`](review.md)): the size rule does not apply to it.

Above the threshold, keep the dispatch the skill describes. That is fork or fresh lenses ([`lore/deep/review.md#fork-or-fresh`](deep/review.md#fork-or-fresh)), waves of agents, or one Workflow. Two or more independent `Parallel: YES` tasks in a wave always fan out.

## Verification in each path

- **Standard depth or deeper:** the adversarial verification stage runs in a fresh agent, also when the lenses ran inline. A High-tier change ([`lore/review.md`](review.md)) always gets Deep and a fresh stage.
- **Quick depth on a small diff:** no agent runs. Phase 3 runs in the main loop: re-read each cited `file:line` and the intent, and drop a finding the code does not confirm. The report states `Verification: in-loop (Quick, small diff)` and offers a Standard re-run for a fresh check.
- **The `verifier` lens and `magician:gatekeeper`** stay fresh whenever they run.

## The handoff when you delegate

Treat a subagent as a tool call with a typed return. Give it the self-contained spawn prompt from [`lore/subagent-context.md`](subagent-context.md) and a bounded return. In a Workflow, that is the `agent()` `schema` (summary ≤ 1200 chars, `files_changed[]`, `obstacles[]`). With `Task`, it is the same fields as text.

Read the return, then decide the next step yourself. A worker never hands work to another worker.

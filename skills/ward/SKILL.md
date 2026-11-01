---
name: ward
description: TDD engine and enforcer — red/green/refactor, one behavior at a time. Use while implementing any feature or bugfix, or to execute a specific blueprint task with TDD.
effort: medium
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *)
argument-hint: "[behavior to implement | task <N>]"
---

# /ward — TDD Engine

Enforce strict red → green → refactor discipline for all implementation work. (This skill absorbed the former `/forge` — general TDD and per-task blueprint execution are one engine.)

## Match the project's conventions (read before you write)

Before implementing, discover and read the repo's own standards — `CLAUDE.md`, any `code-review.md` / `CONTRIBUTING` / `STYLEGUIDE`, and the linter/formatter config — and mirror the patterns already in the files you touch. Conventions a formatter can't enforce (async/await over `.then`, error-wrapping, naming, locale-code format) are still binding — apply them **as you write**, not after a reviewer flags them. See [lore/code-standards.md](../../lore/code-standards.md).

## Effort

Scale `/effort` to task size: low for a one-line fix, medium for normal work, high for a complex multi-behavior task (`xhigh` only for a genuinely hard multi-layer one; `max` is session-only and an opt-in for frontier problems). Across a run: `medium` for implementation turns, `high` for certify/review/security turns; on Bedrock/Vertex/gateways hold one level (an effort change drops the cache there). See [lore/models.md](../../lore/models.md).

The failing test *is* the verification. Don't add a self-review step after green — re-reading your own diff to confirm it is redundant on current models. Let RED → GREEN → REFACTOR and [/certify](../certify/SKILL.md) carry the proof. See [lore/model-behavior.md](../../lore/model-behavior.md).

## Autonomy — approve the plan, then run

Once the spec is settled — the failing test you can write, or the plan task in `.workspace/shared/plans/` — run the remaining phases (RED → GREEN → REFACTOR and the per-task steps) autonomously: don't stop to ask the owner between phases before reading `CLAUDE.md`/standards, searching, `kg query`/`blast`, running the tests, or read-only git (`git status`, diff). This skill pre-approves only reads and read-only searches (Read, Grep, Glob and the embedded `ugrep`/`bfs`/`rg`/`grep`/`find` commands), because TDD edits arbitrary source and no honest path limit exists: `kg` lookups, test runs, and edits go through Claude Code's normal permission prompt unless the user runs in auto mode or approves them. Re-gate only on real side effects — the per-task `git add`/`commit`/`push`. Beyond that, pause only for genuine spec ambiguity (the "cannot write the test first" case below). See [lore/autonomy.md](../../lore/autonomy.md).

## Two modes

- **Freeform** (`/ward <behavior>`): drive TDD for whatever you're implementing now.
- **Task mode** (`/ward task <N>`): execute task N from the current blueprint plan in `.workspace/shared/plans/`. Read the task text from the plan first; if the plan isn't clear from context, ask which plan file or folder. **End your turn and wait** if you must ask. (dispatched with no human present: return NEEDS_CONTEXT instead of waiting).
  - **Plan folder** (`plan.json` next to `plan.md`): read `plan.json` with Read; task N is `steps[N-1]` — its `red` (test, code, run), `green` (sketch, run), `verify`, `files` and the top-level `constraints` are the task text. A step whose `review.status` is `deferred` is not executed this run: say so and stop. If the last line of `plan.md` (`<!-- magician.plan/1 v<n> … -->`) names a version other than `plan.json.version`, say the plan is stale and ask the user to re-run `plan-render all <dir>/plan.json` before continuing.
  - **Single `plan.md`** (legacy): read the `### Task N` block as before.

## The Law

1. **RED** — Write a failing test describing exactly one behavior. Run it and read the output: it must fail **for the reason under test** — your assertion, with a meaningful message, not a compile error, missing import, or typo. A failure for the wrong reason is a false RED → back to RED (fix the test, re-run), never forward to GREEN. If implementation code for this behavior already exists (written before its test), delete it and re-derive it from the test — code the test never drove is unproven.
2. **GREEN** — Write the minimum code to pass. Ugly is fine. Add no untested logic. Re-run the same test; RED→GREEN is proven by the two runs you watched — the real RED output, then GREEN — not by "it should pass" ([lore/verification.md](../../lore/verification.md)).
3. **REFACTOR** — Clean up implementation and tests. No behavior change. All tests stay green.
4. Repeat for the next behavior.

## Vertical tracer bullets

Go end-to-end for one behavior before expanding: first test → first implementation → works → next behavior.

## What counts as one behavior

One function doing one thing · one API endpoint with one response case · one UI component in one state. NOT "the whole auth system".

## Test quality rules

- Test names describe behavior: `test_returns_404_when_user_not_found`
- Test observable behavior, not implementation internals
- No `assertTrue(true)` — always-pass tests are worse than none
- One assertion per concept

## If you cannot write the test first

The spec is incomplete. Do not guess. Ask: "I can't write this test yet — the spec doesn't define what [behavior] should do. Clarify the expected input and output?" **End your turn. Wait for clarification before writing code.** But if you are running as a dispatched subagent with no human present to answer, do not wait — return a BLOCKED or NEEDS_CONTEXT Obstacles block (see below) naming the exact spec gap, and stop.

## Per task (task mode only)

After the behavior(s) for the task are green and refactored:
1. Run the project's **formatter + linter** (the ones CI/review actually use) and type-check — **fix style/lint before committing.** A convention the reviewer or `code-review.md` would flag (e.g. async/await vs `.then`) is a failing gate, not a post-review fixup ([lore/code-standards.md](../../lore/code-standards.md)).
2. Run the full test suite — no regressions. In a plan folder, the step's `verify` commands are the definition of done `/blueprint` wrote from the project's `verify` skill, `REVIEW.md` or the stack lore: run them exactly as written, every one, and treat a command you had to change as a plan defect to report, not a thing to paper over.
3. Commit with a conventional commit message.
4. Mark the task complete in the plan file (`- [ ]` → `- [x]`). In a plan folder, tick the boxes in `plan.md` only; `plan.json` carries no progress and its `version` is not bumped for this. The plan file is the checklist — Task tools (TaskCreate/TodoWrite) are absent on current models unless `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` — and `.workspace/local/session-state.md` is the compaction-proof state: write it before you start a multi-task run and after each task lands.

## Obstacles

If this skill runs as a dispatched unit and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) to the caller alongside whatever you completed; interactively, say the same in prose.

## Completion Signal

- Freeform: "All behaviors covered. Run /certify."
- Task mode: "Task N complete. Next: /ward task N+1, or /certify if all tasks done."

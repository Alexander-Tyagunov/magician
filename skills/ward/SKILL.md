---
name: ward
description: TDD engine and enforcer — red/green/refactor, one behavior at a time. Use while implementing any feature or bugfix, or to execute a specific blueprint task with TDD.
allowed-tools: Read, Edit, Write, Bash
argument-hint: [behavior to implement | task <N>]
---

# /ward — TDD Engine

Enforce strict red → green → refactor discipline for all implementation work. (This skill absorbed the former `/forge` — general TDD and per-task blueprint execution are one engine.)

## Match the project's conventions (read before you write)

Before implementing, discover and read the repo's own standards — `CLAUDE.md`, any `code-review.md` / `CONTRIBUTING` / `STYLEGUIDE`, and the linter/formatter config — and mirror the patterns already in the files you touch. Conventions a formatter can't enforce (async/await over `.then`, error-wrapping, naming, FR-CA vs FR) are still binding — apply them **as you write**, not after a reviewer flags them. See [lore/code-standards.md](../../lore/code-standards.md).

## Effort

Scale `/effort` to task size: low for a one-line fix, medium for normal work, high for a complex multi-behavior task. See [lore/models.md](../../lore/models.md).

## Two modes

- **Freeform** (`/ward <behavior>`): drive TDD for whatever you're implementing now.
- **Task mode** (`/ward task <N>`): execute task N from the current blueprint plan in `.workspace/shared/plans/`. Read the task text from the plan file first; if the plan isn't clear from context, ask which plan file. **End your turn and wait** if you must ask.

## The Law

1. **RED** — Write a failing test describing exactly one behavior. Run it. Confirm it fails with a meaningful message (not a compile error).
2. **GREEN** — Write the minimum code to pass. Ugly is fine. Add no untested logic.
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

The spec is incomplete. Do not guess. Ask: "I can't write this test yet — the spec doesn't define what [behavior] should do. Clarify the expected input and output?" **End your turn. Wait for clarification before writing code.**

## Per task (task mode only)

After the behavior(s) for the task are green and refactored:
1. Run the project's **formatter + linter** (the ones CI/review actually use) and type-check — **fix style/lint before committing.** A convention the reviewer or `code-review.md` would flag (e.g. async/await vs `.then`) is a failing gate, not a post-review fixup ([lore/code-standards.md](../../lore/code-standards.md)).
2. Run the full test suite — no regressions.
3. Commit with a conventional commit message.
4. Mark the task complete in the plan file (`- [ ]` → `- [x]`).

## Completion Signal

- Freeform: "All behaviors covered. Run /certify."
- Task mode: "Task N complete. Next: /ward task N+1, or /certify if all tasks done."

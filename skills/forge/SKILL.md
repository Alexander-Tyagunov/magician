---
name: forge
description: Executes a single blueprint task using TDD — failing test first, then minimum implementation
keep-coding-instructions: true
---

# /forge — Task Execution

Execute one task from a blueprint plan using strict TDD.

## Inputs Required

Ask: which task number from the plan? If no plan exists, suggest /blueprint first.

## Process

1. **Read the task** from the plan file
2. **Write the failing test** exactly as specified
3. **Run the test** — verify it fails with the expected message
4. **Write minimum implementation** to make it pass — nothing more
5. **Run the test** — verify it passes
6. **Run lint and type-check** — fix any issues
7. **Refactor if needed** — no behavior change, tests must stay green
8. **Run full test suite** — no regressions
9. **Commit** with conventional commit message
10. **Mark task complete** in the plan file (change `- [ ]` to `- [x]`)

## Rules

- Never write implementation before the test exists and fails
- Never stack multiple failing tests — one behavior at a time
- Never skip the refactor phase — clean code is part of done
- If a test cannot be written, the task spec is incomplete — raise to user

## Completion Signal

After commit: "Task N complete. Next: /forge task N+1, or /certify if all tasks done."

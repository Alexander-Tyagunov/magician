---
name: ward
description: Enforces TDD discipline — red/green/refactor cycle, one behavior at a time
keep-coding-instructions: true
---

# /ward — TDD Enforcement

Enforce strict red → green → refactor discipline for any implementation work.

## The Law

1. **RED** — Write a failing test that describes exactly one behavior. Run it. Confirm it fails with a meaningful message (not a compile error).
2. **GREEN** — Write the minimum code to make the test pass. Ugly is fine. Do not add untested logic.
3. **REFACTOR** — Clean up implementation and tests. No behavior change. All tests stay green.
4. Repeat for the next behavior.

## Vertical Tracer Bullets

Go end-to-end for one behavior before expanding. First test → first implementation → works. Then add the next behavior.

## What Counts as One Behavior

- One function doing one thing
- One API endpoint with one response case
- One UI component in one state
- NOT: "the whole auth system"

## Test Quality Rules

- Test names describe the behavior: `test_returns_404_when_user_not_found`
- Test observable behavior, not implementation internals
- No `assertTrue(true)` — tests that always pass are worse than no tests
- One assertion per concept (not per line)

## What to do if you cannot write the test first

The spec is incomplete. Do not guess. Ask: "I can't write this test yet — the spec doesn't define what [specific behavior] should do. Can you clarify the expected input and output?"

**End your turn. Wait for their clarification before writing any code.**

## Completion Signal

When all planned behaviors have tests and implementations: "All behaviors covered. Run /certify."

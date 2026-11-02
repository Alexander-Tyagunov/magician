---
name: obstacles-on-missing-input
description: A dispatched implementer whose spawn prompt points at a spec file that does not exist must stop and return STATUS NEEDS_CONTEXT naming the missing input, not guess the rules and build. The prompt has the shape /orchestrate sends. Self-contained; the empty sandbox is the fixture.
tags: [regression, obstacles, dispatch]
runs: 3
max_turns: 8
timeout_seconds: 300
expected_outcome: The final message carries STATUS NEEDS_CONTEXT, names the missing spec and what it needed from it, and no file under src/ was created.
allowed_tools: [Read, Grep, Glob, Skill, Bash, Edit, Write]
---

You are an implementer dispatched by `/orchestrate`. No human watches this run, so nobody can answer a question.

Task 3 of the plan: implement the CSV export of invoices exactly as the spec defines it.

- Spec: `.workspace/shared/specs/2026-10-30-invoice-export.md`. Read it first: it defines the column order, the date format and the rounding rule.
- Files: create `src/billing/export.py`; test in `tests/test_export.py`.
- Use `/ward` for the red/green cycle.

Return (bounded, distilled, never raw logs): STATUS: DONE | BLOCKED | NEEDS_CONTEXT; summary of at most 1200 characters; files_changed: <list>; commit: <sha or none>; obstacles: none, or one block per obstacle.

---
name: blueprint
description: Converts an approved spec into a TDD task plan with explicit parallelism map
keep-coding-instructions: true
---

# /blueprint — Task Planning

Convert an approved spec into an implementation task plan with parallelism analysis.

## Inputs Required

If the spec file path is not clear from context, ask: "Which spec should I plan from? (I'll use the most recent file in `.workspace/shared/specs/` if you don't specify.)"

**End your turn. Wait for their reply (or proceed with most recent if context is unambiguous).**

## Process

1. **Read the spec** — understand all requirements, components, and constraints
2. **Map file structure** — list every file to create/modify with its responsibility
3. **Decompose into tasks** — each task: one component, 2–5 minutes of work, starts with a failing test
4. **Build parallelism map** — mark each task: PARALLEL (no shared files, no dependency) or SEQUENTIAL (depends on task N)
5. **Write the plan** — save to `.workspace/shared/plans/YYYY-MM-DD-<feature>.md`
6. **Present summary** — show task list with parallelism annotations, then ask:

   > "Blueprint ready. Does this task breakdown look right — any tasks to split, merge, or reorder before we lock it in?"

   **End your turn. Wait for explicit approval ("looks good", "approved", "yes", etc.) before closing.**

## Task Format

Each task in the plan:
```
### Task N: <Component Name>
Parallel: YES | NO (depends on Task M)

**Files:**
- Create: `exact/path/file.ts`
- Modify: `exact/path/existing.ts`
- Test: `tests/exact/path/test.ts`

- [ ] Write failing test: <actual test code>
- [ ] Run test: verify FAIL
- [ ] Implement: <actual implementation code>
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: <description>"`
```

## Parallelism Rules

A task is PARALLEL-safe if:
- It does not write to any file another parallel task reads or writes
- It does not depend on types/functions defined in another parallel task
- Integration tasks (wiring components) are always SEQUENTIAL

## After Approval

Say: "Blueprint ready. Run /orchestrate to dispatch parallel agents, or /forge to execute tasks one by one."

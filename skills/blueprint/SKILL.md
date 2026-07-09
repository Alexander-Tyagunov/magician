---
name: blueprint
description: Converts an approved spec into a TDD task plan with a parallelism map (PARALLEL vs SEQUENTIAL), saved to .workspace/shared/plans/. Use after a spec is approved, before implementation.
allowed-tools: Read, Write, Glob
argument-hint: [spec-file-path]
---

# /blueprint — Task Planning

Convert an approved spec into an implementation task plan with parallelism analysis.

## Inputs Required

If the spec file path is not clear from context, ask: "Which spec should I plan from? (I'll use the most recent file in `.workspace/shared/specs/` if you don't specify.)"

**End your turn. Wait for their reply (or proceed with most recent if context is unambiguous).**

## Process

1. **Read the spec** — understand all requirements, components, and constraints. Also read any related research in `.workspace/shared/research/` (from `/magic`) to ground approach and library choices; if a key approach is unresearched, suggest running `/magic` first.
2. **Map file structure** — list every file to create/modify with its responsibility
3. **Decompose into tasks** — each task: one component, 2–5 minutes of work, starts with a failing test
4. **Build parallelism map** — mark each task: PARALLEL (no shared files, no dependency) or SEQUENTIAL (depends on task N)
5. **Write the plan** — save to `.workspace/shared/plans/YYYY-MM-DD-<feature>.md`
6. **Present summary** — show task list with parallelism annotations, then ask:

   > "Blueprint ready. Does this task breakdown look right — any tasks to split, merge, or reorder before we lock it in?"

   **End your turn. Wait for explicit approval ("looks good", "approved", "yes", etc.) before closing.**

## Autonomy — approve the plan, then run

Steps 1–5 run as **one autonomous pass** — read the spec + `.workspace/shared/research/`, map files, decompose, build the parallelism map, and write the plan to `.workspace/shared/plans/`. Reading, searching, `kg query`/`blast`, and read-only git NEVER pause for permission, and neither does writing that plan file. The **only** gate is step 6: presenting the plan for approval. The real downstream side effects — implementation `Write`/`Edit`, `git add`/`commit`/`push`, PR create/merge — are gated later by `/orchestrate` and `/ward`, not here. See [lore/autonomy.md](../../lore/autonomy.md).

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

Say: "Blueprint ready. Run /orchestrate to dispatch parallel agents, or /ward task <N> to execute tasks one by one."

> Model/effort: for large multi-component specs, prefer the latest/code-optimal model and raise /effort to keep the decomposition and parallelism map sharp. See [lore/models.md](../../lore/models.md).

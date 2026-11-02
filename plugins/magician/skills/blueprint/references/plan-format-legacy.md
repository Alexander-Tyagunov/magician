# Legacy plan format — single-file `plan.md`

Use this format only when `plan-render` is not available (Claude chat and Cowork ship no plugin
tools). Write one file, `.workspace/shared/plans/YYYY-MM-DD-<feature>.md`, by hand. `/orchestrate`
and `/ward task <N>` parse it exactly as they always have: `### Task N`, the `Parallel:` line, the
Files list and the five TDD checklist lines.

When `plan-render` is available, never write this file by hand: write `plan.json` instead (see
[plan-schema.md](plan-schema.md)) and let `plan-render md` produce a `plan.md` whose Task blocks
have exactly this shape.

## Global Constraints — inherited by every task

Open the plan with a **Global Constraints** section in the header, before Task 1. Copy each project-wide requirement from the spec **verbatim — one line each**: version floors, dependency limits, naming/copy rules, platform requirements — anything that binds the whole feature rather than a single task. Lift the spec's words; don't paraphrase or re-derive.

Every task **implicitly inherits** this section — say so in the plan, so each dispatched subagent carries the constraints without re-deriving them from the spec:

```
## Global Constraints
_Every task inherits these — do not restate per task._
- <requirement copied verbatim from the spec>
- <requirement copied verbatim from the spec>
```

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

## Header

Before Global Constraints, open with the title, the spec path and a one-line summary:

```
# Plan: <feature title>
Spec: .workspace/shared/specs/YYYY-MM-DD-<feature>.md
<one sentence: what the feature delivers>
```

Then the Global Constraints block, then the tasks in execution order. Number tasks from 1 without
gaps; a task's `Parallel: NO (depends on Task M)` must name a lower-numbered task.

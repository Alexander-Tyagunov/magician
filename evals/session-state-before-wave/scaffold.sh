#!/usr/bin/env bash
# Stages the session-state-before-wave fixture: an empty mathx package and an approved
# two-task plan in the legacy single-file plan.md format.
set -eu
mkdir -p mathx tests .workspace/shared/plans
printf '' > mathx/__init__.py
printf '' > tests/__init__.py
cat > .workspace/shared/plans/2026-11-02-mathx.md <<'MD'
# Plan: mathx clamp and lerp
Spec: .workspace/shared/specs/2026-11-02-mathx.md
Two small numeric helpers for the mathx package.

## Global Constraints
_Every task inherits these — do not restate per task._
- Python 3.10 or later, standard library only.
- Run the tests with `python3 -m unittest -v`.

### Task 1: clamp
Parallel: YES

**Files:**
- Create: `mathx/clamp.py`
- Test: `tests/test_clamp.py`

- [ ] Write failing test: `self.assertEqual(clamp(5, 0, 3), 3)`, `self.assertEqual(clamp(-1, 0, 3), 0)`, and `clamp(1, 3, 0)` raises `ValueError`
- [ ] Run test: verify FAIL
- [ ] Implement: `def clamp(x, lo, hi)` returns `lo` if `x < lo`, `hi` if `x > hi`, else `x`; raises `ValueError` when `lo > hi`
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: clamp"`

### Task 2: lerp
Parallel: YES

**Files:**
- Create: `mathx/lerp.py`
- Test: `tests/test_lerp.py`

- [ ] Write failing test: `self.assertEqual(lerp(0, 10, 0.25), 2.5)` and `self.assertEqual(lerp(4, 8, 1), 8)`
- [ ] Run test: verify FAIL
- [ ] Implement: `def lerp(a, b, t)` returns `a + (b - a) * t`
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: lerp"`
MD
if command -v git >/dev/null 2>&1; then
  git init -q .
  git add -A
  git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add the mathx plan"
fi

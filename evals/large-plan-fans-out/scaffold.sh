#!/usr/bin/env bash
# Stages the large-plan-fans-out fixture: an empty textkit package and an approved six-task plan
# (legacy single-file plan.md format) whose first wave has four independent tasks.
set -eu
mkdir -p textkit tests .workspace/shared/plans
printf '' > textkit/__init__.py
printf '' > tests/__init__.py
cat > .workspace/shared/plans/2026-11-02-textkit.md <<'MD'
# Plan: textkit
Spec: .workspace/shared/specs/2026-11-02-textkit.md
Four independent text utilities, a command line that exposes them, and its usage docs.

## Global Constraints
_Every task inherits these — do not restate per task._
- Python 3.10 or later, standard library only.
- Run the tests with `python3 -m unittest -v`.
- Each module raises `ValueError` with a clear message on invalid input.

### Task 1: Word wrap
Parallel: YES

**Files:**
- Create: `textkit/wrap.py`
- Test: `tests/test_wrap.py`

- [ ] Write failing test: `wrap(text, width)` breaks at spaces so no line is longer than `width`, keeps blank-line paragraph breaks, puts a word longer than `width` on its own line, and raises `ValueError` for `width < 1`
- [ ] Run test: verify FAIL
- [ ] Implement: greedy wrap per paragraph, joined with `\n`, paragraphs joined with `\n\n`
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: word wrap"`

### Task 2: Roman numerals
Parallel: YES

**Files:**
- Create: `textkit/roman.py`
- Test: `tests/test_roman.py`

- [ ] Write failing test: `to_roman(1994) == "MCMXCIV"`, `from_roman("MMXXVI") == 2026`, round trip for 1 to 3999, `ValueError` for 0, 4000 and `"IIII"`
- [ ] Run test: verify FAIL
- [ ] Implement: subtractive table for `to_roman`; `from_roman` parses and re-encodes to reject non-canonical input
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: roman numerals"`

### Task 3: Durations
Parallel: YES

**Files:**
- Create: `textkit/duration.py`
- Test: `tests/test_duration.py`

- [ ] Write failing test: `parse_duration("1h30m") == 5400`, `parse_duration("45s") == 45`, `format_duration(3725) == "1h2m5s"`, `ValueError` for `""`, `"5x"` and `"1m1h"`
- [ ] Run test: verify FAIL
- [ ] Implement: units `h`, `m`, `s` in that order, each at most once
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: durations"`

### Task 4: Slugs
Parallel: YES

**Files:**
- Create: `textkit/slug.py`
- Test: `tests/test_slug.py`

- [ ] Write failing test: `slug("Crème Brûlée!") == "creme-brulee"`, runs of separators collapse to one hyphen, no leading or trailing hyphen, `ValueError` when nothing is left
- [ ] Run test: verify FAIL
- [ ] Implement: `unicodedata.normalize("NFKD")`, drop combining marks, keep `[a-z0-9]`, join with `-`
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: slugs"`

### Task 5: Command line
Parallel: NO (depends on Task 1, Task 2, Task 3, Task 4)

**Files:**
- Create: `textkit/cli.py`
- Test: `tests/test_cli.py`

- [ ] Write failing test: `python3 -m textkit.cli roman 1994` prints `MCMXCIV`; `wrap`, `duration` and `slug` subcommands print their results; a `ValueError` exits 2 with the message on stderr
- [ ] Run test: verify FAIL
- [ ] Implement: `argparse` subcommands that call the four modules
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "feat: textkit command line"`

### Task 6: Usage docs
Parallel: NO (depends on Task 5)

**Files:**
- Create: `README.md`
- Test: `tests/test_readme.py`

- [ ] Write failing test: every subcommand of `textkit.cli` appears in `README.md` with one example
- [ ] Run test: verify FAIL
- [ ] Implement: a usage section with one example per subcommand
- [ ] Run test: verify PASS
- [ ] Commit: `git commit -m "docs: textkit usage"`
MD
if command -v git >/dev/null 2>&1; then
  git init -q .
  git add -A
  git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add the textkit plan"
fi

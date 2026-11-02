---
name: scrutinize-fixes-seeded-bug
description: /scrutinize on an uncommitted change with a seeded off-by-one in page_count must find it, fix it in place and add a regression test that pins the boundary. The scaffold stages a git repo whose working tree holds the change. A lens-ab case.
tags: [regression, review, scrutinize, lens-ab]
runs: 3
max_turns: 40
timeout_seconds: 1200
expected_outcome: pagination.py computes the ceiling of total/size in page_count, and a new test_pagination.py asserts an exact-multiple or zero-items case that the original code fails.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Edit, Write]
---

I added `page_count` to `pagination.py`; the change is uncommitted (`git diff` shows it). Run `/scrutinize` on the working-tree change before I commit it: review it, then fix the Important findings. Put the regression test for any bug you fix in a new `test_pagination.py` (stdlib `unittest`, run with `python3 -m unittest`). Do not commit, and do not open a PR.

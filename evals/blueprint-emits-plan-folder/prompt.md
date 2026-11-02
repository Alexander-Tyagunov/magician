---
name: blueprint-emits-plan-folder
description: Given an approved spec, /blueprint writes one plan.json and renders it with plan-render into plan.md (with the "### Task N:" blocks /orchestrate parses) and plan.html, all in one plan folder under .workspace/shared/plans/. Self-contained; the spec is in the prompt.
tags: [regression, planning, blueprint]
runs: 3
max_turns: 30
timeout_seconds: 900
expected_outcome: The plan folder .workspace/shared/plans/2026-11-02-syncer-dry-run/ holds plan.json, plan.md with "### Task 1:" and the following task blocks, and plan.html, rendered by plan-render.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Write, Edit]
---

The spec below is approved. Turn it into a task plan with `/blueprint --static`, and put the plan folder at `.workspace/shared/plans/2026-11-02-syncer-dry-run/`. I review plans in chat, so do not start a server. I will approve or revise in my next message.

# Spec: `--dry-run` for `syncer`

`syncer` is a small Python command-line tool (`syncer/cli.py`, `syncer/copy.py`, tests in `tests/`, run with `python3 -m unittest`). It copies every file from a `source` folder to a `target` folder and overwrites older files.

Requirements:
1. Add a `--dry-run` flag to `syncer/cli.py`.
2. With `--dry-run`, `syncer` changes no file and creates no folder in `target`.
3. With `--dry-run`, `syncer` prints one line per file it would copy: `would copy <relative path>`.
4. Without `--dry-run`, the behavior does not change.
5. The copy plan (which files to copy) is computed by one function in `syncer/copy.py` that both modes share.

Constraints:
- Python 3.10 or later.
- No new dependencies.

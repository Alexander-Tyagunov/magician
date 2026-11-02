---
name: tdd-red-before-green
description: Asked to add one behavior test-first, the model runs a failing test before it edits the implementation (red before green) and ends with the whole suite passing. The scaffold stages a tiny Python module and its passing test file.
tags: [regression, tdd, ward]
runs: 3
max_turns: 25
timeout_seconds: 600
expected_outcome: A new separator test is written and run red first, then slugify.py is edited, and the last test run shows every test passing.
allowed_tools: [Read, Grep, Glob, Skill, Bash, Edit, Write]
---

This folder has `slugify.py` and its tests in `test_slugify.py`. Run the tests with `python3 -m unittest -v`.

Add one behavior to `slugify`, test-first, with your TDD workflow (`/ward`): a run of spaces, underscores or hyphens becomes a single hyphen, and the result never starts or ends with a hyphen. For example, `slugify("  Hello__World -- 2026 ")` returns `"hello-world-2026"`.

Keep the existing behavior and the existing tests. Do not commit.

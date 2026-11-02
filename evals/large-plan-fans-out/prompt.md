---
name: large-plan-fans-out
description: Fold-first routing, the positive twin of small-diff-stays-inline. /orchestrate on an approved six-task plan whose first wave has four independent, substantial tasks fans that wave out to subagents dispatched together, and starts the dependent tasks only after the wave returns. The scaffold stages a git repo with the plan.
tags: [routing, fold-first, orchestrate]
runs: 3
max_turns: 25
timeout_seconds: 1200
expected_outcome: At least two of Tasks 1 to 4 go to subagents dispatched together in the first wave, and Task 5 starts only after that wave returns.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Edit, Write]
---

The plan `.workspace/shared/plans/2026-11-02-textkit.md` is approved. Run it with `/orchestrate`. You do not need my go-ahead between waves, and do not open a PR.

---
name: session-state-before-wave
description: /orchestrate on an approved two-task plan writes .workspace/local/session-state.md (goal, plan path, wave graph) before its first wave, before any subagent dispatch or implementation edit, so a compaction mid-run loses nothing. The scaffold stages a git repo with the plan.
tags: [regression, orchestrate, compaction]
runs: 3
max_turns: 20
timeout_seconds: 900
expected_outcome: .workspace/local/session-state.md exists, names the plan path and the goal, and was written before the first subagent dispatch and before any file under mathx/ changed.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Edit, Write]
---

The plan `.workspace/shared/plans/2026-11-02-mathx.md` is approved. Run it with `/orchestrate`. You do not need my go-ahead before the first wave, and do not open a PR.

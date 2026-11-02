---
name: plain-question-loads-no-skill
description: Negative control for skill routing. A plain conceptual question gets a plain answer and loads none of the workflow skills (research, planning, TDD, debugging, review, security). The paired positives are security-scan-routes-to-sentinel and code-review-routes-to-review-skill. Self-contained.
tags: [routing, negative-control]
runs: 3
max_turns: 3
timeout_seconds: 120
expected_outcome: A correct answer of at most three sentences (lists are mutable, tuples are not) and no workflow skill invoked.
allowed_tools: [Read, Grep, Glob, Skill]
---

Quick question, no code to change: how does a Python list differ from a tuple? Three sentences at most.

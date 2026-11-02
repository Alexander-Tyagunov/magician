---
name: planning-negative-control
description: Negative control for the planning skills. A one-line typo fix must be done directly, without routing to /manifest, /conjure, /blueprint or /orchestrate. The paired positive is blueprint-emits-plan-folder. The scaffold stages a README with the typo.
tags: [routing, negative-control, planning]
runs: 3
max_turns: 6
timeout_seconds: 180
expected_outcome: README.md reads "receive" instead of "recieve", and no planning or orchestration skill was invoked.
allowed_tools: [Read, Grep, Glob, Skill, Edit]
---

There is a typo in `README.md`: it says "recieve" where it should say "receive". Please fix it.

---
name: unravel
description: Systematic debugging with a mandatory hypothesis preflight — no code changes before evidence; one change at a time, then a regression test. Use for any bug, test failure, or unexpected behavior.
---

# $unravel — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/unravel/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

For reproductions or watchers that remain running, retain the `exec_command` session and poll with `write_stdin`; there is no separate `Monitor` tool. Stop a process only through its session and only when doing so is within the requested diagnostic scope.

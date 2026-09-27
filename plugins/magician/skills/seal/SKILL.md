---
name: seal
description: Ships a feature — simplify pass, certify, commit, PR, CI monitoring, review loop, merge. Use when a feature branch is verified and ready to ship.
---

# $seal — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/seal/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Codex safety overrides take precedence over source mechanics:

- Inspect `git status --short`, `git diff`, and `git diff --cached` before staging. Separate task-owned files from pre-existing or unrelated user changes. Never use `git add -A`, `git add .`, or an equivalent blanket stage; stage only explicitly enumerated task files.
- Show the proposed file list and commit message before committing. If ownership is ambiguous, stop for user direction. A request to ship authorizes the normal source gates, not inclusion of unrelated work.
- Detect the forge from configured remotes and available CLI (`gh` for GitHub, `glab` for GitLab). Do not assume GitHub. If no supported forge/account is confidently identified, complete local verification/commit only and report the limitation.
- Push, PR/MR creation, review posting, merge, deployment, and branch deletion remain separate explicit approval gates. Do not widen a commit approval into network authorization.
- Monitor CI through a running CLI process/session and polling (`exec_command` + `write_stdin`) or the forge's read-only status command. Use recurring automations only when the user explicitly requests scheduling.

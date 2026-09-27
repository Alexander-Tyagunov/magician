---
name: sentinel
description: Security scan — OWASP Top 10, credential/secret detection, injection surfaces, dependency audit, git-history secret scan, auth spot-check. Read-only; produces a severity-ranked report. Use to audit a codebase for vulnerabilities.
---

# $sentinel — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/sentinel/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Keep the scan read-only. If the source requests a Claude context fork or security profile, use a generic self-contained Codex agent when available or perform the lens locally. Write any intermediate report to a temporary directory; create a repository report only when explicitly requested.

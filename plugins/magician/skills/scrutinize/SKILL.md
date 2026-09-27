---
name: scrutinize
description: Multi-agent code review AND remediation — dispatches correctness, security, and simplification reviewers in parallel, consolidates findings, then fixes criticals/highs. Use when reviewing a diff or PR before shipping.
---

# $scrutinize — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/scrutinize/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Dispatch correctness, security, and simplification as generic Codex agents only when collaboration tools are available. Every prompt must be self-contained (Goal, Scope, diff/intent inputs, constraints, evidence, Return format); never request `magician:*` or other Claude profiles. Store intermediate review patches/reports in a temporary directory so the review phase remains read-only. Apply remediation to repository files only after the source remediation gate, and never commit without explicit authorization.

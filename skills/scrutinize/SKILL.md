---
name: scrutinize
description: Multi-agent code review AND remediation — dispatches correctness, security, and simplification reviewers in parallel, consolidates findings, then fixes criticals/highs. Use when reviewing a diff or PR before shipping.
allowed-tools: Bash(git diff:*), Bash(git status:*), Read, Edit, Task
argument-hint: [base-ref, e.g. main]
---

# /scrutinize — Multi-Agent Review & Remediation

Review a code change with three specialist agents in parallel, consolidate findings, then remediate. (This skill absorbed the former `/absorb` — review and fix are one loop.)

## Effort

Scale review depth to the change size: a tiny diff needs little; a large changeset or security-sensitive change warrants `/effort high` (or `xhigh` for sprawling diffs). See [lore/models.md](../../lore/models.md).

## Phase 1 — Review

1. **Collect review scope** — files changed since the branch diverged (base defaults to `main`, or `$ARGUMENTS`):
   ```bash
   git diff main...HEAD --name-only
   git diff main...HEAD
   ```
2. **Dispatch 3 specialist agents simultaneously** — in ONE message, make three `Task` calls using these subagent types (do NOT read agent files by path; the plugin registers them):
   - `magician:reviewer` — correctness and edge cases
   - `magician:sentinel` — security vulnerabilities
   - `magician:simplifier` — over-engineering

   **Context contract (no context loss):** each `Task` prompt MUST be self-contained — the agents see none of this conversation. Include in every prompt: the goal ("review this change for <lens>"), the full list of changed files WITH their diff/contents, the project conventions/lore in play, and the required output format below. See [lore/subagent-context.md](../../lore/subagent-context.md). If an agent returns `NEEDS_CONTEXT`, add the missing input and re-dispatch.

   Each agent returns findings as:
   ```
   SEVERITY: Critical | High | Medium | Low
   FILE: path:line
   ISSUE / VULNERABILITY: <what>
   FIX: <remediation>
   ```
3. **Collect all findings.**
4. **Deduplicate** — collapse the same issue flagged by multiple agents into one (note all sources).
5. **Prioritize** — Critical → High → Medium → Low.
6. **Present consolidated report:**
   ```
   === SCRUTINY REPORT ===
   Critical: N | High: N | Medium: N | Low: N

   [Critical] FILE:LINE — Issue (Source: reviewer/sentinel/simplifier)
   Fix: remediation steps
   ...
   ```
7. Ask: "Fix Critical/High now, or discuss any first?" **End your turn. Wait for the reply before remediating.**

## Phase 2 — Remediate

Triage order: **Critical** (fix immediately), **High** (fix before PR), **Medium** (fix if straightforward, else document), **Low** (note in PR description).

Per finding (Critical and High first):
1. Understand the root cause, not just the symptom.
2. Fix it (direct edit, or `/ward task <N>` if it maps to a plan task — write a failing test first for behavioral fixes).
3. Run the affected test, then the full suite — no regressions.
4. Mark resolved.

**Declining** a finding: allowed only for Low/Medium (convention conflict, readability, documented false positive). Never decline Critical/High without sign-off — ask: "I'm considering declining [finding] because [reason]. Agree, or fix it anyway?" **End your turn. Wait for explicit confirmation.**

## Summary

```
=== SCRUTINY SUMMARY ===
Fixed:    N (list)
Deferred: N (list with rationale)
Declined: N (list with rationale)
```

## Completion Signal

"Scrutinize complete. All critical/high findings resolved. Run /certify to verify clean state."

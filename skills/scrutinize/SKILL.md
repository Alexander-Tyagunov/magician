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

1. **Collect review scope and write the diff once** — files changed since the branch diverged (base defaults to `main`, or `$ARGUMENTS`). Write the diff to a single patch artifact so it isn't duplicated across agent prompts:
   ```bash
   git diff main...HEAD --name-only
   DIFF=".workspace/shared/diffs/review.patch"; [ -d .workspace ] || DIFF="$(git rev-parse --git-dir)/magician-review.patch"
   mkdir -p "$(dirname "$DIFF")"; git diff main...HEAD > "$DIFF"; echo "$DIFF"
   ```
2. **Dispatch 3 specialist agents simultaneously** — in ONE message, make three `Task` calls using these subagent types (do NOT read agent files by path; the plugin registers them):
   - `magician:reviewer` — correctness and edge cases
   - `magician:sentinel` — security vulnerabilities
   - `magician:simplifier` — over-engineering

   **Context contract (no context loss, no re-dump):** each `Task` prompt MUST be self-contained — the agents see none of this conversation. Pass the **patch artifact PATH** from step 1 (each agent `Read`s it) plus the changed-file list, the goal ("review this change for <lens>"), the conventions/lore in play, and the output format below. Do **not** paste the full diff into each prompt — that copies a large payload into the parent's context N times and bloats every agent prompt; pass the path once. See [lore/subagent-context.md](../../lore/subagent-context.md). If an agent returns `NEEDS_CONTEXT`, add the missing input and re-dispatch.

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

**Re-review (evaluator-optimizer loop).** After the Critical/High fixes land, re-dispatch the relevant lens(es) on just the remediated files to confirm the fixes didn't introduce new Critical/High. If they did, remediate and re-review again — loop until a clean pass or 2 rounds (then report what remains). This is what makes review + fix *one loop*, not one pass.

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

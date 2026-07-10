---
name: scrutinize
description: Multi-agent code review AND remediation — dispatches correctness, security, and simplification reviewers in parallel, consolidates findings, then fixes criticals/highs. Use when reviewing a diff or PR before shipping.
allowed-tools: Bash(git diff:*), Bash(git status:*), Read, Edit, Task, AskUserQuestion
argument-hint: [base-ref, e.g. main]
---

# /scrutinize — Multi-Agent Review & Remediation

Review a code change with three specialist agents in parallel, consolidate findings, then remediate. (This skill absorbed the former `/absorb` — review and fix are one loop.)

## Effort

Scale review depth to the change size: a tiny diff needs little; a large changeset or security-sensitive change warrants `/effort high` (or `xhigh` for sprawling diffs). See [lore/models.md](../../lore/models.md).

## Autonomy — approve the plan, then run

Phase 1 runs autonomously: batch the diff write and all three `Task` dispatches in one message; reads, searches, `kg query`/`blast`, and read-only `git diff`/`status` NEVER pause for permission. The **SCRUTINY REPORT** (Phase 1, step 7) is the single approval gate — end your turn there and wait. Once approved, Phase 2 runs the Critical/High fix batch and the re-review loop without gating on intermediate reads, re-gating **only** on real side effects: the fix `Edit`s and the decline-a-finding decision (never decline Critical/High without sign-off). See [lore/autonomy.md](../../lore/autonomy.md).

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
7. **Approval gate (AskUserQuestion).** Present the report, then ask how to proceed via **AskUserQuestion** (never bare prose):
   - **Fix Critical/High now** *(default)* — proceed to Phase 2 remediation.
   - **Discuss first** — talk through findings before any fix.

   **End your turn at the tool call. Wait for the choice before remediating.** Treat a free-form "yes / approved / looks good" as **Fix Critical/High now**.

## Phase 2 — Remediate

Triage order: **Critical** (fix immediately), **High** (fix before PR), **Medium** (fix if straightforward, else document), **Low** (note in PR description).

Per finding (Critical and High first):
1. Understand the root cause, not just the symptom.
2. Fix it (direct edit, or `/ward task <N>` if it maps to a plan task — write a failing test first for behavioral fixes).
3. Run the affected test, then the full suite — no regressions.
4. Mark resolved.

**Re-review (evaluator-optimizer loop).** After the Critical/High fixes land, re-dispatch the relevant lens(es) on just the remediated files to confirm the fixes didn't introduce new Critical/High. If they did, remediate and re-review again — loop until a clean pass or 2 rounds (then report what remains). This is what makes review + fix *one loop*, not one pass.

**Declining** a finding: allowed only for Low/Medium (convention conflict, readability, documented false positive). Never decline Critical/High without sign-off — put the decision to the user via **AskUserQuestion** ("Decline [finding] because [reason]?"):
- **Agree — decline it** — record the rationale and skip the fix.
- **Fix it anyway** — remediate as normal.

**End your turn at the tool call. Wait for explicit confirmation** before declining any Critical/High.

## Summary

```
=== SCRUTINY SUMMARY ===
Fixed:    N (list)
Deferred: N (list with rationale)
Declined: N (list with rationale)
```

## Completion Signal

"Scrutinize complete. All critical/high findings resolved. Run /certify to verify clean state."

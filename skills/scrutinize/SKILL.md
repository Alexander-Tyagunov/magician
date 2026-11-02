---
name: scrutinize
description: Multi-agent review and remediation; correctness, security and simplification lenses, then fixes criticals and highs. Use to review a diff or PR before shipping.
effort: high
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), Task, AskUserQuestion, Bash(kg query *), Bash(kg blast *), Edit(./.workspace/shared/diffs/**)
argument-hint: "[base-ref, e.g. main] [--lens simplifier]"
---

# /scrutinize — Multi-Agent Review & Remediation

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Review a code change with three specialist lenses (inline when small, parallel agents above), consolidate the findings, then remediate in at most three rounds. Review and fix are one loop.

## Completion Signal

"Scrutinize complete. <N Important, N Nit, N Pre-existing; N fixed, N closed with reason>. Run /certify to verify clean state."

## Dialect

The review follows [`lore/review.md`](../../lore/review.md). Every finding carries a tag (`Important`, `Nit`, `Pre-existing`) and `file:line`. Nits are capped. Remediation runs at most three rounds, each after the first on the diff since the last round only, with a round ledger at `.workspace/shared/diffs/<ref>-rounds.md`. The count line is the first line of the report and of the summary. The findings follow it.

If `REVIEW.md` exists at the repository root, Read it first. Its values (what failure means, skip paths, nit cap, round cap, risk tiers) override the defaults, and its text goes into every lens prompt. Remove its skip paths from the diff before the lenses run.

## Effort

Scale effort to the change size. A large or security-sensitive change warrants `/effort high` (`xhigh` for a sprawling diff, `max` only as an opt-in). See [`lore/models.md`](../../lore/models.md).

## Autonomy — approve the plan, then run

Phase 1 runs autonomously. Do not ask before reads, searches, `kg query`/`blast`, or read-only `git diff`/`status`. This skill pre-approves `kg query`/`blast` and the writes under `.workspace/shared/diffs/`. The Phase 2 fix edits go through the normal permission prompt unless the user runs in auto mode.

The **SCRUTINY REPORT** (Phase 1, step 7) is the single approval gate: end your turn there and wait. Once approved, Phase 2 runs the fix rounds without gating on intermediate reads. Re-gate **only** on real side effects: the fix `Edit`s and a decision to close an `Important` finding without a fix. See [`lore/autonomy.md`](../../lore/autonomy.md).

## Phase 1 — Review

1. **Collect the scope and write the diff once.** `<base>` is the first word of `$ARGUMENTS` when given, otherwise `main`. Run each as its own plain command so it matches the pre-approval:
   ```bash
   git diff <base>...HEAD --shortstat
   git diff <base>...HEAD --name-only
   git diff <base>...HEAD > .workspace/shared/diffs/review.patch
   ```
   If `.workspace/` exists but `.workspace/shared/diffs/` does not, create that directory first (the `mkdir` prompts). With no `.workspace/` at all, do not create one. Run `git rev-parse --git-dir` and write the patch to `<git-dir>/magician-review.patch` instead, outside the tracked tree (that write also prompts). Note the patch path. Drop the `REVIEW.md` skip paths from the file list. A small diff (3 files or fewer, 300 changed lines or fewer, by `--shortstat`) needs no patch file.
2. **Small diff: run the lenses inline.** A High-tier change dispatches its lenses fresh at any size. Below the threshold, run each lens in the main loop with `${CLAUDE_PLUGIN_ROOT}/agents/<lens>.md` as its checklist, one lens at a time, and make no lens `Agent` call ([`lore/fold-first.md`](../../lore/fold-first.md)). Its re-review rounds run inline too. The gatekeeper stays fresh.

   **Larger diff: dispatch the lenses in one message.** Fork or fresh follows [`lore/deep/review.md#fork-or-fresh`](../../lore/deep/review.md#fork-or-fresh). When the diff is already in context (about 40k tokens or less), each lens is a fork (`subagent_type: "fork"`). The fork prompt names the lens and tells it to Read `${CLAUDE_PLUGIN_ROOT}/agents/<lens>.md`. Otherwise use these fresh subagent types, which the plugin registers:
   - `magician:reviewer`: correctness and edge cases
   - `magician:sentinel`: security (OWASP, secrets, injection into app code)
   - `magician:simplifier`: over-engineering
   - `magician:guardian`: add this lens when the diff touches the agentic surface (agents, hooks, tools, skills, prompts, untrusted input)

   With `--lens <name>` in `$ARGUMENTS`, dispatch only that lens (the project `simplify` skill calls `/scrutinize --lens simplifier`).

   **Context contract:** each `Task` prompt is self-contained, because the agents see none of this conversation. Pass the patch **path** from step 1 and the changed-file list, never the pasted diff. Add the goal ("review this change for <lens>"), the conventions and lore in play, the `REVIEW.md` text, the ledger path on a re-review, and the output format below ([`lore/subagent-context.md`](../../lore/subagent-context.md)). On `NEEDS_CONTEXT`, add the missing input and re-dispatch.

   Each agent returns findings as:
   ```
   SEVERITY: Critical | High | Medium | Low
   TAG: Important | Nit | Pre-existing
   FILE: path:line
   ISSUE / VULNERABILITY: <what>
   FIX: <remediation>
   ```
   **Finders optimize for recall. Consolidation optimizes for precision.** Never tell a lens to be conservative, to skip nits, or to report only high severity. Models follow that literally and withhold bugs. Ask for full coverage with confidence and severity attached, then filter in steps 4 and 5.

3. **Collect all findings.**
4. **Deduplicate.** Merge the same issue from several lenses into one (note all sources). Drop findings the code refutes and findings without `file:line`.
5. **Prioritize.** Critical, then High, Medium, Low. Keep at most the nit cap (default 5) and note how many nits you withheld.
6. **Present the consolidated report:**
   ```
   === SCRUTINY REPORT ===
   N Important, N Nit, N Pre-existing; 0 fixed, 0 closed with reason.
   Critical: N | High: N | Medium: N | Low: N

   [Critical] Important FILE:LINE — Issue (Source: reviewer/sentinel/simplifier)
   Fix: remediation steps
   ...
   ```
7. **Approval gate (AskUserQuestion).** Present the report, then ask how to proceed through **AskUserQuestion** (never bare prose):
   - **Fix Important findings now** (default): proceed to Phase 2.
   - **Discuss first**: talk through the findings before any fix.

   **End your turn at the tool call. Wait for the choice before you remediate.** Treat a free-form "yes / approved / looks good" as **Fix Important findings now**. When the request itself already says to fix (for example "review it, then fix the Important findings"), that is the answer: show the report and go on to Phase 2 without asking.

## Phase 2 — Remediate, in rounds

Triage order: **Critical** (fix now), **High** (fix before the PR), **Medium** (fix if simple, else document), **Low** and **Nit** (note in the PR description). A `Pre-existing` finding is reported, not fixed, unless the user asks.

**Round ledger.** Before the first fix, write `.workspace/shared/diffs/<ref>-rounds.md` in the format of [`lore/deep/review.md#round-ledger`](../../lore/deep/review.md#round-ledger). It holds one row per finding with tag, severity, location, status `open`, and the head SHA. Update the rows as you go.

Per finding (Critical and High first):
1. Understand the root cause, not just the symptom.
2. Fix it (a direct edit, or `/ward task <N>` when it maps to a plan task). Write a failing test first for a behavioral fix.
3. Run the affected test, then the full suite. No regressions.
4. Mark the row `fixed`.

**Parallel fixes.** For two or more independent `Important` findings in disjoint files on a committed branch, dispatch `magician:fixer` per finding with `isolation: "worktree"` on the call. The pattern is in [`lore/deep/review.md#fixer-worktree`](../../lore/deep/review.md#fixer-worktree). Each fixer returns `BRANCH: fix/<finding-id>`. Merge or cherry-pick each branch into the review branch. A single fix, or a chain of dependent fixes, runs in place.

The fixer edits **source only**, never tests, evals or gates, and escalates on ambiguity. **Reviewer ≠ author:** never let a fixer's own patch ship unreviewed.

**Re-review (evaluator-optimizer loop).** After the fixes land, re-dispatch the relevant lenses on the diff since the ledger's last head SHA only. Put the ledger path in every prompt, so no finding fixed or closed in an earlier round is repeated. If the diff introduced a new `Important` finding, fix it and re-review again. Stop at a clean pass or after round 3, and then report what remains. Append each round's table and count line to the ledger.

**Close without a fix.** A `Nit` or a `Pre-existing` finding closes on your own judgment with a one-line reason (convention conflict, readability, documented false positive). An `Important` finding never closes without sign-off. Put the decision to the user through **AskUserQuestion** ("Close [finding] because [reason]?"):
- **Agree, close it**: record the reason in the ledger and skip the fix.
- **Fix it anyway**: remediate as normal.

**End your turn at the tool call. Wait for explicit confirmation** before you close any `Important` finding.

## Final gate (gatekeeper)

Before you declare the change shippable, dispatch `magician:gatekeeper` to grade the **end state**: GO, NO-GO or UNVERIFIED. It runs the repository's gates and grades them against the change's goal. A check it could not run is **UNVERIFIED**, never GO. Resolve any NO-GO before the hand-off to `/certify` or `/seal`.

## Summary

```
=== SCRUTINY SUMMARY ===
N Important, N Nit, N Pre-existing; N fixed, N closed with reason.
Rounds:   N of 3
Fixed:    N (list)
Deferred: N (list with rationale)
Closed:   N (list with rationale)
```

## Circulate the report (optional)

You can offer to publish the SCRUTINY REPORT as a Claude Code **Artifact** (a live page on claude.ai). Never create it unprompted. A **public** link is an outward sharing action: **confirm it, keep the page account-private by default, and never expose proprietary code, secrets, or unremediated findings.**

## Obstacles

**As a consumer:** every dispatched lens returns an Obstacles block on a non-clean run. Roll them up into one report kept distinct from the deliverables (never let a blocked unit read as done). Detect a pattern by a normalized BLOCKER + SCOPE signature. Memorize a confirmed pattern with `ctx learn --add "<signature -> workaround / next-action>"` written from your own signature: never verbatim worker text, never secrets or PII. A lens `NEXT` field that proposes a lint rule or a `CLAUDE.md` line (a finding class that recurred twice) goes to the user as a suggestion. Full consumer protocol: [`lore/obstacles.md`](../../lore/obstacles.md).

**As a producer:** when this skill runs as a dispatched unit and something blocks or degrades the work, do not wait for a human. Nobody is there. Do not silently ship a degraded result. Return the Obstacles block from [`lore/obstacles.md`](../../lore/obstacles.md) with whatever you completed. The fields are STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT. Interactively, say the same in prose.

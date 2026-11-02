---
name: divine
description: Research-grounded multi-lens code review of a change, PR or MR, severity-ranked. Use to review or audit a changeset; not for remediation (/scrutinize).
effort: high
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), Bash(mkdir -p .workspace/local), Bash(touch .workspace/local/security-scan.active), Task, AskUserQuestion, mcp__context7__resolve-library-id, mcp__context7__query-docs, Bash(gh pr view *), Bash(gh pr diff *), Bash(gh pr checks *), Bash(gh pr list *), Bash(glab mr view *), Bash(glab mr diff *), Bash(glab mr list *), Bash(glab ci status *), Bash(git merge-base *), Bash(kg check), Bash(kg query *), Bash(kg blast *), Bash(kg neighbors *), Edit(./.workspace/shared/diffs/**), Edit(~/.claude/plugins/data/magician-*/divine-monitor.json)
argument-hint: "[PR/MR URL · branch · \"working tree\" · monitor <repo>]"
---

# /divine — Deep Code Review

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Review a change for correctness, security, simplification and test quality, grounded in its intent and in external truth. Rank by severity, tag each finding, give a fix. This is the on-demand, PR/MR-aware reviewer. `/scrutinize` reviews the branch diff mid-flow and remediates. `/divine` reports, and fixes only on request.

## Completion Signal

Remove the scan marker (`rm -f .workspace/local/security-scan.active`), then close with the quoted signal:
> "Divine complete. <N Important, N Nit, N Pre-existing; N fixed, N closed with reason>. Fix in-repo with /scrutinize or /ward task <N>; verify with /certify, then /seal."

## When to use

Trigger phrases: "do a code review", "review this PR/MR", "review my changes/diff/branch", "audit this MR". Not for the review that remediates (`/scrutinize`) or a security-only scan (`/sentinel`). `/transmute` invokes `/divine` as its G7 gateway, checked against `.workspace/shared/research/<feature>-parity.md`.

On review intent, magician's `UserPromptSubmit` hook notes that this skill covers code review. Then announce:
> "Auto-activating /divine for a structured code review. I will establish the change context, then confirm how deep to go."

## Dialect

The review speaks the dialect in [`lore/review.md`](../../lore/review.md). Every finding has a tag (`Important`, `Nit`, `Pre-existing`) and `file:line`. Nits are capped. Remediation runs at most three rounds, diff-only after the first, with a round ledger. The count line comes first, then the findings.

If `REVIEW.md` exists at the repository root, Read it first. Its values override the defaults, and its text goes into every lens prompt. Platform alternatives (`/code-review`, `claude ultrareview --trust-workspace`, the `@claude review` GitHub flow) are in [`lore/deep/review.md#platform-surfaces`](../../lore/deep/review.md#platform-surfaces). Recommend one when it fits better.

## Phase 0 — Change context

**Monitor mode:** `/loop 1h /divine monitor <owner/repo>` reviews new PRs/MRs unattended and never implements fixes. If `$ARGUMENTS` starts with `monitor`, skip the interactive phases and follow [`references/monitor-mode.md`](references/monitor-mode.md).

Read [`references/change-context.md`](references/change-context.md). Resolve the target from `$ARGUMENTS` (a PR/MR URL, a branch, or "working tree"). Gather the diff and changed files, the base ref, the PR/MR description and tickets, CI status, and in-repo grounding. Drop the `REVIEW.md` skip paths. Summarize the change and its scale in two sentences, silently.

## Phase 1 — Depth gate

<HARD-GATE>
Ask how deep the review goes with `AskUserQuestion`, never in prose. Skip the gate only when the user named a depth ("quick review", "deep review of …").
</HARD-GATE>

Four depths: **Quick**, **Standard** (default), **Deep**, **Exhaustive**. The matrix (lenses, `/effort`, grounding, verification) is in [`references/depth-and-research.md`](references/depth-and-research.md). A High-tier change per `REVIEW.md` gets Deep at least. At Deep or Exhaustive, or on unfamiliar ground, invoke `/magic` first for external truth. Prefer the latest coding model. Suggest an upgrade, do not switch silently ([`lore/models.md`](../../lore/models.md)).

## Autonomy

After the depth gate, run to completion without more questions: context reads, `kg` blast radius, lens dispatch, verification, the report. Re-gate only on side effects: a post to the PR/MR (Phase 5) and, on request, edits, commits and pushes (Phase 6). Web fetches show Claude Code's normal prompt. Doctrine: [`lore/autonomy.md`](../../lore/autonomy.md).

## Phase 2 — Multi-lens review

First run `mkdir -p .workspace/local && touch .workspace/local/security-scan.active`. While the marker exists, the PreModelSwitch hook holds a model switch for confirmation. Remove it in the Completion Signal and on any early exit.

Lenses: `magician:reviewer` (correctness), `magician:sentinel` (security, supply chain), `magician:simplifier` (over-engineering), `magician:verifier` (tests, Deep and Exhaustive, always fresh). Pick the path by the measured diff size ([`lore/fold-first.md`](../../lore/fold-first.md)):
- **Small** (3 files or fewer, 300 changed lines or fewer): run each lens but the verifier in the main loop, with `agents/<lens>.md` as its checklist. Quick depth here makes no `Agent` call. A High-tier change dispatches its lenses fresh at any size.
- **Larger:** write the diff once to `.workspace/shared/diffs/<ref>.patch`, then dispatch the lenses in parallel, in one message. Fork or fresh follows [`lore/deep/review.md#fork-or-fresh`](../../lore/deep/review.md#fork-or-fresh).

Each spawn prompt is self-contained (goal, patch path, intent, grounding, `REVIEW.md` text, ledger path, return format). Templates in [`references/dispatch.md`](references/dispatch.md), contract in [`lore/subagent-context.md`](../../lore/subagent-context.md). On `NEEDS_CONTEXT`, add the input and re-dispatch.

Finders optimize for recall. Never tell a lens to be conservative or to skip nits. Phase 3 removes the noise, and it can only remove what the finders surfaced.

## Phase 3 — Adversarial verification

Try to refute every Critical and High finding against the code and the intent, in a fresh context, never in a fork. At Exhaustive, use independent votes. At Quick on a small diff, run this check in the main loop and state `Verification: in-loop` in the report. Keep the survivors, list the rest as dropped. Details in [`references/depth-and-research.md`](references/depth-and-research.md#adversarial-verification).

## Phase 4 — Report

Deduplicate, rank, tag, and present in the format of [`references/report-format.md`](references/report-format.md). Order: the count line, the Overall verdict, merge gates, then Critical, High, Medium, Low, then the dropped candidates. Each finding has `file:line`, impact, fix, tag and traceability.

## Phase 5 — Deliver and post

Present the report in chat. For a real PR/MR, offer to post:

<HARD-GATE>
A post publishes on the user's behalf. Confirm through `AskUserQuestion`, show the exact text, and check the GitHub/GitLab account before any `gh` or `glab` write. Never post without a clear yes.
</HARD-GATE>

Commands and inline-comment format: [`references/report-format.md`](references/report-format.md#posting-to-the-pr).

## Phase 6 — Fixes on request

Offer fixes through `AskUserQuestion`. The default is "just report". The round flow, the ledger, and the commit and push gate are in [`references/remediation.md`](references/remediation.md).

## Obstacles

As a consumer, roll the lenses' Obstacles blocks into one report, separate from the findings. Memorize a confirmed pattern with `ctx learn --add "<signature -> workaround>"` in your own words, never secrets or PII. As a producer, on a non-clean run return the Obstacles block from [`lore/obstacles.md`](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) with what you completed.

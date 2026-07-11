---
name: divine
description: Thorough, research-grounded code review of a change, PR, or MR — multi-lens (correctness, security, simplification, tests), severity-ranked with impact + fix, configurable depth, optional PR comments. Use when asked to review code, "do a code review", "review this PR/MR", "review my changes/diff/branch", or audit a changeset before merge.
allowed-tools: Read, Grep, Glob, Bash, Monitor, Task, AskUserQuestion, WebSearch, WebFetch, mcp__context7__resolve-library-id, mcp__context7__query-docs
argument-hint: [PR/MR URL · branch · "working tree" · monitor <repo>]
---

# /divine — Deep Code Review

Perceive what's hidden in a change: correctness, security, simplification, and test quality — grounded in the change's actual intent and external truth, ranked by severity, with a concrete fix for each finding.

This is the **on-demand, PR/MR-aware** reviewer. Its pipeline-internal counterpart is `/scrutinize` (which reviews the branch diff vs base mid-flow and also remediates Critical/High). `/divine` adds: change-context detection (GitHub PR / GitLab MR / branch / working tree), a depth gate, optional `/magic` grounding, adversarial verification, and optional posting back to the PR — and it reports rather than auto-fixing.

`/transmute` invokes `/divine` as its **G7 sanity gateway** — a blast-radius review (`kg blast`) of a ported or in-place-integrated change; when reviewing such a change, check it against the parity contract in `.workspace/shared/research/<feature>-parity.md` (behavior/UX must be preserved).

## Auto-invocation

The `UserPromptSubmit` hook injects a strong activation hint on review intent ("review this PR/MR", "do a code review", "audit/evaluate this MR", "review my changes/diff"). When it fires — or you otherwise pick up review intent — announce:
> "Auto-activating /divine for a structured code review. Let me establish the change context, then confirm how deep to go."

## Phase 0 — Establish change context

**Monitor mode:** if `$ARGUMENTS` starts with `monitor` (typically launched by `/loop`), skip the interactive phases and follow [references/monitor-mode.md](references/monitor-mode.md).

Before anything, know exactly **what changed and why**. Read [references/change-context.md](references/change-context.md) and resolve the target from `$ARGUMENTS` (a PR/MR URL, a branch, or "working tree"). Gather: the diff + changed-file list, the base ref, the PR/MR **description and linked tickets** (intent), CI / merge-gate status, and any in-repo grounding (`.workspace/shared/specs|research/`, design docs). Summarize the change in 1–2 sentences and the scale (files / +adds / −dels) before proceeding. Do this silently, then move to Phase 1.

## Phase 1 — Depth & grounding (AskUserQuestion)

<HARD-GATE>
Ask the user how extensive the review should be using the **AskUserQuestion** tool — never in prose. Skip the gate ONLY if the user already named a depth ("quick review", "deep review of …").
</HARD-GATE>

Offer the four depth levels (full matrix — lenses, effort, grounding, verification — in [references/depth-and-research.md](references/depth-and-research.md)):

- **Quick** — a simple logic change / fast sanity pass; correctness lens, `/effort` low–medium, no grounding or pointers needed.
- **Standard** *(default)* — 3 lenses (correctness, security, simplification), `/effort` medium, light grounding from PR/specs.
- **Deep** — 4 lenses (+ tests), `/effort` high, `/magic` grounding (PRDs/docs/external + internal data) on unfamiliar domain/libraries, **blast-radius analysis** (affected services & infrastructure), adversarial verification, CI/merge-gate + requirement traceability.
- **Exhaustive** — Deep + loop-until-dry finders, multi-vote verification, full PRD/requirement traceability, deep blast-radius across affected services & infrastructure, supply-chain deep dive, and agent-teams / dynamic-workflows for very large PRs. `/effort` xhigh.

**Grounding (Deep/Exhaustive, or any change in unfamiliar territory):** if the change relies on a framework, protocol, domain, or library you can't review from first principles — or there's a PRD/spec/story to check it against — invoke **`/magic`** first to gather that evidence (it saves to `.workspace/shared/research/` and hands the artifact back). The strongest reviews are checked against external truth, not vibes. See [references/depth-and-research.md](references/depth-and-research.md).

Confirm model/effort per the chosen depth — prefer the latest code-optimal model and raise `/effort`; suggest an upgrade rather than switching silently if the session is on an older model ([lore/models.md](../../lore/models.md)).

## Autonomy — approve the plan, then run

Once the **depth & grounding** gate (Phase 1) is answered, run the review to completion **autonomously**: change-context reads (Phase 0), `kg query`/`blast` blast-radius, the parallel reviewer subagents (Phase 2), adversarial verification (Phase 3), and the consolidated report (Phase 4) — reading, searching, and read-only git NEVER pause for permission. Re-gate **only** on this skill's real side effects: posting the review to a PR/MR (Phase 5, `gh`/`glab` write) and, if fixes are implemented (Phase 6), `Write`/`Edit`, `git add`/`commit`/`push`, and PR create. Doctrine: [lore/autonomy.md](../../lore/autonomy.md).

## Phase 2 — Multi-lens review

Dispatch the specialist agents **in parallel** (one message, multiple `Task` calls), scaled to the chosen depth, using these subagent types — do NOT read agent files by path:
- `magician:reviewer` — correctness, logic, edge cases
- `magician:sentinel` — security & supply-chain (deps/lockfile changes get the supply-chain check)
- `magician:simplifier` — over-engineering, premature abstraction
- `magician:verifier` — test quality, coverage, meaningful assertions (Deep/Exhaustive)

**Context contract (no context loss):** each `Task` prompt MUST be self-contained — agents see none of this conversation. Include the goal, the changed files WITH diff/contents, the change intent + any grounding artifact path, project conventions, and the exact return format. Full per-lens prompts in [references/dispatch.md](references/dispatch.md) and the contract in [lore/subagent-context.md](../../lore/subagent-context.md). If an agent returns `NEEDS_CONTEXT`, add the missing input and re-dispatch.

## Phase 3 — Adversarial verification

Before reporting, **try to refute** every Critical/High finding (and, at Exhaustive depth, with multiple independent votes). A finding survives only if it holds up against the actual code and the change's intent. Drop the rest and list them as verified false-positives. This is what separates a trustworthy review from a noisy one. See [references/depth-and-research.md](references/depth-and-research.md#adversarial-verification).

## Phase 4 — Consolidated report

Deduplicate across lenses, rank by severity, and present the report in the format in [references/report-format.md](references/report-format.md): an **Overall** verdict, **🔴 Merge gates / CI**, then 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low, each with `file:line`, **impact**, **fix**, and **traceability** to the requirement/DoD it affects when one exists — plus a **✅ Dropped (false positives)** section from Phase 3.

## Phase 5 — Deliver & (optionally) post

Present the report in-chat. Then, only if the target is a real PR/MR, offer to post it:

<HARD-GATE>
Posting to a PR/MR (review body or inline comments) publishes content on the user's behalf. Ask for explicit confirmation via AskUserQuestion, show exactly what will be posted, and confirm the GitHub/GitLab account is correct, before any `gh`/`glab` write. Never post without a clear yes.
</HARD-GATE>

Posting commands and the inline-comment format are in [references/report-format.md](references/report-format.md#posting-to-the-pr).

## Phase 6 — Optional: implement the fixes

The report is the deliverable; acting on it is the user's call. After delivering, **offer** (via AskUserQuestion) to go further — never assume:
- **Just report** *(default)* — leave the fixes to the author.
- **Implement Critical/High fixes here** — spin an agent to fix them, with tests, in this repo.
- **Implement, then commit (and push)** — as above, then commit; push only on a second confirmation.

If the user opts to implement:
1. Scope strictly to the **confirmed Critical/High** findings. Dispatch an implementer per finding (or run the `/scrutinize` remediate loop) — a failing test first for behavioral fixes (see `/ward`). Each task is self-contained (the finding's `file:line`, root cause, intended behavior) per [lore/subagent-context.md](../../lore/subagent-context.md).
2. Run the affected tests, then the full suite — no regressions.
3. <HARD-GATE> Committing and pushing are side effects. Show the diff and the proposed commit message, confirm via AskUserQuestion, and verify the **branch + correct account** before any `git commit`/`git push`. Prefer a feature branch; never push to a protected/default branch without explicit instruction. </HARD-GATE>
4. Report what changed and where (commit SHA / pushed branch / opened PR URL).

For a PR/MR you don't own locally, prefer leaving inline review comments (Phase 5) over pushing to someone else's branch unless the user explicitly asks for the fixes to be pushed.

## Monitor mode (unattended, via /loop)

Run /divine on a schedule to watch repos for new PRs/MRs and review them automatically:
> `/loop 1h review open PRs in <owner/repo> at standard depth and post the review`
> or: `/loop 1h /divine monitor <owner/repo>`
> or **omit the interval** (`/loop review open PRs in <owner/repo> …`) to **self-pace** — Claude widens the gap on quiet repos and tightens it on active ones (fixed-interval on Bedrock/Vertex).

To react the moment a PR opens or gets new commits (instead of waiting for the next tick), prefer the **Monitor tool** over clock polling — see [references/monitor-mode.md](references/monitor-mode.md).

Unattended runs have no one to answer gates, so depth and post-policy are **pre-set** when the loop starts, the run is **idempotent** (reviews a PR/MR only when its head SHA hasn't been reviewed yet), and it **never implements or pushes fixes** — review (and optional review comments) only. Full flow in [references/monitor-mode.md](references/monitor-mode.md).

## Completion Signal

Close with the quoted signal, then route:
> "Divine complete. <N critical · N high · N medium · N low>. Fix in-repo with /scrutinize or /ward task <N>; verify with /certify, then /seal."

- Findings to fix in this repo → `/scrutinize` (review+remediate loop) or `/ward task <N>` for test-first fixes.
- Need deeper domain grounding mid-review → `/magic`.
- Ready to ship after fixes → `/certify` then `/seal`.

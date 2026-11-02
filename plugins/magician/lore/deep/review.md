# review — deep dive

> On-demand companion to `lore/review.md`. **Do not read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Review dialect](#dialect) · [Round ledger](#round-ledger) · [Fork or fresh](#fork-or-fresh) · [`REVIEW.md`](#review-md) · [Reviewer memory](#reviewer-memory) · [Parallel fixes in worktrees](#fixer-worktree) · [Platform surfaces](#platform-surfaces)

## Review dialect <a id="dialect"></a>

This is the dialect Anthropic describes for Claude Code's own review pipeline. `/divine` and `/scrutinize` speak it, and every lens agent returns it.

**Tags.** Every finding carries one tag next to its severity:

- `Important`: a defect in this change that must be fixed or closed with a reason before merge.
- `Nit`: a style, naming or micro-cleanup point. A nit never blocks a merge.
- `Pre-existing`: a real problem in code the change did not touch. Report it once and do not count it against the author. Do not fix it in this round unless the user asks.

Severity (Critical, High, Medium, Low) says how bad the defect is. The tag says what the author must do with it. A Critical finding is always `Important`. A `Nit` is Low by definition.

**Evidence.** Every finding names `file:line` and states the impact. A finding without a location is a hunch, not a finding, and the consolidation step drops it.

**Nit cap.** A review reports at most the number of nits `REVIEW.md` allows (default 5). Keep the nits with the most value, and say "N more nits withheld" in the summary.

**Count-first summary.** The count line is the first line of the report summary. The findings follow it:

```
3 Important, 5 Nit, 2 Pre-existing; 3 fixed, 0 closed with reason.
```

The second half appears after remediation. Every `Important` finding ends as "fixed" or as "closed with reason", never as silence.

**Risk tiers by change, not author.** The tier comes from what the diff touches, never from who wrote it. Low: tests, docs, comments, a leaf function. Medium: application logic, a public interface, a dependency bump. High: auth, payments, data migrations, CI workflow files, secrets handling, anything with a wide blast radius.

A High-tier change gets the Deep depth and a fresh verification stage. `REVIEW.md` can redefine the tiers for a repository.

**Three rounds, diff-only.** Remediation runs at most three rounds. Round 1 reviews the whole change. Round 2 and round 3 review only the diff since the previous round. They read the round ledger first and never repeat a finding that an earlier round fixed or closed. After round 3, report what remains and stop, do not loop until clean.

## Round ledger <a id="round-ledger"></a>

The ledger is the memory between rounds. It lives next to the patch artifact at `.workspace/shared/diffs/<ref>-rounds.md`, where `<ref>` is the patch name (`pr-42`, `review`, a branch name). The skill that runs the rounds writes it. A lens agent reads it only when the spawn prompt names the path.

```markdown
# Review rounds — <ref>

## Round 1 — <date> — <base sha>..<head sha>
| # | Tag | Severity | Location | Finding | Status | Reason |
|---|---|---|---|---|---|---|
| 1 | Important | High | src/auth.ts:42 | token compared with == | fixed | — |
| 2 | Nit | Low | src/auth.ts:60 | rename `tmp` | closed | style call, author declined |
| 3 | Pre-existing | Medium | src/db.ts:12 | pool never closed | deferred | not in this change |
Summary: 1 Important, 1 Nit, 1 Pre-existing; 1 fixed, 1 closed with reason.

## Round 2 — <date> — <head sha of round 1>..<new head sha>
(only findings in the diff since round 1; carry forward nothing that is fixed or closed)
```

Rules:

- Status is one of `open`, `fixed`, `closed`, `deferred`. A closed row always has a reason.
- A new round starts with the ledger read, and its spawn prompts name the ledger path and the diff range.
- A finding that matches an earlier row by location and class is a repeat. Drop it unless the fix regressed.
- The ledger is a workspace artifact, so it follows the workspace mode: shared and committed, or private and ignored.

## Fork or fresh <a id="fork-or-fresh"></a>

A fork subagent (`subagent_type: "fork"` on the Agent call) inherits the whole conversation, the parent's tools, model and prompt cache. A fresh subagent (`magician:reviewer` and the other lens types) starts from its definition file with only the spawn prompt. Pick by this rule, once, for the whole review:

- **Below the fold-first threshold, dispatch no lens at all.** A diff of 3 files or fewer and 300 changed lines or fewer runs each lens in the main loop, with `agents/<lens>.md` read as a checklist ([`lore/fold-first.md`](../fold-first.md)). The fork and fresh rules below apply above that threshold.
- **Fork the lenses when the diff is already in context** and is small (about 40k tokens or less). Three forks over the same diff do not re-read the repository, and their first request reuses the parent's cache. A fork does not load the agent definition. So the fork prompt must name the lens and tell it to Read `../../skills/<lens>-lens/SKILL.md` for its checklist and output format. A fork runs on the main session's model, and it has no `memory:` of its own.
- **Dispatch fresh agents otherwise:** the diff is large, the diff is not in context (the patch artifact is), or the lens must not inherit the author's framing. Fresh lenses carry their own model, effort and memory.
- **The verification stage is always fresh.** Adversarial verification and the verifier lens refute the findings against the code. A fork carries the author's bias into that stage, so it never runs as a fork. `lore/verification.md` demands fresh evidence for the same reason. The one exception is a Quick review of a small diff: it verifies in the main loop and states `Verification: in-loop` in the report.
- If `Agent(fork)` is denied in the permission settings, or fork mode is off (`CLAUDE_CODE_FORK_SUBAGENT=0`), dispatch fresh agents and say so in the report.

## REVIEW.md <a id="review-md"></a>

`REVIEW.md` at the repository root is the code owners' review contract. It holds what failure means in this repository, plus the nit cap, skip paths, evidence rule, summary line, risk tiers, tags, and round cap. `/almanac` scaffolds it from `skills/divine/references/review-md-template.md`, and the owners edit it.

When the file is present, read it before any dispatch and pass its rules into every lens prompt. Its values override the defaults in this file. Skip paths are excluded from the diff before review, and the report says which paths it skipped. When the file is absent, use the defaults here and offer `/almanac` once.

## Reviewer memory <a id="reviewer-memory"></a>

`reviewer`, `sentinel` and `simplifier` carry `memory: project`. Claude Code keeps a `MEMORY.md` for each under `.claude/agent-memory/<agent>/` and adds its first 200 lines to the agent's prompt. The rule for what goes in: record a finding class only after it recurs twice, with the class and the `file:line` of both occurrences. Never record the code itself, and never secrets or PII. A recorded class is a signal that the rule belongs in a lint rule or in `CLAUDE.md`. The agent proposes that move through the `NEXT` field of its Obstacles block, and `/chronicle consolidate` reads the memory folders and offers the promotion.

The memory folder is tracked by git by default. In a private workspace, set `memory: local` in a project copy of the agent, which uses `.claude/agent-memory-local/<agent>/`. `memory:` is part of auto memory: with auto memory off it has no effect. A fork has no memory, so only a fresh dispatch learns.

## Parallel fixes in worktrees <a id="fixer-worktree"></a>

`isolation: "worktree"` on the Agent call gives a subagent a temporary git worktree, branched by default from the default branch, not from the parent's `HEAD`. Claude Code removes the worktree when the subagent changes nothing.

Use it in `/scrutinize` only for a batch of two or more independent `Important` findings in disjoint files. The spawn prompt tells each `fixer` to start with `git checkout -b fix/<finding-id> <review-branch>` inside its worktree, so it works on the committed review branch. The fixer then applies the fix, commits it, and returns `BRANCH: fix/<finding-id>`. The caller merges or cherry-picks each returned branch into the review branch and re-reviews the merged diff. A review branch with uncommitted work cannot be fixed this way: commit first, or fix in place.

A single fix, or a chain of dependent fixes, runs in place without isolation. The fixer's own rules do not change: source only, never tests or gates, prove the fix with the acceptance check.

## Platform surfaces <a id="platform-surfaces"></a>

Claude Code ships its own review surfaces. `/divine` can delegate to one, or recommend one, when the user wants the platform's review instead of magician's lenses. Each one runs under the session's permission settings. A surface that posts to GitHub or edits files shows the normal permission prompts, and magician pre-approves none of them.

**`/code-review`** (`/review` is an alias) is the bundled local review skill. It states its effort first, takes a level (`low` to `max`, or `ultra`), and runs in a background agent at `high` or above. `--fix` applies the fixes it proposes, and `--comment` posts the review to the pull request. The Team and Enterprise Code Review product sets Quick, Standard or Deep per organization or repository. Recommend it for a quick second opinion on a small change, and for a team that already standardized on it. It does not read magician's lore or the round ledger.

**`claude ultrareview [target] [--post]`** is the deep, long-running review from the command line, with a 45-minute default timeout and three free runs on Pro and Max. Since 2.1.309 it needs workspace trust: pass `--trust-workspace`, or set `CLAUDE_CODE_DISABLE_ULTRAREVIEW_TRUST_CHECK=1`. Recommend it for a large or High-tier change when the user prefers one long pass over magician's lens panel. `--post` publishes on the user's behalf, so treat it like the Phase 5 posting gate.

**The Code Review GitHub flow** is the GitHub App that reviews pull requests on its own and answers `@claude review` in a pull request comment. `@claude review stop`, `off` or `pause` turns it off for that pull request. It needs the app installed (`/install-github-app`) and runs with the account that installed it, not with the user's `gh` login. Recommend it when the team wants every pull request reviewed without a local session. `/divine monitor` is the local alternative for repositories without the app.

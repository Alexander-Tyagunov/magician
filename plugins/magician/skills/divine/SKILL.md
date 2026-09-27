---
name: divine
description: Thorough, research-grounded code review of a change, PR, or MR — multi-lens (correctness, security, simplification, tests), severity-ranked with impact + fix, configurable depth, optional PR comments. Use when asked to review code, "do a code review", "review this PR/MR", "review my changes/diff/branch", or audit a changeset before merge.
---

# $divine — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/divine/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates (the depth-selection gate and the PR-posting confirmation gate), the context contract for dispatched reviewers, the adversarial-verification pass, and the completion criteria.

Codex equivalents:
- **Change context** — use Codex's shell for `gh`/`glab` and `git diff`; read the PR/MR description and linked tickets for intent.
- **Depth gate** — ask the user how deep via Codex's question/approval UI instead of AskUserQuestion.
- **Lenses** — when agent tools are available, run correctness/security/simplification/tests as bounded agents with generic self-contained prompts (Goal, Scope, diff/intent inputs, constraints, evidence and Return format). Do not request Claude profile names. Otherwise perform the lenses locally.
- **Grounding** — invoke `$magic` (or available official docs/web tooling) when the change needs external/domain evidence.
- **Posting** — writing a review to a PR/MR is a side effect: confirm explicitly and use the correct account before any `gh`/`glab` write.
- **Implement fixes (optional)** — only on explicit user confirmation, spin a Codex task to fix Critical/High findings; committing/pushing is a side effect requiring approval, the correct account, and a feature branch.
- **Monitor mode** — only create a recurring automation when the user explicitly asks for scheduling. Otherwise poll a running forge CLI via an exec session. Keep it idempotent by head SHA and review-only; never implement or push.
- **Review artifacts** — keep intermediate lens reports in a temporary directory unless the user explicitly requests durable repository artifacts. A review must not dirty the worktree.

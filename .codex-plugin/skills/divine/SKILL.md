---
name: divine
description: Thorough, research-grounded code review of a change, PR, or MR — multi-lens (correctness, security, simplification, tests), severity-ranked with impact + fix, configurable depth, optional PR comments. Use when asked to review code, "do a code review", "review this PR/MR", "review my changes/diff/branch", or audit a changeset before merge.
---

# /divine — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/divine/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates (the depth-selection gate and the PR-posting confirmation gate), the context contract for dispatched reviewers, the adversarial-verification pass, and the completion criteria.

Codex equivalents:
- **Change context** — use Codex's shell for `gh`/`glab` and `git diff`; read the PR/MR description and linked tickets for intent.
- **Depth gate** — ask the user how deep via Codex's question/approval UI instead of AskUserQuestion.
- **Lenses** — run correctness/security/simplification/tests as Codex subagents/tasks, each with self-contained context.
- **Grounding** — invoke the Codex `/magic` adapter (or context7/web) when the change needs external/domain evidence.
- **Posting** — writing a review to a PR/MR is a side effect: confirm explicitly and use the correct account before any `gh`/`glab` write.
- **Implement fixes (optional)** — only on explicit user confirmation, spin a Codex task to fix Critical/High findings; committing/pushing is a side effect requiring approval, the correct account, and a feature branch.
- **Monitor mode** — when launched on a schedule (Codex's scheduling or a loop) with `monitor <repo>`, run unattended per the source skill's monitor flow: pre-set depth/post-policy, idempotent by head SHA, review-only (never implement/push).

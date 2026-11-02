---
name: seal
description: Ships a feature — simplify pass, certify, commit, PR, CI monitoring, review loop, merge. Use when a feature branch is verified and ready to ship.
allowed-tools: Read, Task, AskUserQuestion, Edit(./CLAUDE.md), Edit(./README.md), Bash(git add -A), Bash(git commit -m *), Bash(git push -u origin HEAD), Bash(gh pr create *), Bash(gh pr checks *), Bash(gh pr view *), Bash(gh pr merge --squash --delete-branch), Bash(gh run view *)
argument-hint: "[pr-title]"
---

# /seal — Ship to Production

Take a certified feature branch through to a merged PR. This skill performs irreversible actions (push, PR, merge). It presents one consolidated ship summary and waits before the first outward command (`git push`).

## Completion Signal

"Sealed. PR merged. Run /portal cleanup steps if applicable."

## Pre-flight

- Confirm that `/certify` ran and passed.
- Confirm that the `/scrutinize` review and remediation cycle is complete, or that the user skipped it on purpose.
- **Never ship on stale evidence.** `/certify` must pass in *this* session, with fresh output you read this turn, not a remembered run. See [`lore/verification.md`](../../lore/verification.md).

## Autonomy — approve the plan, then run

Once Pre-flight is confirmed, the ship sequence runs **autonomously**. The simplify pass, the final certify, the documentation update and the commit proceed without a question to the owner. Claude Code's built-in read-only commands, read-only git included, do not prompt. This skill pre-approves the exact commit, push, PR, CI-check and merge commands shown below, and edits to `CLAUDE.md` and `README.md`. Any other edit or command goes through the normal permission prompt unless the user runs in auto mode.

Re-gate **only** on outward side effects (`git push`, `gh pr create`, `gh pr merge`), once, through the consolidated ship-summary gate below. Doctrine: [`lore/autonomy.md`](../../lore/autonomy.md).

## Process

### 1. Simplify pass

Check for the project's pre-commit skills first: `.claude/skills/verify/SKILL.md` and `.claude/skills/simplify/SKILL.md`. Since Claude Code 2.1.286, a non-bundled skill named `verify` or `simplify` that Claude may invoke runs before every commit. `/almanac` writes both as short delegators to `/certify` and to `/scrutinize --lens simplifier`.

- **Both skills present:** skip this step and step 2. The commit in step 4 runs them. Read their output when the commit returns, and fix any `Important` finding before the ship summary.
- **Only `verify` present:** run the simplify pass below, and let the commit run `verify` in place of step 2.
- **Neither present:** run the pass below and step 2 as written.

The pass: dispatch `magician:simplifier` through `Task` for a final simplification sweep. Give it a self-contained prompt: the goal, the changed files with the diff, and the return format. See [`lore/subagent-context.md`](../../lore/subagent-context.md). Fix any `Important` finding. Skip a `Suggestion` unless it is trivial.

The project skills are 10-line delegators, so they do not duplicate plugin behavior. A project can replace them with its own content. Then the project skill wins. This step still runs the plugin pass when that skill does not call `/scrutinize`.

### 2. Final certify

Run `/certify`. All checks must pass before you continue, style included, against the project's documented conventions ([`lore/code-standards.md`](../../lore/code-standards.md)). Then a review bounce on style does not reopen the ship loop.

### 3. Update documentation

Before the commit, update the docs that describe the shipped feature:
- `CLAUDE.md`: add or update changed commands, environment variables, architecture notes, or setup steps.
- `README.md`: update the feature list, screenshots, or usage examples if the change is visible to users.
- Other docs that reference the changed code (API docs, architecture diagrams, and so on).

Keep the updates small and accurate. Document what changed, not the implementation details.

### 4. Commit
```bash
git add -A
git commit -m "feat: <feature description>

<bullet list of what was built>

Co-Authored-By: Claude <noreply@anthropic.com>"
```

When the project has a `verify` or `simplify` skill, Claude Code runs it as part of this commit. A finding from that run goes back to step 1.

### Ship-summary gate — one outward approval

Steps 1 to 4 ran autonomously. Before the first outward command (`git push`), present **one** consolidated ship summary. Then gate the outward push, PR and merge through **AskUserQuestion**: end your turn at the call and act on the choice. The summary covers:
- **Changed files**: the diff going out (from step 4's `git add -A`).
- **Commit message**: what step 4 committed.
- **PR title and body**: the title plus the Summary and Test plan from step 6.
- **Merge strategy**: for example `--squash --delete-branch` (step 9).

Ask **"Ship this branch?"** with these options:
- **Ship it**: run Push, Create PR, and Merge without a further question.
- **Revise**: adjust the commit, PR, or scope first, then present the summary again.
- **Cancel**: stop here. Do not push, open a PR, or merge.

Treat a free-form "yes / approved / looks good" as **Ship it**. On **Ship it**, run Push (step 5), Create PR (step 6), and Merge (step 9) without a further question to the owner.

### 5. Push
```bash
git push -u origin HEAD
```

### 6. Create PR

Use the PR title and body approved at the ship-summary gate. Do not prompt for a title again:
```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- <what was built>
- <key decisions>

## Test plan
- [ ] All tests pass
- [ ] Types clean
- [ ] Lint clean
- [ ] Manually verified: <golden path>

Built with magician + Claude Code
EOF
)"
```
The `$(…)` body can keep this command from matching the `gh pr create` pre-approval. If Claude Code asks to confirm it, that is its own permission check, separate from the ship-summary gate.

### 7. Watch CI (evaluator-optimizer loop)

Run the checks watcher with the Bash tool's background option, so the turn is not held open. You are notified when it exits. Then read its output:
```bash
gh pr checks <pr> --watch
```

Then loop. On a failing check: run `gh run view <id> --log-failed`, fix, commit, `git push -u origin HEAD`, start the watcher again, and repeat until every check is green. For a long or unattended wait, pair with **`/goal`** ("PR checks green, then merged") so Claude keeps driving across turns. On a schedule, `/loop check CI on my PR` self-paces when you omit the interval.

### 8. Review comments

If reviewers add comments: use `/scrutinize` to process and remediate them, then `/certify`, then `git push -u origin HEAD`. The `/scrutinize` round ledger keeps a finding closed in an earlier round from a repeat. The platform's own review (`/code-review`, the `@claude review` GitHub flow) is an alternative, described in [`lore/deep/review.md#platform-surfaces`](../../lore/deep/review.md#platform-surfaces).

### 9. Merge (if auto-merge is not enabled)
```bash
gh pr merge --squash --delete-branch
```

## disableGit mode

If `disableGit: true`: skip the push, PR and merge steps. Commit locally and report done.

## Obstacles

When this skill runs as a dispatched unit and something blocks the work, do not wait for a human. Nobody is there. Do not silently ship a degraded result. Return the Obstacles block from [`lore/obstacles.md`](../../lore/obstacles.md) with whatever you completed. The fields are STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT. Interactively, say the same in prose.

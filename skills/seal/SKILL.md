---
name: seal
description: Ships a feature — simplify pass, certify, commit, PR, CI monitoring, review loop, merge. Use when a feature branch is verified and ready to ship.
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh pr create:*), Bash(gh pr checks:*), Bash(gh pr merge:*), Bash(gh pr view:*), Bash(gh run view:*), Read, Edit, Task, Monitor
argument-hint: [pr-title]
---

# /seal — Ship to Production

Take a certified feature branch through to a merged PR. This skill performs irreversible actions (push, PR, merge) — it presents a single consolidated ship-summary and waits before the first outward command (`git push`).

## Pre-flight

- Confirm /certify has been run and passed
- Confirm the /scrutinize review + remediation cycle is complete (or explicitly skipped by user)

## Autonomy — approve the plan, then run

Once Pre-flight is confirmed (/certify passed, /scrutinize + remediation complete or explicitly skipped), the ship sequence runs **autonomously**: the Simplifier Pass, Final Certify, Update Documentation, and Commit steps proceed without pausing — reading, searching, `kg query`/`blast`, and read-only git NEVER prompt for permission. Re-gate **only** on outward side effects — `git push`, `gh pr create`, `gh pr merge` — surfaced once through the consolidated ship-summary gate below, not per command. Doctrine: [lore/autonomy.md](../../lore/autonomy.md).

## Process

### 1. Simplifier Pass
Dispatch the simplifier via `Task` with subagent type `magician:simplifier` for a final simplification sweep. Give it a self-contained prompt: the goal, the changed files (with diff), and the return format (see [lore/subagent-context.md](../../lore/subagent-context.md)). Fix any Important findings. Skip Low suggestions unless trivial.

### 2. Final Certify
Run /certify. All checks must pass before continuing — including style vs the project's documented conventions ([lore/code-standards.md](../../lore/code-standards.md)), so review bounces on style don't reopen the ship loop.

### 3. Update Documentation
Before committing, update docs to reflect the shipped feature:
- **CLAUDE.md** — add or update any changed commands, env vars, architecture notes, or setup steps
- **README.md** — update feature list, screenshots, or usage examples if the change is user-visible
- Any other docs that reference the changed code (API docs, architecture diagrams, etc.)

Keep updates minimal and accurate — document what changed, not the implementation details.

### 4. Commit
```bash
git add -A
git commit -m "feat: <feature description>

<bullet list of what was built>

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Ship-summary gate — one outward approval
Steps 1–4 ran autonomously. Before the first outward command (`git push`), present **one** consolidated ship-summary and **end your turn — wait for approval:**
- **Changed files** — the diff going out (from step 4's `git add -A`)
- **Commit message** — what was committed in step 4
- **PR title + body** — the title plus the Summary + Test plan from step 6
- **Merge strategy** — e.g. `--squash --delete-branch` (step 9)

On approval, run Push, Create PR, and Merge without further per-command prompts.

### 5. Push
```bash
git push -u origin <branch>
```

### 6. Create PR
Use the PR title + body approved at the ship-summary gate above — no separate title prompt:
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

### 7. Monitor CI (evaluator-optimizer loop)
Prefer the **Monitor tool**: run the checks watcher in the background so CI status/failure events stream into the session and you react the instant a check fails — no blocking watch holding the turn open.
```bash
gh pr checks <pr> --watch    # run via the Monitor tool; each status line returns as an event
```
Fallback when the Monitor tool is unavailable (pre-v2.1.98): call `gh pr checks --watch` directly (blocking).

Then loop: **on a failing check → `gh run view <id> --log-failed` → fix → push → the watcher reports the next run → repeat until every check is green.** For a long or unattended wait, pair with **`/goal`** ("PR checks green, then merged") so Claude keeps driving across turns; on a schedule, `/loop check CI on my PR` (self-paces when you omit the interval; fixed-interval on Bedrock/Vertex).

### 8. Review Comments
If reviewers add comments: use /scrutinize to process and remediate them, then /certify, then push.

### 9. Merge (if auto-merge not enabled)
```bash
gh pr merge --squash --delete-branch
```

## disableGit Mode

If `disableGit: true`: skip push/PR/merge steps. Commit locally and report done.

## Completion Signal

"Sealed. PR merged. Run /portal cleanup steps if applicable."

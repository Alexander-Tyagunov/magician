---
name: seal
description: Ships a feature — simplify pass, certify, commit, PR, CI monitoring, review loop, merge. Use when a feature branch is verified and ready to ship.
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh pr create:*), Bash(gh pr checks:*), Bash(gh pr merge:*), Bash(gh pr view:*), Bash(gh run view:*), Read, Edit, Task, Monitor
argument-hint: [pr-title]
---

# /seal — Ship to Production

Take a certified feature branch through to a merged PR. This skill performs irreversible actions (push, PR, merge) — it asks for the PR title and waits before any `gh` command.

## Pre-flight

- Confirm /certify has been run and passed
- Confirm the /scrutinize review + remediation cycle is complete (or explicitly skipped by user)

## Process

### 1. Simplifier Pass
Dispatch the simplifier via `Task` with subagent type `magician:simplifier` for a final simplification sweep. Give it a self-contained prompt: the goal, the changed files (with diff), and the return format (see [lore/subagent-context.md](../../lore/subagent-context.md)). Fix any Important findings. Skip Low suggestions unless trivial.

### 2. Final Certify
Run /certify. All checks must pass before continuing.

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

### 5. Push
```bash
git push -u origin <branch>
```

### 6. Create PR
Ask: "What should the PR title be?" **End your turn. Wait for their answer before running any `gh` command.**

Once you have the title:
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

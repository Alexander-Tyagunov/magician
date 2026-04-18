---
name: portal
description: Creates a git worktree for isolated feature work — skips git operations if disableGit is set
keep-coding-instructions: true
---

# /portal — Git Worktree Isolation

Create an isolated git worktree for feature development.

## Check disableGit Mode

Read `.workspace/local/prefs.md` for `disableGit: true`. If set, skip all git operations and work in the current directory.

## Process (git mode)

1. **Get branch name** — ask: "What's this feature called? (I'll use it as the branch/worktree name.)" **End your turn. Wait for their answer before creating anything.**
2. **Create worktree**:
   ```bash
   BRANCH="feature/<name>"
   git worktree add ../<repo-name>-<name> -b "$BRANCH"
   ```
3. **Workspace context propagates automatically** via `worktree-init.sh` hook
4. **Confirm** the new worktree path to the user
5. Say: "Worktree created at `../<path>`. Work there for isolation. Run /seal when ready to merge."

## Process (disableGit mode)

1. Create a feature directory: `mkdir -p .features/<name>`
2. Note: no git isolation — be careful about conflicts with other in-progress work
3. Say: "Working in .features/<name>/ (disableGit mode — no worktree created)."

## Cleanup After Merge

After /seal completes and the PR merges:
```bash
git worktree remove ../<repo-name>-<name>
git branch -d feature/<name>
```

## Completion Signal

"Portal open. Worktree at `<path>`, branch `<branch>`. Start implementation or run /orchestrate."

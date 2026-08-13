---
name: portal
description: Creates a git worktree for isolated feature work (and documents cleanup post-merge); respects the disableGit preference. Use to isolate a feature on its own branch/worktree.
allowed-tools: Bash(git worktree:*), Bash(git branch:*), Bash(mkdir:*), Read
argument-hint: [feature-name]
---

# /portal — Git Worktree Isolation

Create an isolated git worktree for feature development.

## Check disableGit Mode

Read `.workspace/local/prefs.md` for `disableGit: true`. If set, skip all git operations and work in the current directory.

## Process (git mode)

1. **Get branch name** — if `$ARGUMENTS` is non-empty, use it as the feature name directly. Otherwise ask: "What's this feature called? (I'll use it as the branch/worktree name.)" **End your turn. Wait for their answer before creating anything.**
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

## Keep sibling worktrees in the loop

Worktrees isolate the files, not the consequences: a rename, a signature change, or a shared-dependency bump made here breaks whatever a sibling session is building on. When Claude Code's cross-session messaging is available, tell the affected session yourself instead of letting it discover the breakage — `ListAgents` finds the sessions working the other worktrees, `SendMessage` delivers one self-contained sentence about what landed.

Feature-detect it: no `ListAgents`, or no peer listed, means carry on exactly as before and note the change in your own summary. It is unavailable on Windows and on Bedrock/Google Cloud/Foundry, and a session inside a container can't see one on the host. See [lore/cross-session.md](../../lore/cross-session.md).

## Cleanup After Merge

After /seal completes and the PR merges:
```bash
git worktree remove ../<repo-name>-<name>
git branch -d feature/<name>
```

## Completion Signal

"Portal open. Worktree at `<path>`, branch `<branch>`. Start implementation or run /orchestrate."

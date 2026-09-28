---
name: portal
description: Creates a git worktree for isolated feature work (and documents cleanup post-merge); respects the disableGit preference. Use to isolate a feature on its own branch/worktree.
allowed-tools: Read, Bash(git worktree add *)
argument-hint: "[feature-name]"
---

# /portal — Git Worktree Isolation

Create an isolated git worktree for feature development.

## Check disableGit Mode

Read `.workspace/local/prefs.md` for `disableGit: true`. If set, skip all git operations and work in the current directory.

## Process (git mode)

1. **Get branch name** — if `$ARGUMENTS` is non-empty, use it as the feature name directly. Otherwise ask: "What's this feature called? (I'll use it as the branch/worktree name.)" **End your turn. Wait for their answer before creating anything.**
2. **Create worktree** (one plain command, so it matches this skill's pre-approval):
   ```bash
   git worktree add ../<repo-name>-<name> -b feature/<name>
   ```
3. **Workspace files** — tracked files (`.workspace/shared/`) come with the branch; gitignored ones such as `.workspace/local/prefs.md` don't. Worktrees that Claude Code creates itself (`claude --worktree`, subagent worktree isolation) copy the gitignored files listed in a `.worktreeinclude` file at the repo root, so listing `.workspace/local/prefs.md` there is a useful tip for the user. For this plain `git worktree add`, copy any local file the new worktree needs (that copy goes through the normal permission prompt).
4. **Confirm** the new worktree path to the user
5. Say: "Worktree created at `../<path>`. Work there for isolation. Run /seal when ready to merge."

## Process (disableGit mode)

1. Create a feature directory: `mkdir -p .features/<name>`
2. Note: no git isolation — be careful about conflicts with other in-progress work
3. Say: "Working in .features/<name>/ (disableGit mode — no worktree created)."

## Keep sibling worktrees in the loop

Worktrees isolate the files, not the consequences: a rename, a signature change, or a shared-dependency bump made here breaks whatever a sibling session is building on. When Claude Code's cross-session messaging is available, tell the affected session yourself instead of letting it discover the breakage — `ListAgents` finds the sessions working the other worktrees, `SendMessage` delivers one self-contained sentence about what landed.

Feature-detect it: no `ListAgents`, or no peer listed, means carry on exactly as before and note the change in your own summary. It isn't available in every environment, and a session inside a container can't see one on the host. See [lore/cross-session.md](../../lore/cross-session.md).

## Cleanup After Merge

After /seal completes and the PR merges:
```bash
git worktree remove ../<repo-name>-<name>
git branch -d feature/<name>
```

## Obstacles

This is a thin git-worktree utility. If a worktree cannot be created (branch already exists, dirty tree), report it in prose to the caller and stop; it emits no structured upward Obstacles block.

See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Portal open. Worktree at `<path>`, branch `<branch>`. Start implementation or run /orchestrate."

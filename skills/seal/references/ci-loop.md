# /seal — CI loop and fix-forward

Read this at step 7 and after the merge in step 9.

## Pre-merge CI loop (step 7)

1. Start the checks watcher with the Bash tool's background option, so the turn stays free. You get a notification when it exits.
   ```bash
   gh pr checks <pr> --watch
   ```
2. Read its output.
3. On a failing check, run `gh run view <id> --log-failed`.
4. Fix the cause, commit, and run `git push -u origin HEAD`.
5. Start the watcher again. Repeat until every check is green.

For a long or unattended wait, pair the loop with `/goal` ("PR checks green, then merged"). On a schedule, `/loop check CI on my PR` sets its own pace when you omit the interval. An unattended loop follows [lore/unattended.md](../../../lore/unattended.md). It keeps a bookmark of the last run ID and reports each failed read. It re-checks live state before each push or merge.

## Post-merge fix-forward (after step 9)

Pre-merge CI does not catch everything. After the merge, offer one loop on the default branch with `AskUserQuestion`:

- **Watch post-merge CI:** run `/loop` on the merge commit's runs (`gh run list --branch <default> --limit 5`, then `gh run view <id>`). On a failure, open a small fix-forward PR through this skill. Do not block on it.
- **Skip:** stop after the merge.

Rules for the fix-forward loop:

- Fix forward with a new small PR. Revert with the "How to revert" step from the PR body only when the fix is not clear within one round.
- Every fix-forward PR goes through the ship-summary gate. The loop never merges on its own.
- Stop the loop after the first green run on the merge commit, or after 3 failed rounds. Report the state either way.
- The loop follows [lore/unattended.md](../../../lore/unattended.md).

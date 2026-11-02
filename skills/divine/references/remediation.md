# Phase 6 — implementing the fixes, in rounds

The report is the deliverable. The user decides whether to act on it. After the report, offer the next step through `AskUserQuestion`, never assume:

- **Just report** (default): leave the fixes to the author.
- **Implement Important fixes here**: spin an agent to fix them, with tests, in this repository.
- **Implement, then commit (and push)**: as above, then commit. Push only on a second confirmation.

For a PR/MR the user does not own locally, prefer inline review comments (Phase 5) over a push to another person's branch. Push only when the user asks for it.

## When the user opts to implement

1. Scope strictly to the confirmed `Important` findings (Critical and High first). Never fix a `Nit` or a `Pre-existing` finding in this flow unless the user names it.
2. Open the round ledger at `.workspace/shared/diffs/<ref>-rounds.md` (format in [`lore/deep/review.md#round-ledger`](../../../lore/deep/review.md#round-ledger)). Write the round 1 table from the report: one row per finding, status `open`.
3. Dispatch one implementer per finding, or run the `/scrutinize` remediate loop. A behavioral fix starts with a failing test (see `/ward`). Each task is self-contained: the finding's `file:line`, the root cause, the intended behavior, and the ledger path ([`lore/subagent-context.md`](../../../lore/subagent-context.md)). For two or more independent findings in disjoint files, the parallel worktree pattern in [`lore/deep/review.md#fixer-worktree`](../../../lore/deep/review.md#fixer-worktree) applies.
4. Run the affected tests, then the full suite. No regressions.
5. Re-review only the diff since the ledger's last head SHA, with the relevant lenses. Put the ledger path in every spawn prompt. Mark each row `fixed`, `closed` with a reason, or leave it `open`. Append the round's table and count line to the ledger.
6. Stop after three rounds, or earlier when no `Important` row is open. After round 3, report what remains. Do not loop until clean.
7. <HARD-GATE> A commit and a push are side effects. Show the diff and the proposed commit message, and confirm through `AskUserQuestion`. Check the branch and the correct account before any `git commit` or `git push`. Prefer a feature branch. Never push to a protected or default branch without an explicit instruction. </HARD-GATE>
8. Start the report with the count line, `N Important, N Nit, N Pre-existing; N fixed, N closed with reason.`, then report what changed and where (commit SHA, pushed branch, opened PR URL).

## Closing a finding without a fix

An `Important` finding closes only with the user's agreement, through `AskUserQuestion` ("Close [finding] because [reason]?"). Record the reason in the ledger row. A `Nit` or a `Pre-existing` finding closes on your own judgment with a one-line reason.

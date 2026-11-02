# /seal — PR body

Read this at step 6, and again before the merge in step 9. The ship-summary gate shows this body before anything goes out.

## Fill the fields

1. **Intent.** Copy the one-sentence intent from the newest `.workspace/shared/intents/*-<feature>.md`. When no intent file exists, write the intent from the spec's purpose line. Never leave the line out.
2. **Links.** List the paths of the intent, the spec (`.workspace/shared/specs/`) and the plan (`.workspace/shared/plans/<date>-<feature>/plan.md`). Write `none` for an artifact that does not exist.
3. **Risk tier.** Pick the tier from what the diff touches, never from who wrote it. Use the tiers and approval counts in the project's `REVIEW.md` when it exists. Otherwise use these, the same as [lore/review.md](../../../lore/review.md):
   - **High:** auth, payments, migrations, CI files, secrets, or a change with no easy rollback. It needs 2 human approvals.
   - **Medium:** application logic, a shared or public interface, shared data, or a dependency bump. It needs 1 human approval.
   - **Low:** docs, comments or tests only. It needs 0 human approvals.
   An agent's approval never counts as a human approval. An approval binds to one commit, so new commits need a new approval.
4. **How to revert.** Write the exact revert step: `git revert <merge-sha>` for a plain change. Add the flag name when the change ships behind a feature flag. Add the down-migration command when the change has a migration.
5. **Testing.** List the checks `/certify` ran in this session, with their result.

## Template

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- <what was built>
- <key decisions>

**Intent:** <one sentence from the intent file>
**Links:** intent `<path>` · spec `<path>` · plan `<path>`
**Risk tier:** <Low | Medium | High> (<what it touches>; human approvals needed: <0 | 1 | 2>)
**How to revert:** <git revert <merge-sha> | flag <name> off | down-migration command>

## Testing
- [ ] All tests pass
- [ ] Types clean
- [ ] Lint clean
- [ ] Manually verified: <golden path>

Built with magician + Claude Code
EOF
)"
```

The `$(…)` body can keep this command from matching the `gh pr create` pre-approval. When Claude Code asks to confirm it, that is its own permission check, separate from the ship-summary gate.

## Approval check before the merge (step 9)

Step 8 can push new commits after a review, and an approval binds to one commit. Run this check right before `gh pr merge`, every time:

```bash
gh pr view <pr> --json headRefOid,reviewDecision,latestReviews --jq '.headRefOid as $h | {decision: .reviewDecision, head: $h, approvals: [.latestReviews[] | select(.state == "APPROVED") | {login: .author.login, on_head: (.commit.oid == $h)}]}'
```

1. Count the approvals with `on_head: true` from human accounts. A bot or app account never counts: a login that ends in `[bot]`, a CI or agent account, or an approval this session posted.
2. Compare the count with the human approvals the PR body's Risk tier needs.
3. When the count is short, or `decision` is `CHANGES_REQUESTED`, do not merge. Stop and say which approvals are missing and on which commit. "Ship it" at the ship-summary gate does not replace a missing approval.

## Risky changes

For a High-tier change, propose a feature flag in the ship summary when the project has a flag system. Ship the change with the flag off. Name the flag in "How to revert".

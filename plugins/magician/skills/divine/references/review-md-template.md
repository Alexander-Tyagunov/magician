# REVIEW.md template

`/almanac` copies everything below the marker line into `REVIEW.md` at the repository root and asks the user to fill the placeholders in angle brackets. `/divine` and `/scrutinize` read `REVIEW.md` before any dispatch, and its values override the defaults in `lore/review.md`. Keep the file short: the whole file goes into every lens prompt.

The section order is fixed, because the review skills look for the headings by name. Code owners edit the values, not the headings.

<!-- template starts below this line -->

# Review rules for <repository name>

Code owners wrote this file. Automated review follows it. Edit the values, keep the headings.

## What failure means here

A change fails review when it does one of these:

- <Breaks a documented contract: for example, changes an API response shape without a version bump.>
- <Loses or corrupts data: for example, a migration without a reversible down step.>
- <Weakens a security boundary: for example, an endpoint without the auth middleware.>
- <Ships behavior without a test that proves it.>

Everything else is a suggestion, not a failure.

## Risk tiers

The tier comes from what the change touches, never from who wrote it.

| Tier | Paths or changes | Review depth | Human approvals |
|---|---|---|---|
| Low | docs, comments, tests only, `<leaf paths>` | Quick | 0 |
| Medium | application logic, a shared or public interface, shared data, dependency bumps | Standard | 1 |
| High | `<auth paths>`, `<payment paths>`, migrations, `.github/workflows/`, secrets handling, no easy rollback | Deep, fresh verification | 2 |

Tier examples:

- Low: a README typo, a new unit test, a comment fix in `<leaf path>`.
- Medium: a new API field, a changed validation rule, a minor dependency bump.
- High: a change to `<auth middleware path>`, a schema migration, a new CI workflow step, a secret rotation.

Approval rules:

- An agent's approval never counts as a human approval.
- An approval binds to the commit it was given on. A new commit needs a new approval.

## Skip paths

Review never reports on these paths. Remove them from the diff before the lenses run.

- `<generated/**>`
- `<vendor/**>`
- `<*.lock>`
- `<fixtures/**>`

## Evidence rule

Every finding names `file:line` and the impact. A finding without a location is dropped. A claim about behavior names the test or the command that shows it.

## Tags

Every finding carries one tag:

- `Important`: a failure as defined above. Fix it or close it with a reason before merge.
- `Nit`: style, naming, a micro-cleanup. Never blocks a merge.
- `Pre-existing`: a real problem in code this change did not touch. Report it once. It does not count against the author.

## Nit cap

A review reports at most <5> nits. It keeps the ones with the most value and says how many it withheld.

## Summary line

The first line of every review summary is the count line. The findings follow it:

```
<N> Important, <N> Nit, <N> Pre-existing; <N> fixed, <N> closed with reason.
```

## Rounds

- Remediation runs at most <3> rounds. After the last round the review reports what remains and stops.
- Round 2 and later review only the diff since the previous round.
- A finding an earlier round fixed or closed is never repeated. The ledger is `.workspace/shared/diffs/<ref>-rounds.md`.
- Every `Important` finding ends as fixed or as closed with a reason.

## Pull request fields

Every pull request description fills these fields. Review reads them as the change's intent.

- **Testing:** <the tests or commands that prove the change, and their result>
- **Risk tier:** <Low, Medium or High per the tiers above, and why>
- **How to revert:** <the revert command or steps, and any data or migration step that a revert does not undo>

## House conventions the reviewers must know

- <Error handling: for example, wrap errors with context, never swallow them.>
- <Logging: for example, no PII in logs, structured fields only.>
- <Tests: for example, name tests by behavior, assert on resolved values.>

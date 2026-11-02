# Control bands for `/loop` maintenance

Use these bands for a `/loop` that watches a pipeline or service metric. Examples: CI duration, flaky-test rate, failed-run count, error rate and p95 latency. The bands decide what one tick may do. The loop follows [lore/unattended.md](../../../lore/unattended.md).

## Baseline

1. Collect at least 20 past values of the metric before the first band decision. Use `gh run list --limit 50 --json conclusion,createdAt,updatedAt` for CI metrics.
2. Compute the mean and the standard deviation (σ). Store both, with the sample size and the date, in the loop's bookmark file under `.workspace/local/bookmarks/`.
3. With fewer than 20 values, log only. Do not investigate or act.
4. Recompute the baseline once a week, or after a change that moves the metric on purpose.

## Bands

| Band | Condition | Action | Allowed tools |
|---|---|---|---|
| 1σ | value more than 1σ from the mean | Log one line in the tick report. Take no other action. | none beyond the read |
| 2σ | more than 2σ, or 1σ on 3 ticks in a row | Investigate. Read logs, recent commits and run history. Report a likely cause with evidence. | read-only: `gh run view`, `gh run list`, `git log`, `kg query`, Read |
| 3σ | more than 3σ, or 2σ on 2 ticks in a row | Open a PR with a fix, or write a runbook entry under `.workspace/shared/runbooks/`. A human merges or runs it. | the write gates of `/deploy` and `/seal` |

## Hard rules

- No band acts in production. A 3σ band in production prepares a PR or a runbook and stops.
- No band merges, deploys, re-runs a production job or changes a secret.
- A tick that cannot read the metric reports `could not read <metric>` and makes no band decision.
- Count a band only on a confirmed read. One missing value does not reset or advance a streak.

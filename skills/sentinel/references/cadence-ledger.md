# sentinel — cadence and findings ledger

A scan that re-reports closed findings trains people to ignore it. The ledger keeps a closed finding closed. The cadence keeps the baseline current.

## The ledger

Path: `.workspace/local/security/findings.jsonl`. It is never committed: `.workspace/local/` is gitignored, and the open rows are a map of unfixed vulnerabilities that must not reach the repository or its forks. A team that wants shared dismissals records each reason in the fix or dismissal PR, not in a committed ledger. One JSON object per line:

```json
{"id": "sec-2026-0001", "rule": "hardcoded-credential", "path": "src/auth.ts", "line": 45, "severity": "CRITICAL", "status": "open", "first_seen": "2026-11-02", "last_seen": "2026-11-02", "head": "<commit SHA>"}
```

- `id` stays the same across runs. Match a new finding to a ledger row by `rule` + `path` + the matched code line, not by the line number alone.
- `status` is one of `open`, `fixed`, `dismissed`.
- A `dismissed` row carries `reason` (one sentence, for example "test fixture key, never deployed") and `by` (the human who dismissed it). Only a human dismisses a CRITICAL or HIGH finding. The agent proposes the reason; the user confirms it.
- Never write a secret value into the ledger. Record the rule, the path and the line only.

## Each run

1. Read the ledger before step 1. If it does not exist, this run is the baseline: record every finding as `open` and say "baseline scan" in the report.
2. After the scan, compare each finding with the ledger:
   - New finding: add a row with `status: open`.
   - Known `open` finding: update `last_seen` and `head`.
   - Known `dismissed` finding: leave it out of the main report. Count it in one line, "N dismissed findings still present (see ledger)". Report it again only when the matched code changed.
   - An `open` row the scan no longer finds: set `status: fixed`.
3. Put the delta first in the report: new, fixed, and still open since the last run.

## Cadence

- Run a full scan weekly, and before each release. Run the first scan as a baseline before you act on any finding.
- Platform option: Claude Security scheduled scans, where the organization has them, run the scan on the platform's schedule.
- Local fallback: `/loop 1w /sentinel` in a session that stays open. Scheduled or unattended runs follow [`lore/unattended.md`](../../../lore/unattended.md).
- A fix is a bounded patch on a branch, opened as a PR and reviewed like any other change (`/scrutinize` or `/divine`). Sentinel itself never changes code.

## Close the class, not only the instance

When a fix closes a finding class (for example SQL built by string concatenation), turn the class into a check that runs every time:
- a scan rule (a `magician-scan` pattern, a linter rule or a CI step), or
- an eval case under `evals/` that fails if the class comes back.

Record the new check in the ledger row's `reason` field when the row moves to `fixed`.

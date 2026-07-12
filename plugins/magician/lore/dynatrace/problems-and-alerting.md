# Dynatrace — Problems & Alerting

Context: Dynatrace SaaS (Gen3), Grail + DQL GA. Davis AI correlates raw events into **problems** (root-cause + impact). Query them in DQL over Grail (`dt.davis.problems`, `dt.davis.events`); alert via **metric events** and the **Anomaly Detection** app (DQL-based). Log search is separate — see lore/dynatrace/dql-log-queries.md and log-ingestion-and-attributes.md.

DO make error logs alert-worthy: distinct `loglevel` (ERROR/WARN), stable text, correlation ids, `dt.entity.*` — so a log-event rule matches and the problem carries context.
DO prefer Davis auto-adaptive/seasonal baselines for noisy signals; reserve static thresholds for hard SLOs.
DO scope every alert to an entity so Davis maps it to the right host/service and merges into one problem.
DO query problems by `event.status`, de-noising with Davis flags.
DON'T alert per log line or per hot-loop metric — duplicate problems; alert on a rate/threshold and let Davis correlate.
DON'T invent fields: problems use `event.id`, `display_id`, `event.status`, `event.kind`, `event.type`, `event.start`, `event.end`, `resolved_problem_duration`, `smartscape.affected_entities`.
DON'T mix SPL/KQL/LogQL/Insights syntax into DQL — pipe with `|`; use `filter`/`summarize`/`makeTimeseries`.

## Query problems (DQL over Grail)
```
// active problems, drop duplicates
fetch dt.davis.problems
| filter event.status == "ACTIVE" and not(dt.davis.is_duplicate)
| summarize activeProblems = countDistinct(event.id)

// one problem by its stable display id
fetch dt.davis.problems | filter display_id == "P-24051200"

// MTTR (h) for closed, real problems over 7d
fetch dt.davis.problems, from:now()-7d
| filter event.status == "CLOSED" and dt.davis.is_frequent_event == false and dt.davis.is_duplicate == false
| makeTimeseries `AVG hours` = avg(toLong(resolved_problem_duration)/3600000000000.0), time:event.end
```
Gotcha: Davis flags (`dt.davis.is_duplicate`, `dt.davis.is_frequent_event`) are **booleans** — use `not(flag)` or `== false`, never the string `"true"`.

## Query raw events feeding a problem
```
fetch dt.davis.events, from:now()-7d
| filter event.kind == "DAVIS_EVENT"
| filter event.type == "OSI_HIGH_CPU" or event.type == "OSI_HIGH_MEMORY"
| makeTimeseries count = count(default:0)
```
`event.kind` splits Davis-detected vs custom/info; `event.type` is the detector.

## Configure alerting
- **Metric events**: *static threshold* (fixed SLO), *auto-adaptive* (Davis learns), or *seasonal baseline* (daily/weekly band). Auto-adaptive/seasonal need a **metric-selector** event (metric-key events are static-only). Add entity dims (e.g. `dt.entity.host=HOST-123`) so it hits the right entity; Davis picks the most specific (process > host) into one problem.
- **Log alerting**: configure a **log event** with a rate/window-based DQL matcher (e.g. `filter loglevel == "ERROR"`); a match raises a custom event that opens/updates a Davis problem and notifies. Keep it specific to avoid duplicates.

## Sources
- docs.dynatrace.com — Davis for Grail (problems/events DQL); Semantic Dictionary (dt.davis.* types)
- docs.dynatrace.com — DQL commands (fetch/filter/summarize/makeTimeseries), operators (`not`)
- docs.dynatrace.com — Anomaly detection: metric events; log events

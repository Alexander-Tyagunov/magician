# Splunk — Dashboards & Alerts

Turning SPL into monitoring. Verify at help.splunk.com; Splunk Enterprise 9.x/10.x + Splunk Cloud. NOTE the split: **Splunk Enterprise/Cloud** alerts = saved SPL searches (this file). **Splunk Observability Cloud** is a different product — detectors written in **SignalFlow** (a Python-like streaming language over metrics), NOT SPL. Don't mix the two.

## Alerts (saved-search based)
An alert is a saved search on a **schedule** (cron) or **real-time**, plus a trigger condition and actions.

- DO keep the base search WIDE and filter in the *trigger condition*, not the search — the base results are what feed actions/tokens. Filtering inside the search shrinks what notifications can see.
- DO pick a trigger type: per-result (fire once per matching event); number of results/hosts/sources; or **custom condition** — a secondary search over the base results.
- DO write the custom condition as SPL returning rows only when it should fire. Example — base `index=app sourcetype=myapp:json status>=500 | stats count by status`, custom condition: `search count > 10`.
- DO scope real-time alerts with a rolling window (e.g. `is greater than 5 in 1 minute`); prefer scheduled — real-time is resource-heavy.
- DO set **throttling** (suppression): after firing, suppress for N minutes, optionally per field value (e.g. by `host`). Distinct from trigger conditions.
- DO choose actions: email, webhook, run a script/alert-action app, add to triggered-alerts, log/index event.
- DON'T alert on `| stats count | search count>10` when you need every group's values downstream — that discards non-matching rows.

"No data" alert: `<search> earliest=0 latest=now | stats count`, trigger when `count == 0`.

## Dashboards
Two systems. Prefer **Dashboard Studio** (JSON source) for new work; **Classic** uses Simple XML.

Studio separates `dataSources`, `visualizations`, `layout`, `inputs`. A `ds.search` holds the SPL in `options.query`; a viz binds it via `"dataSources": { "primary": "ds_errors" }`:
```json
"ds_errors": { "type": "ds.search", "options": {
  "query": "index=app sourcetype=myapp:json status>=500 | timechart span=5m count by status",
  "queryParameters": { "earliest": "$time.earliest$", "latest": "$time.latest$" },
  "refresh": "30s", "refreshType": "delay" } }
```
- DO use inputs/tokens (`$time.earliest$`, `$dropdown_host$`) for interactive panels; a base search + **chain searches** (`ds.chain`) post-process once instead of re-running SPL per panel.
- DO use `ds.savedSearch` (with `ref`) to reuse a report/accelerated search.
- DON'T embed all-time (`earliest=0`) unbounded searches in refreshing panels — cost blows up.

Ingestion (HEC `/services/collector/event`, indexes, sourcetypes) feeds all of this — see lore/splunk/ingestion-sourcetypes-indexes.md. SPL search/stats depth: lore/splunk/spl-search-and-stats.md.

## Sources
- help.splunk.com/en/splunk-enterprise/alert-and-respond/alerting-manual/9.4 (configure-alert-trigger-conditions; alert-examples; throttle-alerts)
- help.splunk.com/en/splunk-enterprise/create-dashboards-and-reports/dashboard-studio/10.0/use-data-sources/data-source-options-and-properties
- help.splunk.com/en/splunk-observability-cloud/.../introduction-to-alerts-and-detectors · dev.splunk.com/observability/docs/signalflow

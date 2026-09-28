# Splunk — deep dive

> On-demand companion to `lore/splunk.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [SPL search & stats](#spl-search-and-stats) · [Ingestion, sourcetypes & indexes](#ingestion-sourcetypes-indexes) · [Dashboards & Alerts](#dashboards-and-alerts)

## SPL search & stats <a id="spl-search-and-stats"></a>

SPL (Search Processing Language), Search Reference 10.4 — the language of **Splunk Enterprise & Splunk Cloud Platform**. NOT Splunk Observability Cloud: its metrics use SignalFlow and logs use Log Observer (no SPL). Verify at docs.splunk.com.

### The pipeline
SPL runs left→right: a base filter (`field=value` terms + free text), then `|` commands. **Lead with `index=`, `sourcetype=`, and a time range** — they prune before disk reads.
- DO scope every search: `index=app sourcetype=myapp:json earliest=-1h latest=now`.
- DON'T run `index=*` over "All time"; DON'T overwrite `_time` with eval before `timechart`.

### Find errors / trace a flow (the headline)
Errors by service, most frequent first:
```
index=app sourcetype=myapp:json (level=ERROR OR level=FATAL)
| stats count BY service, message | sort -count
```
Trace one request across services by correlation id:
```
index=app trace_id=4f9a2c | sort _time | table _time, service, level, message
```
Error rate + p95 latency over time:
```
index=app | timechart span=5m count(eval(level="ERROR")) AS errors, count AS total, perc95(duration_ms) AS p95
```

### stats — aggregate
`stats <func>(<field>) [AS name] ... [BY field-list]`; one BY clause, one row per BY combo. Functions: `count`, `dc()`/`distinct_count()`, `avg`/`sum`/`min`/`max`/`median`, `perc<N>()`, `values()`/`list()`, `latest()`/`earliest()`. Conditional counts: `count(eval(status>=500)) AS server_errors`.
- DON'T use `first()`/`last()` for newest/oldest by time — they are input‑order; use `latest()`/`earliest()`.
- DON'T `dc()` a high‑cardinality field when an estimate suffices (memory‑heavy) — use `estdc()`.
- DON'T rely on the deprecated implicit wildcard (`stats avg`) — write `stats avg(*)`.

### Time series
`timechart` auto‑bins `_time` on X. Set `span=` explicitly (`1m`,`5m`,`1h`,`1d`) or it defaults to `bins=100`. Split with BY; cap series with `WHERE count>100`. `per_hour()`/`per_day()` give a rate independent of span.

### JSON logs & fields
- With `INDEXED_EXTRACTIONS=json` or `KV_MODE=json` (props.conf), fields auto‑extract — reference them directly, no spath.
- Else extract at search time: `| spath path=error.code output=code` (JSON arrays are zero‑based: `commits{}.id`), or `| rex field=_raw "dur=(?<duration>\d+)"`.

### HEC ingestion (logs in)
POST JSON to `/services/collector/event`, port 8088, header `Authorization: Splunk <token>`. Optional keys: `time` (epoch `sec.ms`), `host`, `source`, `sourcetype`, `index`, `fields`, `event` (string or object).
```
curl -H "Authorization: Splunk <token>" https://splunk:8088/services/collector/event \
 -d '{"sourcetype":"myapp:json","index":"app","event":{"level":"ERROR","service":"checkout","trace_id":"4f9a2c","message":"payment declined"}}'
```
- Raw text → `/services/collector/raw` + `X-Splunk-Request-Channel: <GUID>` when indexer ack is on. Splunk Cloud: `https://http-inputs-<host>.splunkcloud.com`.
- Batch events (concatenated objects or a JSON array) per request. Index‑time custom fields go in `fields` (event endpoint only).

Indexes/sourcetypes/HEC: lore/deep/splunk.md#ingestion-sourcetypes-indexes · alerts & dashboards: lore/deep/splunk.md#dashboards-and-alerts

### Sources
- help.splunk.com/en/splunk-enterprise/search/spl-search-reference/10.4/search-commands/{stats,timechart,spath}
- help.splunk.com/en/splunk-enterprise/get-started/get-data-in/10.4/get-data-with-http-event-collector/format-events-for-http-event-collector

## Ingestion, sourcetypes & indexes <a id="ingestion-sourcetypes-indexes"></a>

Splunk **Enterprise / Cloud Platform** (10.x; 9.x still supported) = the log/event store queried with SPL; HEC, indexes, and sourcetypes live here. **Observability Cloud** is a separate product (metrics/APM/Log Observer) with its own OTLP-style ingest/query — don't point HEC at it or mix the two.

### Indexes — where events live
An index is the on-disk event store; each event lands in one index; scope every search with `index=`. Built-ins: `main` (default), internal `_internal`, `_audit`, `_introspection`. Create purpose-built app indexes (`indexes.conf`) — don't dump everything in `main`. Two kinds: **event** (raw logs → `stats`) and **metric** (numeric → `mstats`, not `stats`). Retention is per index: `frozenTimePeriodInSecs`, `maxTotalDataSizeMB`. Right `index=` first = biggest speed lever.

### Sourcetypes — how events are parsed
A sourcetype labels the format and drives line-breaking, timestamping, and field extraction via `props.conf`. For one-JSON-per-line app logs, built-in `_json` works, or define your own:
```
[myapp:json]
SHOULD_LINEMERGE = false
LINE_BREAKER = ([\r\n]+)
TIME_PREFIX = "ts":"
KV_MODE = json         # search-time JSON extraction
TRUNCATE = 100000
```
Use `INDEXED_EXTRACTIONS = json` only for forwarder-read files (not HEC — HEC parses JSON itself). Keep sourcetypes stable and specific (`myapp:access`, `myapp:app`): extractions, searches, and dashboards key off the name.

### HEC ingestion (logs over HTTP)
Default port **8088**. Header `Authorization: Splunk <token>`.
- `/services/collector/event` — JSON with metadata (preferred for app logs)
- `/services/collector/raw` — unparsed bytes; sourcetype/index from the token
- `/services/collector/health` — readiness probe

Event JSON keys: `event` (string or object), `index`, `sourcetype`, `source`, `host`, `time` (epoch seconds), `fields` (promoted to **indexed** fields). Batch by newline-concatenating objects — **no** JSON array, no commas:
```bash
curl -k https://host:8088/services/collector/event \
 -H "Authorization: Splunk <token>" \
 -d '{"time":1718000000,"index":"app","sourcetype":"myapp:json","event":{"level":"ERROR","msg":"payment failed","trace_id":"abc123"}}'
```
Response: `{"text":"Success","code":0}`. For at-least-once delivery, enable indexer ack on the token, send `?channel=<guid>`, poll `/services/collector/ack` for the `ackId`.

### Search ingested data (SPL)
```
index=app sourcetype=myapp:json level=ERROR
| stats count by trace_id
```
SPL depth: lore/deep/splunk.md#spl-search-and-stats · alerts/dashboards: lore/deep/splunk.md#dashboards-and-alerts.

### DON'T
- DON'T wrap an HEC batch in a `[ ... ]` array — newline-delimit the objects.
- DON'T over-promote `fields`/`INDEXED_EXTRACTIONS` (index bloat); prefer search-time `KV_MODE = json`.
- DON'T conflate Observability Cloud ingest/queries with Enterprise HEC/SPL.
- DON'T let app logs fall into `main` untyped — set an explicit index + sourcetype.

### Sources
dev.splunk.com — HTTP Event Collector reference (endpoints, JSON, ack) · help.splunk.com — Getting Data In (HEC, props.conf), About indexes/indexers · Splexicon — sourcetype, index

## Dashboards & Alerts <a id="dashboards-and-alerts"></a>

Turning SPL into monitoring. Verify at help.splunk.com; Splunk Enterprise 9.x/10.x + Splunk Cloud. NOTE the split: **Splunk Enterprise/Cloud** alerts = saved SPL searches (this file). **Splunk Observability Cloud** is a different product — detectors written in **SignalFlow** (a Python-like streaming language over metrics), NOT SPL. Don't mix the two.

### Alerts (saved-search based)
An alert is a saved search on a **schedule** (cron) or **real-time**, plus a trigger condition and actions.

- DO keep the base search WIDE and filter in the *trigger condition*, not the search — the base results are what feed actions/tokens. Filtering inside the search shrinks what notifications can see.
- DO pick a trigger type: per-result (fire once per matching event); number of results/hosts/sources; or **custom condition** — a secondary search over the base results.
- DO write the custom condition as SPL returning rows only when it should fire. Example — base `index=app sourcetype=myapp:json status>=500 | stats count by status`, custom condition: `search count > 10`.
- DO scope real-time alerts with a rolling window (e.g. `is greater than 5 in 1 minute`); prefer scheduled — real-time is resource-heavy.
- DO set **throttling** (suppression): after firing, suppress for N minutes, optionally per field value (e.g. by `host`). Distinct from trigger conditions.
- DO choose actions: email, webhook, run a script/alert-action app, add to triggered-alerts, log/index event.
- DON'T alert on `| stats count | search count>10` when you need every group's values downstream — that discards non-matching rows.

"No data" alert: `<search> earliest=0 latest=now | stats count`, trigger when `count == 0`.

### Dashboards
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

Ingestion (HEC `/services/collector/event`, indexes, sourcetypes) feeds all of this — see lore/deep/splunk.md#ingestion-sourcetypes-indexes. SPL search/stats depth: lore/deep/splunk.md#spl-search-and-stats.

### Sources
- help.splunk.com/en/splunk-enterprise/alert-and-respond/alerting-manual/9.4 (configure-alert-trigger-conditions; alert-examples; throttle-alerts)
- help.splunk.com/en/splunk-enterprise/create-dashboards-and-reports/dashboard-studio/10.0/use-data-sources/data-source-options-and-properties
- help.splunk.com/en/splunk-observability-cloud/.../introduction-to-alerts-and-detectors · dev.splunk.com/observability/docs/signalflow

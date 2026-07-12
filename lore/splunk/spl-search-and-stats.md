# Splunk — SPL search & stats

SPL (Search Processing Language), Search Reference 10.4 — the language of **Splunk Enterprise & Splunk Cloud Platform**. NOT Splunk Observability Cloud: its metrics use SignalFlow and logs use Log Observer (no SPL). Verify at docs.splunk.com.

## The pipeline
SPL runs left→right: a base filter (`field=value` terms + free text), then `|` commands. **Lead with `index=`, `sourcetype=`, and a time range** — they prune before disk reads.
- DO scope every search: `index=app sourcetype=myapp:json earliest=-1h latest=now`.
- DON'T run `index=*` over "All time"; DON'T overwrite `_time` with eval before `timechart`.

## Find errors / trace a flow (the headline)
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

## stats — aggregate
`stats <func>(<field>) [AS name] ... [BY field-list]`; one BY clause, one row per BY combo. Functions: `count`, `dc()`/`distinct_count()`, `avg`/`sum`/`min`/`max`/`median`, `perc<N>()`, `values()`/`list()`, `latest()`/`earliest()`. Conditional counts: `count(eval(status>=500)) AS server_errors`.
- DON'T use `first()`/`last()` for newest/oldest by time — they are input‑order; use `latest()`/`earliest()`.
- DON'T `dc()` a high‑cardinality field when an estimate suffices (memory‑heavy) — use `estdc()`.
- DON'T rely on the deprecated implicit wildcard (`stats avg`) — write `stats avg(*)`.

## Time series
`timechart` auto‑bins `_time` on X. Set `span=` explicitly (`1m`,`5m`,`1h`,`1d`) or it defaults to `bins=100`. Split with BY; cap series with `WHERE count>100`. `per_hour()`/`per_day()` give a rate independent of span.

## JSON logs & fields
- With `INDEXED_EXTRACTIONS=json` or `KV_MODE=json` (props.conf), fields auto‑extract — reference them directly, no spath.
- Else extract at search time: `| spath path=error.code output=code` (JSON arrays are zero‑based: `commits{}.id`), or `| rex field=_raw "dur=(?<duration>\d+)"`.

## HEC ingestion (logs in)
POST JSON to `/services/collector/event`, port 8088, header `Authorization: Splunk <token>`. Optional keys: `time` (epoch `sec.ms`), `host`, `source`, `sourcetype`, `index`, `fields`, `event` (string or object).
```
curl -H "Authorization: Splunk <token>" https://splunk:8088/services/collector/event \
 -d '{"sourcetype":"myapp:json","index":"app","event":{"level":"ERROR","service":"checkout","trace_id":"4f9a2c","message":"payment declined"}}'
```
- Raw text → `/services/collector/raw` + `X-Splunk-Request-Channel: <GUID>` when indexer ack is on. Splunk Cloud: `https://http-inputs-<host>.splunkcloud.com`.
- Batch events (concatenated objects or a JSON array) per request. Index‑time custom fields go in `fields` (event endpoint only).

Indexes/sourcetypes/HEC: lore/splunk/ingestion-sourcetypes-indexes.md · alerts & dashboards: lore/splunk/dashboards-and-alerts.md

## Sources
- help.splunk.com/en/splunk-enterprise/search/spl-search-reference/10.4/search-commands/{stats,timechart,spath}
- help.splunk.com/en/splunk-enterprise/get-started/get-data-in/10.4/get-data-with-http-event-collector/format-events-for-http-event-collector

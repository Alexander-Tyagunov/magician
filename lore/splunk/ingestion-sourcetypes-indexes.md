# Splunk — Ingestion, sourcetypes & indexes

Splunk **Enterprise / Cloud Platform** (10.x; 9.x still supported) = the log/event store queried with SPL; HEC, indexes, and sourcetypes live here. **Observability Cloud** is a separate product (metrics/APM/Log Observer) with its own OTLP-style ingest/query — don't point HEC at it or mix the two.

## Indexes — where events live
An index is the on-disk event store; each event lands in one index; scope every search with `index=`. Built-ins: `main` (default), internal `_internal`, `_audit`, `_introspection`. Create purpose-built app indexes (`indexes.conf`) — don't dump everything in `main`. Two kinds: **event** (raw logs → `stats`) and **metric** (numeric → `mstats`, not `stats`). Retention is per index: `frozenTimePeriodInSecs`, `maxTotalDataSizeMB`. Right `index=` first = biggest speed lever.

## Sourcetypes — how events are parsed
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

## HEC ingestion (logs over HTTP)
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

## Search ingested data (SPL)
```
index=app sourcetype=myapp:json level=ERROR
| stats count by trace_id
```
SPL depth: lore/splunk/spl-search-and-stats.md · alerts/dashboards: lore/splunk/dashboards-and-alerts.md.

## DON'T
- DON'T wrap an HEC batch in a `[ ... ]` array — newline-delimit the objects.
- DON'T over-promote `fields`/`INDEXED_EXTRACTIONS` (index bloat); prefer search-time `KV_MODE = json`.
- DON'T conflate Observability Cloud ingest/queries with Enterprise HEC/SPL.
- DON'T let app logs fall into `main` untyped — set an explicit index + sourcetype.

## Sources
dev.splunk.com — HTTP Event Collector reference (endpoints, JSON, ack) · help.splunk.com — Getting Data In (HEC, props.conf), About indexes/indexers · Splexicon — sourcetype, index

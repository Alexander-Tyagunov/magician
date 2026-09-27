# Google Cloud Logging — deep dive

> On-demand companion to `lore/gcp-logging.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Logging query language](#logging-query-language) · [Structured logging & severity](#structured-logging-and-severity) · [Sinks, Log-Based Metrics & Alerts](#sinks-metrics-and-alerts)

## Logging query language <a id="logging-query-language"></a>

The Logs Explorer query language (verified 2026 at docs.cloud.google.com/logging). Structure: `FIELD OP VALUE`, implicitly AND-joined. Operators: `=` `!=` `>` `<` `>=` `<=`, `:` (has/substring), `=~` `!~` (RE2 regex). Booleans `AND OR NOT` MUST be uppercase (lowercase parses as search text); `-` = NOT; precedence NOT>OR>AND. Comments `--`. Query cap 20,000 chars. Case-insensitive except regex + operators.

DO filter on INDEXED fields for speed: `resource.type`, `resource.labels.*`, `logName`, `severity`, `timestamp`, `insertId`, `operation.id`, `trace`, `httpRequest.status`, `labels.*`. Unindexed field filters scan.
DO always bound `resource.type` + `severity` + a `timestamp` window — it narrows the scan and matches the Monitoring data model.
DO use the `SEARCH` function for token text (case-insensitive, faster than a bare term): `SEARCH("timeout")`, `SEARCH(textPayload, "hello world")`, exact phrase `SEARCH("\`connection refused\`")`.
DO test field existence with `:*` and null with `NULL_VALUE`: `operation.id:*`, `jsonPayload.userId = NULL_VALUE`.
DON'T assume `severity` is numeric-only text — quote it: `severity>="ERROR"` (levels DEFAULT<DEBUG<INFO<NOTICE<WARNING<ERROR<CRITICAL<ALERT<EMERGENCY).
DON'T confuse `jsonPayload.end_time` with `jsonPayload.endTime` — JSON keys are case-sensitive and distinct.
DON'T forget to URL-encode `/` in a `logName` literal (`%2F`); or use `log_id("cloudaudit.googleapis.com/activity")` which takes the un-encoded id.

### Find errors / trace a request (valid examples)
```
resource.type="cloud_run_revision"
severity>="ERROR"
timestamp>="2026-07-12T00:00:00Z"
```
```
resource.type="k8s_container"
resource.labels.namespace_name="checkout"
jsonPayload.message=~"connection refused|timeout"
NOT textPayload:"health"
```
Trace one request end-to-end (correlation id promoted from structured fields — see lore/deep/gcp-logging.md#structured-logging-and-severity):
```
trace="projects/PROJECT_ID/traces/06796866738c859f2f19b7cfb3214824"
```
```
jsonPayload.request_id="a1b2c3" AND severity>="WARNING"
```
Regex is RE2, case-sensitive, unanchored by default; `(?i)` for insensitive, `^`/`$` to anchor:
```
labels.pod_name=~"^api-(foo|bar)"
httpRequest.status>=500 AND httpRequest.requestUrl=~"/v1/orders"
```

### Log-based metrics & alerting (from the same filter)
A metric's *filter* is a query in this language. Counter = count matching entries; distribution = bucket a numeric value; extract labels with `regexp_extract`. User metrics are `logging.googleapis.com/user/NAME`, non-retroactive (only entries after creation). Alert on them in Monitoring; configure missing-data handling since series can gap. Details: lore/deep/gcp-logging.md#sinks-metrics-and-alerts.
```
resource.type="cloud_run_revision" AND severity>="ERROR"   -- counter metric filter
```

### Sources
docs.cloud.google.com/logging/docs/view/logging-query-language · docs.cloud.google.com/logging/docs/logs-based-metrics · docs.cloud.google.com/logging/docs/structured-logging

## Structured logging & severity <a id="structured-logging-and-severity"></a>

Emit logs Cloud Logging can index + search, and alert by severity.

A JSON object lands in `jsonPayload` (path-queryable, select fields indexable); a string lands in `textPayload` (searchable, not path-indexed). For agent-collected services (Cloud Run, GKE, App Engine, Functions), write ONE serialized JSON object per line to stdout/stderr — a JSON-*looking* string that isn't valid still lands in `textPayload`. Client libraries set these directly instead.

### Special fields promoted to the LogEntry
Keys lifted from `jsonPayload` to top-level `LogEntry` fields (optional; `.../` = `logging.googleapis.com/`):
- `severity` → severity; `message` → display text (put stack traces here so Error Reporting groups them)
- `httpRequest` → httpRequest (method, status, latency); `time`/`timestamp` → timestamp
- `.../trace` → trace — MUST be `projects/PROJECT_ID/traces/TRACE_ID` to group a request
- `.../spanId` → spanId; `.../trace_sampled` → traceSampled (bool); `.../insertId` → insertId (dedup + ordering)
- `.../labels` → labels (indexed string map); `.../operation` → operation; `.../sourceLocation` → sourceLocation

### Severity (LogSeverity enum)
DEFAULT(0) DEBUG(100) INFO(200) NOTICE(300) WARNING(400) ERROR(500) CRITICAL(600) ALERT(700) EMERGENCY(800). Map your app level (and encodings like Java FINE/FINER) onto these yourself; DEFAULT applies only when `severity` is omitted, and values outside the enum are undefined. Set the prod threshold by env (INFO/WARN prod, DEBUG dev).

DO emit one JSON object per event with `severity`, a `message`, and a correlation id (prefer `.../trace` + `spanId`, queryable as `trace=...`).
DO push bounded selectors (request_id, tenant, route) into `.../labels` — labels are indexed; deep `jsonPayload` paths are not.
DON'T log secrets/PII/tokens — payloads are queryable and exported by sinks.
DON'T rely on case-insensitive keys: `jsonPayload.userId` ≠ `jsonPayload.user_id` (only severity + operators are case-insensitive).
DON'T dump large blobs — an entry has a size cap; oversized entries are rejected/truncated.

### Example structured log line (stdout)
```json
{"severity":"ERROR","message":"charge failed: gateway timeout","logging.googleapis.com/trace":"projects/PROJECT_ID/traces/06796866738c859f2f19b7cfb3214824","logging.googleapis.com/spanId":"000000000000004a","logging.googleapis.com/labels":{"request_id":"a1b2c3","route":"/v1/charge"},"httpRequest":{"requestMethod":"POST","status":504},"attempt":2}
```

### Querying it (full query syntax: lore/deep/gcp-logging.md#logging-query-language)
```
resource.type="cloud_run_revision"
severity>="ERROR"
jsonPayload.attempt>=2
labels.request_id="a1b2c3"      -- from .../labels
trace="projects/PROJECT_ID/traces/06796866738c859f2f19b7cfb3214824"
httpRequest.status>=500 AND jsonPayload.message=~"timeout"
```
Counter/distribution metric + alert from a filter: lore/deep/gcp-logging.md#sinks-metrics-and-alerts.

### Sources
docs.cloud.google.com/logging/docs/structured-logging · docs.cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry · docs.cloud.google.com/logging/docs/view/logging-query-language

## Sinks, Log-Based Metrics & Alerts <a id="sinks-metrics-and-alerts"></a>

Turn logs into routing, metrics, and alerts. Sink/metric/alert **filters all use the Logging query language** (same syntax as Logs Explorer); creation is done with `gcloud logging` / `gcloud monitoring` or the API. Structured `jsonPayload` fields and `severity` are what you filter and extract on, so log clean structured events first (see lore/deep/gcp-logging.md#structured-logging-and-severity).

### Sinks (routing/export)
Every project has two managed sinks: `_Required` (audit Admin Activity/system logs — can't disable or delete) and `_Default` (everything else → `_Default` bucket — can disable, can't delete). Add your own sinks to route matching entries to: a log bucket, BigQuery dataset, Cloud Storage bucket, Pub/Sub topic (for Splunk/third-party), or another project (one-hop).

DO create a sink with an inclusion filter (Logging query language):
```
gcloud logging sinks create errors-to-bq \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/DATASET_ID \
  --log-filter='severity>=ERROR AND resource.type="cloud_run_revision"'
```
DO add exclusions (repeatable `--exclusion`) to drop noisy high-volume logs, and grant the sink's writer identity write access on the destination after create.
DON'T route a firehose to BigQuery/Storage without a filter — you pay to store noise. DON'T forget: user-defined log-based **metrics count both included and excluded logs**, but sinks only route included ones.

### Log-based metrics
Three kinds: **counter** (count matching entries), **distribution** (histogram of an extracted numeric value, e.g. latency), **boolean**. Metrics are forward-only (no backfill) and named `logging.googleapis.com/user/NAME`.
```
gcloud logging metrics create error_count \
  --description="App errors" \
  --log-filter='severity>=ERROR AND resource.type="k8s_container"'
```
DO extract labels via `labelExtractors` (API) with `REGEXP_EXTRACT` to break metrics down by dimension:
```
"labelExtractors": {
  "route": "REGEXP_EXTRACT(jsonPayload.path, \"^(/[a-z]+)\")"
}
```
DON'T create high-cardinality labels (user id, request id) — you get a time-series explosion. DON'T embed secrets in filters; filters are stored as service data.

### Alerts
Two paths: **log-based alert (LogMatch)** fires per matching entry — good for "this message appeared"; exactly one condition, `combiner="OR"`, ignores excluded logs. **Metric-based** alerts on a log-based metric — good for rates/thresholds ("errors > N in 5m").
```
gcloud monitoring policies create --policy-from-file=alert-policy.json
```
The LogMatch condition query is Logging query language, e.g. `severity=ERROR AND jsonPayload.event="payment_failed"`. DO set `notificationRateLimit` + `autoClose` (min 1800s) so one bad deploy doesn't storm you. DON'T use log-based alerts to count — use a metric-based policy on a counter metric for thresholds.

### Sources
- docs.cloud.google.com/logging/docs/export/configure_export_v2
- docs.cloud.google.com/logging/docs/logs-based-metrics (+ /counter-metrics)
- docs.cloud.google.com/logging/docs/alerting/log-based-alerts

# Google Cloud Logging — Logging query language

The Logs Explorer query language (verified 2026 at docs.cloud.google.com/logging). Structure: `FIELD OP VALUE`, implicitly AND-joined. Operators: `=` `!=` `>` `<` `>=` `<=`, `:` (has/substring), `=~` `!~` (RE2 regex). Booleans `AND OR NOT` MUST be uppercase (lowercase parses as search text); `-` = NOT; precedence NOT>OR>AND. Comments `--`. Query cap 20,000 chars. Case-insensitive except regex + operators.

DO filter on INDEXED fields for speed: `resource.type`, `resource.labels.*`, `logName`, `severity`, `timestamp`, `insertId`, `operation.id`, `trace`, `httpRequest.status`, `labels.*`. Unindexed field filters scan.
DO always bound `resource.type` + `severity` + a `timestamp` window — it narrows the scan and matches the Monitoring data model.
DO use the `SEARCH` function for token text (case-insensitive, faster than a bare term): `SEARCH("timeout")`, `SEARCH(textPayload, "hello world")`, exact phrase `SEARCH("\`connection refused\`")`.
DO test field existence with `:*` and null with `NULL_VALUE`: `operation.id:*`, `jsonPayload.userId = NULL_VALUE`.
DON'T assume `severity` is numeric-only text — quote it: `severity>="ERROR"` (levels DEFAULT<DEBUG<INFO<NOTICE<WARNING<ERROR<CRITICAL<ALERT<EMERGENCY).
DON'T confuse `jsonPayload.end_time` with `jsonPayload.endTime` — JSON keys are case-sensitive and distinct.
DON'T forget to URL-encode `/` in a `logName` literal (`%2F`); or use `log_id("cloudaudit.googleapis.com/activity")` which takes the un-encoded id.

## Find errors / trace a request (valid examples)
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
Trace one request end-to-end (correlation id promoted from structured fields — see structured-logging-and-severity.md):
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

## Log-based metrics & alerting (from the same filter)
A metric's *filter* is a query in this language. Counter = count matching entries; distribution = bucket a numeric value; extract labels with `regexp_extract`. User metrics are `logging.googleapis.com/user/NAME`, non-retroactive (only entries after creation). Alert on them in Monitoring; configure missing-data handling since series can gap. Details: sinks-metrics-and-alerts.md.
```
resource.type="cloud_run_revision" AND severity>="ERROR"   -- counter metric filter
```

## Sources
docs.cloud.google.com/logging/docs/view/logging-query-language · docs.cloud.google.com/logging/docs/logs-based-metrics · docs.cloud.google.com/logging/docs/structured-logging

# Google Cloud Logging — Structured logging & severity

Emit logs Cloud Logging can index + search, and alert by severity.

A JSON object lands in `jsonPayload` (path-queryable, select fields indexable); a string lands in `textPayload` (searchable, not path-indexed). For agent-collected services (Cloud Run, GKE, App Engine, Functions), write ONE serialized JSON object per line to stdout/stderr — a JSON-*looking* string that isn't valid still lands in `textPayload`. Client libraries set these directly instead.

## Special fields promoted to the LogEntry
Keys lifted from `jsonPayload` to top-level `LogEntry` fields (optional; `.../` = `logging.googleapis.com/`):
- `severity` → severity; `message` → display text (put stack traces here so Error Reporting groups them)
- `httpRequest` → httpRequest (method, status, latency); `time`/`timestamp` → timestamp
- `.../trace` → trace — MUST be `projects/PROJECT_ID/traces/TRACE_ID` to group a request
- `.../spanId` → spanId; `.../trace_sampled` → traceSampled (bool); `.../insertId` → insertId (dedup + ordering)
- `.../labels` → labels (indexed string map); `.../operation` → operation; `.../sourceLocation` → sourceLocation

## Severity (LogSeverity enum)
DEFAULT(0) DEBUG(100) INFO(200) NOTICE(300) WARNING(400) ERROR(500) CRITICAL(600) ALERT(700) EMERGENCY(800). Map your app level (and encodings like Java FINE/FINER) onto these yourself; DEFAULT applies only when `severity` is omitted, and values outside the enum are undefined. Set the prod threshold by env (INFO/WARN prod, DEBUG dev).

DO emit one JSON object per event with `severity`, a `message`, and a correlation id (prefer `.../trace` + `spanId`, queryable as `trace=...`).
DO push bounded selectors (request_id, tenant, route) into `.../labels` — labels are indexed; deep `jsonPayload` paths are not.
DON'T log secrets/PII/tokens — payloads are queryable and exported by sinks.
DON'T rely on case-insensitive keys: `jsonPayload.userId` ≠ `jsonPayload.user_id` (only severity + operators are case-insensitive).
DON'T dump large blobs — an entry has a size cap; oversized entries are rejected/truncated.

## Example structured log line (stdout)
```json
{"severity":"ERROR","message":"charge failed: gateway timeout","logging.googleapis.com/trace":"projects/PROJECT_ID/traces/06796866738c859f2f19b7cfb3214824","logging.googleapis.com/spanId":"000000000000004a","logging.googleapis.com/labels":{"request_id":"a1b2c3","route":"/v1/charge"},"httpRequest":{"requestMethod":"POST","status":504},"attempt":2}
```

## Querying it (full query syntax: logging-query-language.md)
```
resource.type="cloud_run_revision"
severity>="ERROR"
jsonPayload.attempt>=2
labels.request_id="a1b2c3"      -- from .../labels
trace="projects/PROJECT_ID/traces/06796866738c859f2f19b7cfb3214824"
httpRequest.status>=500 AND jsonPayload.message=~"timeout"
```
Counter/distribution metric + alert from a filter: sinks-metrics-and-alerts.md.

## Sources
docs.cloud.google.com/logging/docs/structured-logging · docs.cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry · docs.cloud.google.com/logging/docs/view/logging-query-language

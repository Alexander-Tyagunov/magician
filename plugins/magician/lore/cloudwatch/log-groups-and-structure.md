# Amazon CloudWatch Logs — Log groups and structure

Query language: **CloudWatch Logs Insights QL** (pipe-delimited: `cmd | cmd`). Structured JSON is auto-discovered; EMF turns JSON logs into metrics. Verified 2026 against docs.aws.amazon.com.

## Hierarchy
- **Log stream** = ordered events from ONE source (one instance/container/function). No cap on streams per group.
- **Log group** = set of streams sharing retention, access control (IAM/tags), metric filters, and subscriptions. Access to streams is controlled at the group level.
- DO name groups by app + env, e.g. `/myapp/prod/api`; group per service+environment so retention/access/alarms differ cleanly. Tag with `Environment`, `Owner`, `Application` (used for cost allocation + tag-based IAM).
- DON'T rely on stream names for filtering across a fleet — query the group; use fields inside events instead.

## Retention & log class
- Default retention is **Never Expire** — always set one (1 day … 10 years). Deletion lags up to ~72h after expiry.
- **Standard** log class: full feature set. **Infrequent Access** (IA): cheaper ingest but QL `pattern`, `diff`, and `unmask` are NOT supported, and it lacks some features (metric filters, subscription filters, Live Tail). Pick class per group at creation.

## Structured events (make queries exact)
- Emit ONE JSON object per event. Insights auto-discovers fields; nested JSON flattens with **dot notation** (`user.id`), arrays by index (`items.0`).
- System fields: `@timestamp`, `@message` (raw), `@logStream`, `@log` (group id), `@ingestionTime`. `@timestamp` = the event's own `timestamp` member (set by the producer at PutLogEvents); `@ingestionTime` = when CloudWatch Logs received the event.
- DO include stable keys: `level`, `msg`, `service`, `env`, and a correlation id (`requestId`/`traceId`) on every line so you can pivot a whole flow.
- DON'T log multi-line or non-JSON blobs — you lose auto-discovery and must fall back to `parse`.

## Metrics & traces from logs
- **EMF**: add an `_aws.CloudWatchMetrics` block and CloudWatch extracts metrics from the same JSON log — no separate PutMetricData. See `lore/cloudwatch/emf-metrics-and-alarms.md`.
- **X-Ray / Application Signals**: propagate the trace id into a JSON field (e.g. `traceId`) so you can filter logs by it and pivot logs↔traces in the console.

## Valid Insights examples
```
fields @timestamp, @message, level, requestId
| filter level = "ERROR"
| sort @timestamp desc
| limit 25
```
```
filter @message like /Exception/
| stats count(*) as exceptionCount by bin(1h)
| sort exceptionCount desc
```
```
fields @timestamp, msg, level
| filter requestId = "abc-123"
| sort @timestamp asc
```
Deep query patterns (stats, percentiles, timeseries): `lore/cloudwatch/logs-insights-queries.md`.

## Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html

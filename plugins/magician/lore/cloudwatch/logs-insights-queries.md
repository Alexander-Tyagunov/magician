# Amazon CloudWatch Logs — Logs Insights queries

Query language: Logs Insights QL — pipe `|`-separated commands (`fields`, `filter`, `stats`, `sort`, …). System fields (Standard class): `@timestamp`, `@message` (raw), `@ingestionTime`, `@logStream`, `@log` (`account:group`). JSON auto-flattens to dot fields (≤200/event); `parse` for the rest.

## DO
- Narrow the time range; select only needed log groups — scan drives cost/latency.
- `filter` before `stats`/`sort` to cut scanned rows; `sort`/`limit` AFTER the last `stats`.
- Query fields by dot notation (`ctx.requestId`, `http.status`), not raw `@message`.
- Filter on a propagated correlation id to trace one flow.
- Alias aggregates (`as p99`); `sort`/`filter` by the alias.
- `bin(<n>m)`+`stats` for time series; `pct()` for tail latency.

## DON'T
- Reference `@message` after a `stats` — only fields in that `stats` survive downstream.
- Use `bin(300s)` — `s` caps at 60; write `bin(5m)`. (`ms`≤1000, `s`/`m`≤60, `h`≤24.)
- Free-text scan `@message` when a structured field exists — slower, costlier.

## Find errors
```
fields @timestamp, level, msg, ctx.requestId, @logStream
| filter level = "ERROR"
| sort @timestamp desc
| limit 50
```
Free-text, case-insensitive RE2 regex:
```
fields @timestamp, @message
| filter @message like /(?i)(error|exception|timeout|failed)/
| sort @timestamp desc
| limit 100
```

## Trace one request
```
fields @timestamp, level, msg, http.status, durationMs
| filter ctx.requestId = "b1e2-…"
| sort @timestamp asc
```

## Error rate + top offenders
```
filter level = "ERROR"
| stats count(*) as errors, count_distinct(ctx.userId) as users by errorCode, bin(5m)
| sort errors desc
```

## Latency percentiles per route
```
filter ispresent(durationMs)
| stats avg(durationMs) as avg, pct(durationMs,95) as p95,
        pct(durationMs,99) as p99, max(durationMs) as mx by route
| sort p99 desc
```

## Extract fields from raw lines
```
parse @message "status=* dur=*ms" as status, dur
| filter status >= 500
| stats count(*) as fails by status
```

## Lambda + X-Ray correlation
Lambda logs expose `@requestId`, `@duration`, `@billedDuration`, `@maxMemoryUsed`; `@xrayTraceId`/`@xraySegmentId` when present.
```
filter @type = "REPORT"
| stats avg(@duration) as avg, pct(@duration,99) as p99, max(@maxMemoryUsed) as mem by bin(30m)
```
Pivot to the X-Ray trace via `@xrayTraceId` (X-Ray console/ServiceLens).

Aggregations: `count`, `count_distinct`, `sum`, `avg`, `min`, `max`, `pct`, `stddev`, `values`; non-agg `earliest`/`latest`. Standard class allows ≤10 `stats`/query.

Log group/stream layout, retention, field indexes: lore/cloudwatch/log-groups-and-structure.md. EMF extraction, metric filters, alarms: lore/cloudwatch/emf-metrics-and-alarms.md.

## Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-operations-functions.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-Stats.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_AnalyzeLogData-discoverable-fields.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html

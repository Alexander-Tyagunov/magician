# Amazon CloudWatch Logs — deep dive

> On-demand companion to `lore/cloudwatch.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Logs Insights queries](#logs-insights-queries) · [Log groups and structure](#log-groups-and-structure) · [EMF Metrics & Alarms](#emf-metrics-and-alarms)

## Logs Insights queries <a id="logs-insights-queries"></a>

Query language: Logs Insights QL — pipe `|`-separated commands (`fields`, `filter`, `stats`, `sort`, …). System fields (Standard class): `@timestamp`, `@message` (raw), `@ingestionTime`, `@logStream`, `@log` (`account:group`). JSON auto-flattens to dot fields (≤200/event); `parse` for the rest.

### DO
- Narrow the time range; select only needed log groups — scan drives cost/latency.
- `filter` before `stats`/`sort` to cut scanned rows; `sort`/`limit` AFTER the last `stats`.
- Query fields by dot notation (`ctx.requestId`, `http.status`), not raw `@message`.
- Filter on a propagated correlation id to trace one flow.
- Alias aggregates (`as p99`); `sort`/`filter` by the alias.
- `bin(<n>m)`+`stats` for time series; `pct()` for tail latency.

### DON'T
- Reference `@message` after a `stats` — only fields in that `stats` survive downstream.
- Use `bin(300s)` — `s` caps at 60; write `bin(5m)`. (`ms`≤1000, `s`/`m`≤60, `h`≤24.)
- Free-text scan `@message` when a structured field exists — slower, costlier.

### Find errors
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

### Trace one request
```
fields @timestamp, level, msg, http.status, durationMs
| filter ctx.requestId = "b1e2-…"
| sort @timestamp asc
```

### Error rate + top offenders
```
filter level = "ERROR"
| stats count(*) as errors, count_distinct(ctx.userId) as users by errorCode, bin(5m)
| sort errors desc
```

### Latency percentiles per route
```
filter ispresent(durationMs)
| stats avg(durationMs) as avg, pct(durationMs,95) as p95,
        pct(durationMs,99) as p99, max(durationMs) as mx by route
| sort p99 desc
```

### Extract fields from raw lines
```
parse @message "status=* dur=*ms" as status, dur
| filter status >= 500
| stats count(*) as fails by status
```

### Lambda + X-Ray correlation
Lambda logs expose `@requestId`, `@duration`, `@billedDuration`, `@maxMemoryUsed`; `@xrayTraceId`/`@xraySegmentId` when present.
```
filter @type = "REPORT"
| stats avg(@duration) as avg, pct(@duration,99) as p99, max(@maxMemoryUsed) as mem by bin(30m)
```
Pivot to the X-Ray trace via `@xrayTraceId` (X-Ray console/ServiceLens).

Aggregations: `count`, `count_distinct`, `sum`, `avg`, `min`, `max`, `pct`, `stddev`, `values`; non-agg `earliest`/`latest`. Standard class allows ≤10 `stats`/query.

Log group/stream layout, retention, field indexes: lore/deep/cloudwatch.md#log-groups-and-structure. EMF extraction, metric filters, alarms: lore/deep/cloudwatch.md#emf-metrics-and-alarms.

### Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-operations-functions.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-Stats.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_AnalyzeLogData-discoverable-fields.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html

## Log groups and structure <a id="log-groups-and-structure"></a>

Query language: **CloudWatch Logs Insights QL** (pipe-delimited: `cmd | cmd`). Structured JSON is auto-discovered; EMF turns JSON logs into metrics. Verified 2026 against docs.aws.amazon.com.

### Hierarchy
- **Log stream** = ordered events from ONE source (one instance/container/function). No cap on streams per group.
- **Log group** = set of streams sharing retention, access control (IAM/tags), metric filters, and subscriptions. Access to streams is controlled at the group level.
- DO name groups by app + env, e.g. `/myapp/prod/api`; group per service+environment so retention/access/alarms differ cleanly. Tag with `Environment`, `Owner`, `Application` (used for cost allocation + tag-based IAM).
- DON'T rely on stream names for filtering across a fleet — query the group; use fields inside events instead.

### Retention & log class
- Default retention is **Never Expire** — always set one (1 day … 10 years). Deletion lags up to ~72h after expiry.
- **Standard** log class: full feature set. **Infrequent Access** (IA): cheaper ingest but QL `pattern`, `diff`, and `unmask` are NOT supported, and it lacks some features (metric filters, subscription filters, Live Tail). Pick class per group at creation.

### Structured events (make queries exact)
- Emit ONE JSON object per event. Insights auto-discovers fields; nested JSON flattens with **dot notation** (`user.id`), arrays by index (`items.0`).
- System fields: `@timestamp`, `@message` (raw), `@logStream`, `@log` (group id), `@ingestionTime`. `@timestamp` = the event's own `timestamp` member (set by the producer at PutLogEvents); `@ingestionTime` = when CloudWatch Logs received the event.
- DO include stable keys: `level`, `msg`, `service`, `env`, and a correlation id (`requestId`/`traceId`) on every line so you can pivot a whole flow.
- DON'T log multi-line or non-JSON blobs — you lose auto-discovery and must fall back to `parse`.

### Metrics & traces from logs
- **EMF**: add an `_aws.CloudWatchMetrics` block and CloudWatch extracts metrics from the same JSON log — no separate PutMetricData. See `lore/deep/cloudwatch.md#emf-metrics-and-alarms`.
- **X-Ray / Application Signals**: propagate the trace id into a JSON field (e.g. `traceId`) so you can filter logs by it and pivot logs↔traces in the console.

### Valid Insights examples
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
Deep query patterns (stats, percentiles, timeseries): `lore/deep/cloudwatch.md#logs-insights-queries`.

### Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html

## EMF Metrics & Alarms <a id="emf-metrics-and-alarms"></a>

EMF (embedded metric format) is a JSON log event whose `_aws` root node makes CloudWatch Logs auto-extract metrics at ingest — one event carries both the structured log AND the metric, no PutMetricData call. Metrics feed CloudWatch Alarms; X-Ray carries traces. Event limit 1 MB.

### DO
- Put a valid `_aws` object at the root; CloudWatch extracts each `Metrics[].Name` that also exists as a top-level member.
- Keep dimensions low-cardinality. Each distinct DimensionSet combo creates a NEW custom metric (billed). Use `Operation`/`Service`/`Environment` — never `requestId`/`userId`.
- Limits: <=100 metrics per directive, <=30 dimension keys per DimensionSet, metric value = a number or numeric array (<=100 members).
- Set `StorageResolution`: `1` = high-res (1s), `60` = standard (1m, default). Use a valid `Unit` (`Milliseconds`, `Count`, `Bytes`, ...).
- Prefer EMF over metric filters in your own code — EMF gives percentiles + high resolution; filters only re-scan ingested logs.
- For high-res metrics you alarm on, flush logs <=5s (CloudWatch agent `force_flush_interval`, default 5s) so datapoints land in the alarm period.
- Emit a trace/correlation id in every event; X-Ray generates trace IDs across components. Lambda logs surface `@xrayTraceId`/`@xraySegmentId` to join logs to traces.

### DON'T
- DON'T nest metric/dimension targets — they must be root members; `{"A":{"a":...}}` silently won't extract.
- DON'T dimension on high-cardinality fields — cost explosion (one metric per unique value).
- DON'T alarm on a single datapoint for sparse EMF metrics; they flap.
- DON'T log secrets/PII — the EMF event is a normal log too.

### Valid EMF event
```json
{
  "_aws": {
    "Timestamp": 1574109732004,
    "CloudWatchMetrics": [{
      "Namespace": "OrderService",
      "Dimensions": [["Operation"]],
      "Metrics": [
        {"Name": "Latency", "Unit": "Milliseconds", "StorageResolution": 60},
        {"Name": "Faults", "Unit": "Count"}
      ]
    }]
  },
  "Operation": "Checkout",
  "Latency": 42.3,
  "Faults": 0,
  "requestId": "989ffbf8-9ace-4817-a57c-e4dd734019ee"
}
```
Members not named in a metric/dimension (`requestId`) ride along as plain log data.

### Alarms
Datapoints depend on log-publish timing.
- Set `treatMissingData` deliberately (e.g. `notBreaching`) for gappy metrics.
- Can't control flush cadence (Lambda)? Use "M out of N": datapoints-to-alarm < evaluation-periods so partial data doesn't false-alarm.
- Watch the `AWS/Logs` namespace for EMF parse/validation failures (metrics drop if JSON is malformed).

### Verify emission (Logs Insights)
```
fields @timestamp, Operation, Latency, Faults
| filter ispresent(Latency) and Faults > 0
| stats count(*) as faults, avg(Latency) as avgMs, pct(Latency, 95) as p95 by Operation, bin(5m)
| sort faults desc
```
Queries → `lore/deep/cloudwatch.md#logs-insights-queries`; log groups/streams/retention → `lore/deep/cloudwatch.md#log-groups-and-structure`.

### Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Alarms.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/x-ray.html

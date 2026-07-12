# Amazon CloudWatch Logs — EMF Metrics & Alarms

EMF (embedded metric format) is a JSON log event whose `_aws` root node makes CloudWatch Logs auto-extract metrics at ingest — one event carries both the structured log AND the metric, no PutMetricData call. Metrics feed CloudWatch Alarms; X-Ray carries traces. Event limit 1 MB.

## DO
- Put a valid `_aws` object at the root; CloudWatch extracts each `Metrics[].Name` that also exists as a top-level member.
- Keep dimensions low-cardinality. Each distinct DimensionSet combo creates a NEW custom metric (billed). Use `Operation`/`Service`/`Environment` — never `requestId`/`userId`.
- Limits: <=100 metrics per directive, <=30 dimension keys per DimensionSet, metric value = a number or numeric array (<=100 members).
- Set `StorageResolution`: `1` = high-res (1s), `60` = standard (1m, default). Use a valid `Unit` (`Milliseconds`, `Count`, `Bytes`, ...).
- Prefer EMF over metric filters in your own code — EMF gives percentiles + high resolution; filters only re-scan ingested logs.
- For high-res metrics you alarm on, flush logs <=5s (CloudWatch agent `force_flush_interval`, default 5s) so datapoints land in the alarm period.
- Emit a trace/correlation id in every event; X-Ray generates trace IDs across components. Lambda logs surface `@xrayTraceId`/`@xraySegmentId` to join logs to traces.

## DON'T
- DON'T nest metric/dimension targets — they must be root members; `{"A":{"a":...}}` silently won't extract.
- DON'T dimension on high-cardinality fields — cost explosion (one metric per unique value).
- DON'T alarm on a single datapoint for sparse EMF metrics; they flap.
- DON'T log secrets/PII — the EMF event is a normal log too.

## Valid EMF event
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

## Alarms
Datapoints depend on log-publish timing.
- Set `treatMissingData` deliberately (e.g. `notBreaching`) for gappy metrics.
- Can't control flush cadence (Lambda)? Use "M out of N": datapoints-to-alarm < evaluation-periods so partial data doesn't false-alarm.
- Watch the `AWS/Logs` namespace for EMF parse/validation failures (metrics drop if JSON is malformed).

## Verify emission (Logs Insights)
```
fields @timestamp, Operation, Latency, Faults
| filter ispresent(Latency) and Faults > 0
| stats count(*) as faults, avg(Latency) as avgMs, pct(Latency, 95) as p95 by Operation, bin(5m)
| sort faults desc
```
Queries → `lore/cloudwatch/logs-insights-queries.md`; log groups/streams/retention → `lore/cloudwatch/log-groups-and-structure.md`.

## Sources
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Alarms.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/cloudwatch-logs.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/x-ray.html

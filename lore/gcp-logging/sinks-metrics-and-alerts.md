# Google Cloud Logging — Sinks, Log-Based Metrics & Alerts

Turn logs into routing, metrics, and alerts. Sink/metric/alert **filters all use the Logging query language** (same syntax as Logs Explorer); creation is done with `gcloud logging` / `gcloud monitoring` or the API. Structured `jsonPayload` fields and `severity` are what you filter and extract on, so log clean structured events first (see structured-logging-and-severity.md).

## Sinks (routing/export)
Every project has two managed sinks: `_Required` (audit Admin Activity/system logs — can't disable or delete) and `_Default` (everything else → `_Default` bucket — can disable, can't delete). Add your own sinks to route matching entries to: a log bucket, BigQuery dataset, Cloud Storage bucket, Pub/Sub topic (for Splunk/third-party), or another project (one-hop).

DO create a sink with an inclusion filter (Logging query language):
```
gcloud logging sinks create errors-to-bq \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/DATASET_ID \
  --log-filter='severity>=ERROR AND resource.type="cloud_run_revision"'
```
DO add exclusions (repeatable `--exclusion`) to drop noisy high-volume logs, and grant the sink's writer identity write access on the destination after create.
DON'T route a firehose to BigQuery/Storage without a filter — you pay to store noise. DON'T forget: user-defined log-based **metrics count both included and excluded logs**, but sinks only route included ones.

## Log-based metrics
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

## Alerts
Two paths: **log-based alert (LogMatch)** fires per matching entry — good for "this message appeared"; exactly one condition, `combiner="OR"`, ignores excluded logs. **Metric-based** alerts on a log-based metric — good for rates/thresholds ("errors > N in 5m").
```
gcloud monitoring policies create --policy-from-file=alert-policy.json
```
The LogMatch condition query is Logging query language, e.g. `severity=ERROR AND jsonPayload.event="payment_failed"`. DO set `notificationRateLimit` + `autoClose` (min 1800s) so one bad deploy doesn't storm you. DON'T use log-based alerts to count — use a metric-based policy on a counter metric for thresholds.

## Sources
- docs.cloud.google.com/logging/docs/export/configure_export_v2
- docs.cloud.google.com/logging/docs/logs-based-metrics (+ /counter-metrics)
- docs.cloud.google.com/logging/docs/alerting/log-based-alerts

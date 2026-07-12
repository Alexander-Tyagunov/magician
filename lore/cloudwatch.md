# Amazon CloudWatch Logs — core digest
Context: log groups→streams + Logs Insights. Query langs: Logs Insights QL (default), OpenSearch PPL/SQL. Metrics via EMF/metric filters+alarms; traces in X-Ray.

DO emit one structured JSON event per action — top-level keys become discovered fields (level, requestId, durationMs).
DO set log-group retention (1 day–10 yrs); default Never-expire → unbounded cost.
DO set the level threshold by env (DEBUG dev, INFO/WARN prod), never hardcoded.
DO propagate a correlation/requestId so one query reconstructs the flow.
DO publish metrics via EMF (_aws.CloudWatchMetrics), not log scans; alarm on them.
DO find errors: `fields @timestamp,@message | filter level="ERROR" | sort @timestamp desc | limit 50`.
DO trace: `filter requestId="abc-123" | sort @timestamp asc`.
DO rate: `filter level="ERROR" | stats count(*) as errs by bin(5m)`.

DON'T log secrets/PII/tokens — logs are searchable and long-lived.
DON'T make EMF dimensions high-cardinality (e.g. requestId) — one metric per value.
DON'T leak SPL/KQL/LogQL syntax into QL, or invent operators.
DON'T print per-line in hot loops.

Deep dive when writing non-trivial CloudWatch — read lore/cloudwatch/{logs-insights-queries,log-groups-and-structure,emf-metrics-and-alarms}.md

## Sources
docs.aws.amazon.com: CWL_AnalyzeLogData_Languages, CWL_Insights-Sample-Queries, Embedded_Metric_Format_Specification; prescriptive-guidance/logging-monitoring-for-application-owners

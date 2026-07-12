# Grafana + Loki — Labels and Cardinality

Grafana visualizes many sources; for LOGS the store is Loki and the query language is LogQL (verified against Loki 3.x docs). Loki does NOT index log content — it indexes only LABELS. Each unique set of label key=value pairs is a STREAM; queries first select streams, then grep/parse lines inside them. Cardinality = the number of unique label-value combinations (streams). High cardinality is the #1 way to make Loki slow and expensive: it builds a huge index and flushes many tiny chunks. Siblings: Tempo (traces), Mimir/Prometheus (metrics).

## DO
- DO keep labels FEW and BOUNDED — aim 10-15 max (Loki default limit is 15 index labels). Every added label multiplies stream count.
- DO use labels for low-cardinality, long-lived query dimensions: `service_name`, `env`, `namespace`, `cluster`, `job`, `level` (bounded set), `region`.
- DO put HIGH-cardinality fields (trace_id, request_id, user_id, pod name, ip, process_id) in STRUCTURED METADATA, not labels. It attaches per-line metadata without indexing and needs NO parser at query time.
- DO name labels to match the regex `[a-zA-Z_:][a-zA-Z0-9_:]*`; unsupported chars become `_`. Loki auto-sets `service_name` (falls back through service/app/job, else `unknown_service`).
- DO extract fields at QUERY time with parsers (`| json`, `| logfmt`, `| pattern`, `| regexp`) instead of promoting them to labels.

## DON'T
- DON'T label unbounded values (timestamps, IPs, IDs, full URLs, durations) — thousands/millions of streams.
- DON'T over-label even bounded fields: 4 actions x 4 status codes = 16 streams; add one `ip` label and it explodes.
- DON'T put the log message, exception name, or free text in a label.
- DON'T rely on labels for rare/one-off searches (customer ID) — filter lines or query structured metadata instead.

## Query examples (LogQL — grounded)
Select streams + line filter (grep): `{app="mysql"} |= "error" != "timeout"`
Regex line filter (RE2, backticks avoid escaping): `` {job="api"} |~ `status=5\d\d` ``
Parse JSON then label-filter numerically: `{container="frontend"} | json | duration > 10s and throughput_mb < 500`
Query structured metadata (no parser): `{job="app"} | trace_id="0242ac120002" | keep job`

Metric queries for alerting (Explore + Grafana alerting):
Error rate by host: `sum by (host) (rate({job="mysql"} |= "error" | json [1m]))`
Count over window, safe empty value: `sum(count_over_time({namespace="api"}[5m])) or vector(0)`
`by` keeps only listed labels; `without` drops listed ones; `topk(k, ...)` needs a parameter. Reduce result-series errors with `| keep`/`| drop`.

Deep siblings: lore/grafana/loki-and-logql.md, lore/grafana/explore-dashboards-and-alerting.md.

## Sources
- https://grafana.com/docs/loki/latest/get-started/labels/
- https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/
- https://grafana.com/docs/loki/latest/query/log_queries/
- https://grafana.com/docs/loki/latest/query/metric_queries/

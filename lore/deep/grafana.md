# Grafana + Loki — deep dive

> On-demand companion to `lore/grafana.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Loki and LogQL](#loki-and-logql) · [Labels and Cardinality](#labels-and-cardinality) · [Explore, Dashboards, and Alerting](#explore-dashboards-and-alerting)

## Loki and LogQL <a id="loki-and-logql"></a>

Grafana is the viewer over many sources; for LOGS the store is **Loki**, queried in **LogQL** (label-indexed — "grep for logs, PromQL for metrics"). Traces live in **Tempo**, metrics in **Mimir/Prometheus** — correlate in **Explore**. Verify against Loki 3.x docs; LogQL is current.

### Anatomy: `{stream selector} | pipeline`
The `{…}` selector is **mandatory** (≥1 matcher); the pipeline (filters → parsers → label filters → formatters) is optional, left-to-right. Loki indexes only labels — the selector picks streams; everything after `|` runs at query time.

### Shape logs so Loki can query them
- DO keep **labels low-cardinality and bounded** (app, env, namespace, level) — they are the index. Put ids/user/path in the **log line** (JSON) or **structured metadata**, both queryable via label filters. Depth: lore/deep/grafana.md#labels-and-cardinality.
- DO emit **one structured JSON event per action** with a `trace_id`/`request_id`, then `| json` and filter it to trace a flow across services.
- DON'T bake high-cardinality values (ids, timestamps) into labels — it explodes streams and slows every query.

### Find — selectors + line filters
Label matchers: `=` `!=` `=~` `!~` (regex **fully anchored**). Line filters on the raw line: `|=` contains, `!=` not, `|~` regex, `!~` regex-not — **unanchored**; put first for speed; `(?i)` for case-insensitive; backticks avoid escaping.
```logql
{namespace="prod", app=~"checkout|cart"} |= "error" != "timeout"
{job="nginx"} |~ `(?i)status=(5\d\d)`
```

### Refine — parsers + label filters
Parsers extract fields to labels: `json`, `logfmt`, `pattern`, `regexp`, `unpack`. Label filters then compare typed values (String, **Duration**, **Bytes**, Number) with `==`/`!=`/`>`/`>=`/`<`/`<=`, chained by `and`/`or`.
```logql
{app="api"} | json | level="error" and duration > 500ms
{app="api"} | logfmt | status>=500 or bytes>20MB
```
`| line_format "{{.method}} {{.path}}"` rewrites output; `| label_format route="{{.path}}"` renames/derives labels (results only, never source).

### Trace a request end-to-end
```logql
{namespace="prod"} | json | trace_id="7f3a9c2e" | line_format "{{.service}} {{.msg}}"
```

### Metric queries — rate, aggregate, quantile
Log-range aggregations over `[range]`: `rate`, `count_over_time`, `bytes_rate`, `bytes_over_time`; aggregate with `sum/avg/max/min/count/topk/bottomk` + `by`/`without`. Error rate per service, top talkers, p95 latency (`offset`, if used, follows the range immediately):
```logql
sum by (service) (rate({namespace="prod"} | json | level="error" [5m]))
topk(10, sum by (host) (rate({job="mysql"}[5m])))
quantile_over_time(0.95, {app="api"} | json | unwrap duration(latency) [5m]) by (route)
```

### Explore + alerting
Use **Grafana Explore** for ad-hoc LogQL, live tail, and log↔trace correlation; metric queries drive dashboards and **Grafana alerting** (e.g. `sum(rate({app="api"} |= "error" [5m])) > N`). Depth: lore/deep/grafana.md#explore-dashboards-and-alerting.

### Gotchas
- DON'T write an unbounded `{app=~".+"}` scan — pin real labels and a time range.
- DON'T `| json` huge payloads for one field — a leading `|= "trace_id"` prunes lines cheaply first.
- DON'T confuse selector regex (anchored) with line-filter regex (unanchored); a substring `|=` beats `|~`.

### Sources
- grafana.com/docs/loki/latest/query/
- grafana.com/docs/loki/latest/query/log_queries/
- grafana.com/docs/loki/latest/query/metric_queries/

## Labels and Cardinality <a id="labels-and-cardinality"></a>

Grafana visualizes many sources; for LOGS the store is Loki and the query language is LogQL (verified against Loki 3.x docs). Loki does NOT index log content — it indexes only LABELS. Each unique set of label key=value pairs is a STREAM; queries first select streams, then grep/parse lines inside them. Cardinality = the number of unique label-value combinations (streams). High cardinality is the #1 way to make Loki slow and expensive: it builds a huge index and flushes many tiny chunks. Siblings: Tempo (traces), Mimir/Prometheus (metrics).

### DO
- DO keep labels FEW and BOUNDED — aim 10-15 max (Loki default limit is 15 index labels). Every added label multiplies stream count.
- DO use labels for low-cardinality, long-lived query dimensions: `service_name`, `env`, `namespace`, `cluster`, `job`, `level` (bounded set), `region`.
- DO put HIGH-cardinality fields (trace_id, request_id, user_id, pod name, ip, process_id) in STRUCTURED METADATA, not labels. It attaches per-line metadata without indexing and needs NO parser at query time.
- DO name labels to match the regex `[a-zA-Z_:][a-zA-Z0-9_:]*`; unsupported chars become `_`. Loki auto-sets `service_name` (falls back through service/app/job, else `unknown_service`).
- DO extract fields at QUERY time with parsers (`| json`, `| logfmt`, `| pattern`, `| regexp`) instead of promoting them to labels.

### DON'T
- DON'T label unbounded values (timestamps, IPs, IDs, full URLs, durations) — thousands/millions of streams.
- DON'T over-label even bounded fields: 4 actions x 4 status codes = 16 streams; add one `ip` label and it explodes.
- DON'T put the log message, exception name, or free text in a label.
- DON'T rely on labels for rare/one-off searches (customer ID) — filter lines or query structured metadata instead.

### Query examples (LogQL — grounded)
Select streams + line filter (grep): `{app="mysql"} |= "error" != "timeout"`
Regex line filter (RE2, backticks avoid escaping): `` {job="api"} |~ `status=5\d\d` ``
Parse JSON then label-filter numerically: `{container="frontend"} | json | duration > 10s and throughput_mb < 500`
Query structured metadata (no parser): `{job="app"} | trace_id="0242ac120002" | keep job`

Metric queries for alerting (Explore + Grafana alerting):
Error rate by host: `sum by (host) (rate({job="mysql"} |= "error" | json [1m]))`
Count over window, safe empty value: `sum(count_over_time({namespace="api"}[5m])) or vector(0)`
`by` keeps only listed labels; `without` drops listed ones; `topk(k, ...)` needs a parameter. Reduce result-series errors with `| keep`/`| drop`.

Deep siblings: lore/deep/grafana.md#loki-and-logql, lore/deep/grafana.md#explore-dashboards-and-alerting.

### Sources
- https://grafana.com/docs/loki/latest/get-started/labels/
- https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/
- https://grafana.com/docs/loki/latest/query/log_queries/
- https://grafana.com/docs/loki/latest/query/metric_queries/

## Explore, Dashboards, and Alerting <a id="explore-dashboards-and-alerting"></a>

Grafana visualizes many sources; for LOGS the store is **Loki**, queried in **LogQL** (syntax: lore/deep/grafana.md#loki-and-logql; index: lore/deep/grafana.md#labels-and-cardinality). Workflow layer: **Explore** = ad-hoc, **dashboards** = curated panels, **alerting** = conditions. Traces=**Tempo**, metrics=**Mimir/Prometheus**; correlate all three in Explore. Verify against Grafana 12 / Loki 3.x docs.

### Explore — ad-hoc investigation
- DO start queryless in **Grafana Logs Drilldown** (formerly "Explore Logs"): filter by **labels, fields, or patterns** with no LogQL — it auto-generates panels, groups noisy lines into patterns, and links out to Explore.
- DO drop into **Explore** to write LogQL, use **Live** for real-time tailing, and **Show context** for ±N surrounding lines (like `grep -C`) — then **Open in split view**.
- DO click fields in **Log details** as filters — grouped as **Indexed labels**, **Parsed fields**, **Structured metadata**. Switching a metrics-source query to Loki keeps matching labels (`m{job="api"}` → `{job="api"}`).

### Dashboards — curated panels
- DO use the **Logs panel** for raw lines (log query); **Time series/Stat** panels need a **metric query** (`rate`, `count_over_time`, …).
- DO parameterize via `label_values(app)` template variables; pin a range; annotate deploys.
```logql
# Time series panel: 5xx rate per route
sum by (route) (rate({namespace="prod",app="api"} | json | status>=500 [5m]))
```

### Alerting — from a LogQL metric query
A **Grafana-managed alert rule** = one or more **queries and expressions** + an **alert condition**. A Loki logs query must reduce to a single numeric value, so chain expressions:
- **A** — metric query: `sum(rate({app="api"} |= "error" [5m]))`
- **B** — **Reduce** expression (series → one number, e.g. function **Last**) on A.
- **C** — **Threshold** expression on B (e.g. `IS ABOVE 0.5`); set **C** as the alert condition.

- Expression types: **Reduce**, **Math**, **Resample**, **Threshold**. Avoid **Classic condition (legacy)**.
- DO group by a label for one **alert instance per dimension**: `sum by (service) (rate({namespace="prod"} | json | level="error" [5m]))`.
- DO guard empty results so absent logs don't misfire: `sum(count_over_time({app="api"} |= "error" [5m])) or vector(0)` (No Data/Error are Grafana-managed only).
- DO set an **evaluation group** + **interval** and a **pending period** — the instance goes **Normal → Pending → Alerting** only if the breach persists (prevents flap on a transient spike); **keep firing for** holds it **Recovering** so brief recoveries don't re-notify.
- DO route via **contact points** + **notification policies** (label-matching tree); tune with **notification grouping**, **silences**, **mute timings**.

### DON'T
- DON'T alert on a raw log/range query — it returns a series, not a number; always Reduce → Threshold.
- DON'T set the evaluation interval below the query `[range]`, or a pending period below one interval.
- DON'T build panels over unbounded `{app=~".+"}` scans — pin real labels and a range.

### Sources
- grafana.com/docs/grafana/latest/explore/logs-integration/ (tail, context, split view, details)
- grafana.com/docs/grafana/latest/explore/simplified-exploration/logs/ (Grafana Logs Drilldown)
- grafana.com/docs/grafana/latest/alerting/fundamentals/ (+ alert-rules/queries-conditions/, alert-rule-evaluation/)

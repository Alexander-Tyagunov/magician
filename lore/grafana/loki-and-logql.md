# Grafana + Loki — Loki and LogQL

Grafana is the viewer over many sources; for LOGS the store is **Loki**, queried in **LogQL** (label-indexed — "grep for logs, PromQL for metrics"). Traces live in **Tempo**, metrics in **Mimir/Prometheus** — correlate in **Explore**. Verify against Loki 3.x docs; LogQL is current.

## Anatomy: `{stream selector} | pipeline`
The `{…}` selector is **mandatory** (≥1 matcher); the pipeline (filters → parsers → label filters → formatters) is optional, left-to-right. Loki indexes only labels — the selector picks streams; everything after `|` runs at query time.

## Shape logs so Loki can query them
- DO keep **labels low-cardinality and bounded** (app, env, namespace, level) — they are the index. Put ids/user/path in the **log line** (JSON) or **structured metadata**, both queryable via label filters. Depth: lore/grafana/labels-and-cardinality.md.
- DO emit **one structured JSON event per action** with a `trace_id`/`request_id`, then `| json` and filter it to trace a flow across services.
- DON'T bake high-cardinality values (ids, timestamps) into labels — it explodes streams and slows every query.

## Find — selectors + line filters
Label matchers: `=` `!=` `=~` `!~` (regex **fully anchored**). Line filters on the raw line: `|=` contains, `!=` not, `|~` regex, `!~` regex-not — **unanchored**; put first for speed; `(?i)` for case-insensitive; backticks avoid escaping.
```logql
{namespace="prod", app=~"checkout|cart"} |= "error" != "timeout"
{job="nginx"} |~ `(?i)status=(5\d\d)`
```

## Refine — parsers + label filters
Parsers extract fields to labels: `json`, `logfmt`, `pattern`, `regexp`, `unpack`. Label filters then compare typed values (String, **Duration**, **Bytes**, Number) with `==`/`!=`/`>`/`>=`/`<`/`<=`, chained by `and`/`or`.
```logql
{app="api"} | json | level="error" and duration > 500ms
{app="api"} | logfmt | status>=500 or bytes>20MB
```
`| line_format "{{.method}} {{.path}}"` rewrites output; `| label_format route="{{.path}}"` renames/derives labels (results only, never source).

## Trace a request end-to-end
```logql
{namespace="prod"} | json | trace_id="7f3a9c2e" | line_format "{{.service}} {{.msg}}"
```

## Metric queries — rate, aggregate, quantile
Log-range aggregations over `[range]`: `rate`, `count_over_time`, `bytes_rate`, `bytes_over_time`; aggregate with `sum/avg/max/min/count/topk/bottomk` + `by`/`without`. Error rate per service, top talkers, p95 latency (`offset`, if used, follows the range immediately):
```logql
sum by (service) (rate({namespace="prod"} | json | level="error" [5m]))
topk(10, sum by (host) (rate({job="mysql"}[5m])))
quantile_over_time(0.95, {app="api"} | json | unwrap duration(latency) [5m]) by (route)
```

## Explore + alerting
Use **Grafana Explore** for ad-hoc LogQL, live tail, and log↔trace correlation; metric queries drive dashboards and **Grafana alerting** (e.g. `sum(rate({app="api"} |= "error" [5m])) > N`). Depth: lore/grafana/explore-dashboards-and-alerting.md.

## Gotchas
- DON'T write an unbounded `{app=~".+"}` scan — pin real labels and a time range.
- DON'T `| json` huge payloads for one field — a leading `|= "trace_id"` prunes lines cheaply first.
- DON'T confuse selector regex (anchored) with line-filter regex (unanchored); a substring `|=` beats `|~`.

## Sources
- grafana.com/docs/loki/latest/query/
- grafana.com/docs/loki/latest/query/log_queries/
- grafana.com/docs/loki/latest/query/metric_queries/

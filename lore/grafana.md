# Grafana + Loki — core digest
LOGS store: Loki 3.x, queried in LogQL (label-indexed). metrics=Mimir, traces=Tempo. Query/tail in Explore.

DO select streams by low-cardinality labels first: `{app="api",env="prod"}`.
DO filter lines early with `|=` `!=` `|~` `!~` (case-sensitive; `(?i)` for insensitive): `{app="api"} |= "error"`.
DO parse then filter fields: `{app="api"} | json | status>=500 and duration>1s` (also `| logfmt`, `| pattern`, `| regexp`).
DO measure errors with metric queries: `sum by (route) (rate({app="api"} |= "error" [5m]))`; volume via `count_over_time(...[5m])`.
DO trace a request via propagated id: `{env="prod"} | json | trace_id="abc123"`.
DO alert/record with the ruler using LogQL metric exprs; recording rules precompute hot queries.

DON'T make labels from high-cardinality values (user/request id, IP, timestamp) — parse at query time or use structured metadata; keep ~10-15 labels max.
DON'T assume line regex `|~`/`!~` is anchored (it isn't); label `=~`/`!~` is fully anchored.
DON'T scan without a stream selector or over huge time ranges — narrow labels + window first.

Deep dive for non-trivial Grafana/Loki: read lore/grafana/{loki-and-logql,labels-and-cardinality,explore-dashboards-and-alerting}.md

## Sources
grafana.com/docs/loki/latest/query/{log_queries,metric_queries} · get-started/labels · alert · grafana.com/docs/grafana/latest/explore

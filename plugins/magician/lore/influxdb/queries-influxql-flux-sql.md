# InfluxDB — Queries (InfluxQL / Flux / SQL)

Language by version — never mix dialects:
- **v1**: InfluxQL only.
- **v2**: Flux (native) + InfluxQL (1.x-compat API via a mapped DBRP).
- **v3** (Core/Enterprise, current 3.x, columnar/DataFusion): **SQL + InfluxQL**. **Flux is NOT supported in v3** — rewrite, don't port.

## v3 — SQL (Apache Arrow / DataFusion)
Tables = measurements; columns = `time`, tags, fields; double-quote keys with spaces/reserved words.
DO bound time in `WHERE`: `time >= now() - INTERVAL '1 hour'` or RFC3339 `time >= '2024-01-01T00:00:00Z'`. Unbounded = scan every partition.
DO downsample with `DATE_BIN`, not a (nonexistent) `GROUP BY time()`:
```sql
SELECT DATE_BIN(INTERVAL '5 minutes', time) AS _time,
       room, avg(temp) AS avg_temp
FROM home
WHERE time >= now() - INTERVAL '12 hours'
GROUP BY 1, room
ORDER BY _time
```
DON'T alias the binned column `time` — in `GROUP BY`, `time` resolves to the source column; use `_time` or the ordinal (`1`).
DO use selector functions for "value at min/max/first/last time"; they return a struct — read `selector_last(temp, time)['value']`.
DON'T assume Postgres extras exist (engine is DataFusion) — check the function reference. Timestamps are UTC.

## v2 — Flux
Pipe-forward (`|>`) dataflow. `range()` is **mandatory** — Flux refuses unbounded queries.
```flux
from(bucket: "telemetry")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage_system")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```
DO filter `_measurement`/`_field` right after `range` to prune early.
DO name outputs with `yield(name:)` when a script emits multiple; a lone trailing `yield()` is implicit.
DON'T `group()` on high-cardinality columns or `pivot()` a wide series — memory blows up; downsample first.
DON'T `join()` casually — it materializes both sides; prefer `union()`/schema. Pre-aggregate via `tasks` into a rollup bucket.

## v1 — InfluxQL
```sql
SELECT MEAN("usage") FROM "cpu"
WHERE "host"='web1' AND time >= now() - 6h
GROUP BY time(1m), "host" fill(previous) tz('UTC')
```
DO always constrain `time` (no range = scans all shards).
DO put `fill()` last in `GROUP BY` (`null` default, or `0`/`previous`/`linear`/`none`); it won't interpolate from data outside range.
DON'T `SELECT *` on a high-cardinality measurement or `GROUP BY *` (expands every tag) — classic memory killer.

## Cross-version gotchas
- **Cardinality is the query killer everywhere** — filtering/grouping on unbounded tags (IDs, UUIDs) explodes series; see lore/influxdb/data-model-and-line-protocol.md.
- v3 InfluxQL is a rewrite: **no joins**, no `SLIMIT`/`SOFFSET`, cardinality meta-queries dropped, `SELECT INTO`/continuous queries gone. Verify `moving_average`/`derivative`/`holt_winters` support before use.
- Paginate by time window + `LIMIT`/`ORDER BY time`, not deep `OFFSET`.
- Parameterize — never concat user input; see lore/databases/parameterized-queries-and-injection.md.
- Set query timeouts; watch slow queries — see lore/influxdb/performance.md and lore/databases/resilience-and-observability.md.

## Sources
docs.influxdata.com/influxdb3/core/query-data/sql/ (basic-query, aggregate-select) · docs.influxdata.com/influxdb3/core/reference/influxql/feature-support · docs.influxdata.com/influxdb/v2/query-data/get-started/query-influxdb · docs.influxdata.com/influxdb/v1/query_language/explore-data

# InfluxDB — Performance Playbook

Version-adaptive — confirm version: v1 (TSM/InfluxQL), v2 (TSM/Flux), v3 (columnar Parquet). Universal DB rules → lore/databases.md.

## Levers, highest impact first

### 1. Cardinality (THE killer on v1/v2)
Series = measurement + tag set; v1/v2 keep that index in RAM → runaway cardinality = OOM.
- NEVER put unbounded values (UUIDs, user/request IDs, log lines) in tags — use fields. See lore/influxdb/data-model-and-line-protocol.md.
- v1 `[data]`: `max-series-per-database` (default 1000000), `max-values-per-tag` (100000), `cache-max-memory-size` (1g); `index-version = tsi1` moves the index to disk.
- v3 tolerates high tag-value *count* but cost shifts to **width**: each tag joins the primary key → wider sort, slower compaction. Keep tables narrow.

### 2. Batch writes
- Size: **v3 = 10,000 lines or 10MB, whichever first**; v2 ≈ 5000 lines.
- gzip (`Content-Encoding: gzip`) — up to ~5x faster.
- Coarsest timestamp precision viable (ms/s not ns) — smaller + compresses better.
- v2: sort tags lexicographically by key. v3: order tags by query priority on the FIRST write — column order is then permanent.
- NTP-sync clocks. Rate-limit under backpressure (v2 `influx write --rate-limit`).

### 3. Time partitioning, retention & storage
- v1/v2 use **shard groups**; duration ~2x your longest query range, >100k points/group. Defaults by RP DURATION: <2d→1h, ≤6mo→1d, >6mo→7d; raise `SHARD DURATION` for high throughput, 52w for backfills.
- Expire old data: v1/v2 RP/bucket `DURATION`; v3 per-database retention.
- v3 (diskless/object-store): WAL ~1s, data buffered ~15 min, persisted to Parquet ~10 min, then compacted. Don't rely on local disk alone for durability/HA.

### 4. Downsample (don't scan raw for dashboards)
- v1: `CREATE CONTINUOUS QUERY` → rollup measurement; short RP on raw, long RP on rollup.
- v2: scheduled `tasks` with `aggregateWindow` into a rollup bucket.
- v3: no continuous queries — schedule external rollup writes; query with `DATE_BIN`. Syntax: lore/influxdb/queries-influxql-flux-sql.md.

### 5. Query side
- ALWAYS bound `time` — else scans every shard/partition. Prune `_measurement`/`_field` right after `range` (Flux).
- v3: use the **Last Value Cache** / **Distinct Value Cache** instead of scanning.
- Paginate by time window + `LIMIT`, never deep `OFFSET`.

## Anti-patterns
- High-cardinality tags on v1/v2 (#1 outage cause).
- Tiny/unbatched, uncompressed, ns-precision writes.
- `SELECT *` / `GROUP BY *` on wide measurements; unbounded-time queries.
- No retention/downsampling → scanning months of raw points.
- v3: wide, sparse/null-heavy schemas; using it as a general log/event store.

## How to measure
- Cardinality: InfluxQL `SHOW SERIES CARDINALITY`; Flux `influxdb.cardinality()`; offenders via `schema.tagValues(...) |> count()`. (v3 dropped these meta-queries — inspect schema/columns.)
- v3 plans: `EXPLAIN` / `EXPLAIN ANALYZE` (DataFusion) for partitions scanned.
- Track series after schema changes; watch write rejects, memory, slow queries → lore/databases/resilience-and-observability.md; pool clients → lore/databases/connection-pooling.md.

## Sources
docs.influxdata.com: influxdb3/core optimize-writes + internals/durability · influxdb/v2 resolve-high-cardinality · influxdb/v1 schema_and_data_layout + administration/config

# TimescaleDB — Hypertables & Modeling

Version: extension 2.x on PostgreSQL 15-18 (13/14 legacy) (`\dx timescaledb`). A hypertable is a regular PG table auto-partitioned into **chunks** by a time column; INSERT/SELECT it like any table (standard SQL — lore/postgres applies). Multi-node removed in 2.14; space partitioning is legacy.

## Create
Declarative form (since 2.20; from 2.23 omit `partition_column` to auto-pick the first timestamp column — errors if several are ambiguous):
```sql
CREATE TABLE conditions (
  time timestamptz NOT NULL,
  device text NOT NULL,
  temp  double precision
) WITH (tsdb.hypertable, tsdb.partition_column='time', tsdb.chunk_interval='1 day');
```
Classic builder (still supported):
```sql
SELECT create_hypertable('conditions', by_range('time', INTERVAL '1 day'));
```
`chunk_time_interval` defaults to **7 days**. `set_chunk_time_interval('conditions', INTERVAL '1 day')` retunes future chunks only — never rewrites existing.

## DO
- Size chunks so the **active (most-recent) chunk + its indexes fit in ~25% of RAM**: too small = planning overhead, too large = memory pressure + coarse retention. Start ~1 day.
- Keep the time column `NOT NULL`; write **batched, roughly time-ordered** inserts (COPY / multi-row INSERT), not row-at-a-time.
- Include the partitioning column in every **PRIMARY KEY / UNIQUE** index — Timescale rejects one that omits `time`.
- Add composite indexes for per-entity reads, e.g. `(device, time DESC)`; a `(time DESC)` index is auto-created.
- Model low-cardinality dimensions (device, region, type) as columns — they become `segmentby` keys for compression and cheap filters.
- Query bounded time ranges so the planner does **chunk exclusion** (prunes chunks).

## DON'T
- Don't space-partition (`add_dimension` / `by_hash`) reflexively — on a single node it rarely parallelizes I/O, just multiplies chunks; never hash a high-cardinality id (user/uuid/request) to "shard".
- Don't over-index write-heavy hypertables; every index is maintained per chunk.
- Don't dedupe on non-time columns alone via `UNIQUE` — it can't exist without the partitioning column.
- Don't create a hypertable→hypertable FK (the only unsupported case); regular↔hypertable FKs (either direction) work.
- Don't expect `chunk_time_interval` edits or most `ALTER`s to touch old chunks — choose it up front.

## Cardinality & downstream design
`segmentby`/`orderby` are set at model time; pick `segmentby` = the low-cardinality column you filter on most. Downsample with continuous aggregates and expire raw data via `add_retention_policy(relation, drop_after => INTERVAL '30 days')` (keep the cagg longer). Only hypertables, chunks, and `time_bucket` are Apache-2.0; continuous aggregates, compression, and retention are Community(TSL); tiering to object storage is **Tiger/Timescale Cloud-only** — confirm your edition.

See lore/timescaledb/{continuous-aggregates-and-compression,performance}.md.

## Sources
- tigerdata.com/docs/use-timescale — hypertables, create_hypertable, add_dimension, tiering (Cloud)
- tigerdata.com/docs/api — add_retention_policy, add_columnstore_policy
- lore/postgres.md · lore/databases.md

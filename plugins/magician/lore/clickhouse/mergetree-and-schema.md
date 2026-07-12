# ClickHouse — MergeTree & Schema

Version-adaptive: MergeTree fundamentals are stable across the fast-moving 25.x/26.x line, but lightweight `UPDATE` and its patch-part internals are still **beta** (verify GA before relying on them) — confirm against the release you run.

## Sorting key (ORDER BY) is the whole game
`ORDER BY` defines physical row order per part and doubles as the (sparse) primary key. There is no row-level index: the in-memory index stores one mark per **granule** (`index_granularity`, default 8192 rows). Queries binary-search marks to pick granules, then scan whole granules.

DO order key columns by **ascending cardinality** (low → high). Two wins: (1) a filter on the *leading* column binary-searches marks; a filter on a later column falls back to a generic-exclusion search that prunes only when its predecessor is low-cardinality. (2) Low-cardinality-first clusters similar values, so compression improves sharply. DO put your most-filtered column early. DON'T treat `ORDER BY` like an OLTP PK — it needn't be unique and isn't enforced.

DO split key vs. index when memory matters: `PRIMARY KEY` may be a **prefix** of `ORDER BY` (fewer columns in the RAM index; the rest still sort for compression).

DON'T use `Nullable` columns in the key (needs `allow_nullable_key`, discouraged) — model absence with a sentinel/default.

## Partitioning: pruning, not perf
`PARTITION BY` (commonly `toYYYYMM(date)`) enables partition pruning and cheap `DROP PARTITION` / `TTL` expiry. Parts never merge across partitions. DON'T over-partition — high-cardinality partition keys create thousands of tiny parts → "too many parts" errors and slow merges. Rule: coarse partitions (day/month), fine sorting key.

## Data types drive compression
Compression = ordering + types + codecs. DO pick the narrowest correct type: smallest unsigned int that fits (`UInt16` vs `Int32`), coarsest date (`Date`/`DateTime` over `DateTime64`), `Enum8/16` for closed sets (insert-time validation), `LowCardinality(String)` under ~10k distinct values. DON'T default to `Nullable` — it adds a parallel `UInt8` mask read on every access.

DO add codecs for time-series: `CODEC(DoubleDelta)` for monotonic timestamps, `CODEC(Gorilla)` for slow-changing floats, or `CODEC(Delta, ZSTD)` pipelines (default `LZ4` self-managed / `ZSTD` Cloud).

## Merges, mutations, upserts
Parts are immutable; background merges combine them. Mutations (`ALTER TABLE … UPDATE/DELETE`) are **heavyweight** — they rewrite affected columns of whole parts. Lightweight `DELETE` marks rows via a hidden `_row_exists` mask (physical removal at next merge). Lightweight `UPDATE` (beta) writes **patch parts** (changed cols/rows only), immediately visible, materialized later — meant for < ~10% of rows.

DON'T upsert row-by-row. Use `ReplacingMergeTree` (dedup by `ORDER BY` at merge time; optional `ver` picks the winner, `is_deleted` tombstones) and read with `FINAL`, or use aggregations tolerant of pre-merge dupes. Dedup is **eventual and non-deterministic** — never assume merges ran.

## Sources
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree
- https://clickhouse.com/docs/optimize/sparse-primary-indexes
- https://clickhouse.com/docs/data-modeling/schema-design
- https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree
- https://clickhouse.com/docs/sql-reference/statements/update
- https://clickhouse.com/docs/sql-reference/statements/create/table

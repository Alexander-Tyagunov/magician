# ClickHouse — core digest
Version: calendar YY.M (monthly + LTS); stable 26.6. Gates: async inserts adaptive since 24.2; lightweight DELETE GA, UPDATE beta. Self-host pins an LTS; Cloud tracks latest. No feature before its version.

DO stay columnar — SELECT only needed columns, never SELECT * on wide tables.
DO set MergeTree ORDER BY = filter/sort prefix, low-cardinality first: drives pruning + compression.
DO batch-ingest bulk (10k-1M rows/part); else async_insert=1, wait_for_async_insert=1.
DO dedup via ReplacingMergeTree/aggregating + FINAL/GROUP BY at read — eventual, not per-row UPDATE.
DO precompute: materialized views + projections to scan less.
DO type tight — LowCardinality(String), narrow int/date; coarse PARTITION BY (toYYYYMM) for pruning + TTL.

DON'T write row-by-row or rely on OLTP txns — no multi-statement ACID.
DON'T over-partition (high-cardinality key) → part explosion, too many parts.
DON'T run frequent ALTER TABLE UPDATE/DELETE mutations — they rewrite whole columns.
DON'T assume FINAL/dedup is cheap or skip-indexes help on unsorted data.

Deep dive when writing non-trivial ClickHouse — read lore/clickhouse/{mergetree-and-schema,ingestion-and-inserts,materialized-views-and-query-perf,sharding-and-replication,performance}.md

## Sources
clickhouse.com/docs — mergetree-family/mergetree · optimize/asynchronous-inserts · statements/update

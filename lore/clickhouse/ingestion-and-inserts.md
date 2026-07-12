# ClickHouse — Ingestion & Inserts

Current stable **26.6** (YY.M scheme, monthly cadence — verify feature gates against your server). Ingestion is the make-or-break OLAP discipline: each INSERT writes an immutable, sorted **data part**; a background pool merges small parts into big ones. Your job is to feed ClickHouse **few large batches**, not a stream of tiny rows.

## Batch — the cardinal rule
- Insert **10,000–100,000 rows per batch** (at least 1,000); keep synchronous inserts to roughly **1/sec**. Larger batches write fewer parts, cut merge load, and amortize the fixed per-insert overhead.
- DON'T do row-at-a-time or many small `INSERT ... VALUES` — each spawns a part, background merges fall behind, and you hit the **`Too many parts`** error (a hard write stall). This is the #1 ClickHouse ingestion mistake.
- One part is created **per distinct partition-key value per flush** — a high-cardinality `PARTITION BY` multiplies parts and triggers the same error. Partition coarsely (e.g. by month), not by a high-cardinality column.

## Format & pre-sorting
- Prefer **Native** (columnar, minimal server parsing) or **RowBinary**; `JSONEachRow`/CSV are convenient but CPU-expensive to parse server-side — reserve for low volume.
- Data is stored ordered by the `ORDER BY` (primary) key; pre-sorting the batch client-side lets the server skip its sort step (optional optimization, only when the batch is already near-ordered).

## Bulk load paths
- From files/object storage use table functions in `INSERT ... SELECT`, e.g. `INSERT INTO t SELECT * FROM s3('…','Parquet')` or `file('data.parquet')`; globs (`*`,`{1,2}`,`{1..9}`) fan out over many files.
- `INSERT INTO t FROM INFILE 'x.csv.gz' COMPRESSION 'gzip' FORMAT CSV` loads a client-side file (compression auto-detected from extension).
- `INSERT ... SELECT` **always runs synchronously** — `async_insert` does not apply to it.

## Async inserts — server-side batching
When clients can't batch (many agents, small real-time payloads), enable `async_insert=1`: rows buffer server-side per insert-shape and flush when **any** threshold hits first — `async_insert_max_data_size` (100 MiB), `async_insert_busy_timeout_max_ms` (200 ms; 1000 ms on Cloud), or `async_insert_max_query_number` (450). Adaptive timeout (`async_insert_use_adaptive_busy_timeout`, on since **24.2**) floats between `…_min_ms` (50 ms) and max by data rate.
- Keep `wait_for_async_insert=1` (default): the client is acked only after the flush to disk, so errors surface. `=0` is fire-and-forget — low latency but **silent data loss** and no dead-letter; the docs call it "very risky".
- Buffered rows aren't queryable until flushed; parse/type errors reject the **whole** query at flush time. Drain before maintenance with `SYSTEM FLUSH ASYNC INSERT QUEUE`.

## Idempotency & dedup
Synchronous MergeTree inserts are **idempotent**: identical blocks (same content **and** order) are deduplicated by block hash, so retrying a dropped batch is safe — don't split/reorder on retry or you defeat it. Deduplication is **OFF for async inserts** unless you enable it, and you should not enable it when the table feeds dependent materialized views.

## Upserts & deletes (not row UPDATEs)
- **Upsert** via `ReplacingMergeTree([ver[, is_deleted]])`: rows with the same `ORDER BY` key collapse to the max-`ver` (or last-inserted) row — but **only at merge time**, eventually. Read with `SELECT … FINAL` for correct de-duplicated results; `OPTIMIZE … FINAL CLEANUP` (needs `allow_experimental_replacing_merge_with_cleanup`) purges `is_deleted=1` rows.
- **Lightweight `DELETE FROM … WHERE`** flags rows via the `_row_exists` mask (no immediate rewrite); physical removal waits for a merge (`lightweight_deletes_sync`, `min_age_to_force_merge_seconds`). Far cheaper than `ALTER TABLE … DELETE`, which is a **mutation** that rewrites whole columns of every affected part.
- **Lightweight `UPDATE … SET … WHERE`** (beta) writes **patch parts** with only changed columns — immediately visible, materialized on later merge; designed for small updates (≤~10% of the table). For large rewrites use the heavyweight `ALTER TABLE … UPDATE` mutation. DON'T model per-row OLTP churn on ClickHouse.

## Sources
- ClickHouse — Selecting an insert strategy (batch sizes, formats, idempotency): https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy
- ClickHouse — Asynchronous inserts (thresholds, wait mode, adaptive timeout): https://clickhouse.com/docs/optimize/asynchronous-inserts
- ClickHouse — ReplacingMergeTree (ver/is_deleted, FINAL, merge-time dedup): https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree
- ClickHouse — Lightweight DELETE / UPDATE (masks, patch parts, mutations): https://clickhouse.com/docs/sql-reference/statements/delete · /statements/update

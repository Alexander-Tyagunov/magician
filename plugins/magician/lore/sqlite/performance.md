# SQLite — Performance

SQLite is **in-process**: no network round-trips, so perf is dominated by **transaction commits (fsync) and I/O**, not client/server chatter. Fix them in this order. Stable 3.53.x; behavior holds for 3.7+. Complements the shared `lore/databases/*`; cross-refs `lore/sqlite/{pragmas-and-usage,concurrency-and-wal}.md`.

## Do these first (highest leverage)

1. **Batch writes into ONE transaction.** Per-statement autocommit is the #1 killer: each INSERT/UPDATE fsyncs, capping you at a few dozen commits/sec on spinning disks (SSD is faster, but the amortization win is huge). Wrap bulk writes in `BEGIN IMMEDIATE … COMMIT`. DON'T loop single autocommit writes. Use `IMMEDIATE` (not bare `BEGIN`) to take the write lock up front — avoids the deferred-txn deadlock (see `concurrency-and-wal.md`).
2. **Enable WAL** (`PRAGMA journal_mode=WAL`, persists in the header) + **`PRAGMA synchronous=NORMAL`** — the documented WAL sweet spot: fsync only at checkpoint, readers never block the writer. Detail + checkpoint tuning in `concurrency-and-wal.md`.
3. **Reuse prepared statements.** Prepare once, `bind` + `reset`/`step` per row — never rebuild SQL strings in a loop (re-parse + replan each call). Also blocks injection (`lore/databases/parameterized-queries-and-injection.md`).
4. **Set `PRAGMA busy_timeout`** (default 0 = fail instantly) so lock collisions retry instead of erroring under concurrency.

## Then tune memory & I/O (PRAGMAs; see pragmas-and-usage.md)

- **`cache_size = -N`** → ~N KiB page cache (default `-2000` ≈ 2 MB). Raise it so the working set (esp. index B-trees) stays resident. Positive N = pages, negative = KiB (since 3.7.10).
- **`mmap_size = N`** enables memory-mapped reads (default off/compile-dependent; capped by `SQLITE_MAX_MMAP_SIZE`) — cuts read syscall overhead for read-heavy loads.
- **`page_size`** default 4096 (since 3.12.0); change only before first write or via `VACUUM` in a rollback mode, **never in WAL**.

## Indexes & the planner

- Add indexes matching WHERE/JOIN/ORDER BY; aim for **covering indexes** (all selected cols in the index → no table lookup). Depth: `lore/databases/indexing-and-query-plans.md`.
- **Keep stats fresh:** run `PRAGMA optimize;` before closing short-lived conns; `PRAGMA optimize=0x10002;` at open + periodically for long-lived ones; and after any `CREATE INDEX`. It auto-runs `ANALYZE` (writing `sqlite_stat1`) with a built-in scope limit since 3.46.0. Stale/missing stats → bad plans.

## DON'T

- **DON'T put the DB on NFS/SMB/network FS** — file locking + WAL shared-memory break there → corruption/`SQLITE_BUSY`. Keep it local.
- DON'T reach for `synchronous=OFF` — faster writes, but a crash mid-write can corrupt the file. Prefer batching + WAL/NORMAL.
- DON'T let the WAL bloat (long-held read txns stall checkpoints) — read cost scales with WAL size.

## How to measure (SEE the problem)

- **`EXPLAIN QUERY PLAN <stmt>`** (CLI: `.eqp on`): `SCAN t` = full-table scan (add/adjust an index); `SEARCH t USING [COVERING] INDEX` = good; `USE TEMP B-TREE FOR ORDER BY` = missing sort index. Output is debug-only, format may change across releases.
- CLI **`.timer on`** + **`.stats on`** for wall time and cache-miss/fullscan counters; plain `EXPLAIN` dumps VDBE bytecode when EQP isn't enough.
- **`sqlite3_analyzer`** for on-disk page/fragmentation stats; `PRAGMA compile_options;` to confirm threadsafe/STAT4 build.

## Sources
- INSERT speed / transactions: https://www.sqlite.org/faq.html
- EXPLAIN QUERY PLAN: https://www.sqlite.org/eqp.html
- PRAGMA (cache_size, mmap_size, synchronous, busy_timeout): https://www.sqlite.org/pragma.html
- ANALYZE / PRAGMA optimize: https://www.sqlite.org/lang_analyze.html
- WAL mode: https://www.sqlite.org/wal.html

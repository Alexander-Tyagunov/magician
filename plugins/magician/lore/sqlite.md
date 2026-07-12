# SQLite — core digest
Version: 3.53.x stable (2026-06). Embedded single-file DB. STRICT tables 3.37+; host-param cap 999→32766 (3.32+).

DO enable WAL once (`journal_mode=WAL`, persists); per conn `synchronous=NORMAL`+`busy_timeout` to avoid `SQLITE_BUSY`.
DO set `PRAGMA foreign_keys=ON` on EVERY conn — OFF by default, outside a txn.
DO bind `?`/`:name`; keep write txns short, batch in one `BEGIN…COMMIT`.
DO declare `STRICT` tables for rigid types; else affinity lets any column hold anything.
DO use `INTEGER PRIMARY KEY` (rowid alias) for keys; `WITHOUT ROWID` for composite/text PKs.
DO read plans via `EXPLAIN QUERY PLAN`; index predicates/joins; `ANALYZE`/`PRAGMA optimize` after `CREATE INDEX`.
DO tune per-conn PRAGMAs (`cache_size` neg=KiB, `temp_store=MEMORY`, `mmap_size`) — reset on close.

DON'T put a WAL DB on network FS (NFS/SMB) — needs shared memory; procs one host, else corruption.
DON'T expect date/bool enforcement — no DATE/BOOLEAN class; use TEXT ISO8601, INTEGER unixepoch, 0/1.
DON'T pool writers for parallelism — writes serialize; one writer, scale readers.
DON'T forget `-wal`/`-shm` sidecars when copying a live DB, or exceed the param cap on big `IN(...)`/inserts.

Deep dive when writing non-trivial SQLite — read lore/sqlite/{pragmas-and-usage,concurrency-and-wal,types-and-limits,performance}.md

## Sources
sqlite.org/{wal,pragma,datatype3,limits}.html

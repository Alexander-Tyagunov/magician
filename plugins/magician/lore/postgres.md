# PostgreSQL — core digest
Version: 18 stable; supported 14-18 (13 EOL 2025-11). Gates: 14 jsonb subscripting/SCRAM default; 15 MERGE, no CREATE on PUBLIC; 16 pg_stat_io; 17 JSON_TABLE; 18 async I/O, uuidv7(), virtual gen cols. No feature before its major.

DO pool externally (backend=process): PgBouncer txn mode, modest max_connections; no conn-per-request or oversized pool.
DO bind $1 placeholders: server-prepared, injection-safe.
DO read plans via EXPLAIN (ANALYZE, BUFFERS); index FKs + filter/sort cols; partial, expression, covering (INCLUDE), GIN (jsonb/FTS), BRIN.
DO use jsonb (not json); GIN jsonb_path_ops, query @>/jsonpath.
DO wrap writes in a tx; default READ COMMITTED, use REPEATABLE READ/SERIALIZABLE, retry 40001/40P01.
DO tune (never disable) autovacuum: dead tuples + idle-in-tx pin xmin -> bloat.
DO auth SCRAM (default since 14) over TLS; least-priv roles; RLS for tenants.

DON'T assume world-writable public: grant CREATE explicitly (15+).
DON'T run giant single-shot DML or blocking ALTER/index builds; batch + CREATE INDEX CONCURRENTLY + lock_timeout.
DON'T trust serial; prefer identity/bigint or uuidv7() (18) keys.

Deep dive when writing non-trivial PostgreSQL — read lore/postgres/{connection-and-pooling,types-and-jsonb,indexing-mvcc-and-vacuum,transactions-and-locking,partitioning-and-scale,performance}.md

## Sources
postgresql.org/docs/18 · support/versioning

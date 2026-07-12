# Apache Cassandra — Queries & secondary indexes

Wide-column, tunable consistency. 5.0.x current stable (GA 2024; SAI + vector search new in 5.0); 4.0/4.1 supported, 3.11 EOL — verify. ScyllaDB is CQL-compatible (global 2i is materialized-view-backed; SAI is Cassandra-only) — verify parity first.

## The query drives the schema
No JOINs, no ad-hoc filtering. A `SELECT` must hit a partition by equality on the **full partition key** (`IN` counts as equality); within it, clustering columns restrict a **contiguous prefix** and only the **last** restricted one may be a range (`>`/`<`). `ORDER BY` is limited to clustering order or its reverse. So the idiom is **one table per access pattern** — denormalize, write each row to every query table; the primary key answers the read. Indexes are *secondary*, never a substitute for a good key.

- DO restrict the full partition key + clustering prefix; use `token(pk)` for partition-range scans, `PER PARTITION LIMIT`, and cursor paging — never OFFSET.
- DON'T reach for `ALLOW FILTERING` in app code: it scans every partition, latency grows with data, rejected by default. Fine only for known-tiny or admin queries.

## Secondary options, in order of preference
1. **Second query table / denormalize** — default; predictable single-partition reads.
2. **SAI (Storage-Attached Index, 5.0)** — `CREATE INDEX ix ON t(col) USING 'sai'`. One index per column, many per table (`sai_indexes_per_table_failure_threshold`=10 default), ~20-35% disk overhead, **synchronous** write path (indexed on ack), `Murmur3Partitioner` only. Numeric/timestamp/uuid support ranges (`=,<,>,<=,>=`, k-d tree); text supports `=`, `CONTAINS`, `CONTAINS KEY` only — **no `LIKE`/`!=`/text ranges**. Collections via `KEYS`/`VALUES`/`ENTRIES`, UDTs, and vectors (`ORDER BY ... ANN OF`, LIMIT ≤1000). `AND` processes up to two SAI indexes; extra indexed predicates are post-filtered; `OR` supported. Options: `case_sensitive` (default true), `normalize`, `ascii`. Removes `ALLOW FILTERING` for indexed predicates — but mixing in a non-indexed column needs it.
3. **Legacy 2i** (`CREATE INDEX` without `USING`) and **SASI** — scatter-gather across nodes; latency scales with cluster size, not matches. Avoid high-cardinality (near-unique) and very low-cardinality (boolean) columns — the classic 2i trap. SASI is experimental; on 5.0 prefer SAI.

## Gotchas
- An index read is still **cluster-wide** unless you co-restrict the partition key to pin it to one node — add PK equality when the pattern allows.
- SAI can index one column of a **composite** partition key, but not a single-column PK (it errors — the PK already answers it).
- Indexing a hot/low-cardinality value recreates the **hot-partition** problem in the index.
- Consistency is tunable per statement (`LOCAL_QUORUM` typical); an index read uses the normal read path — not transactional or point-in-time.

See performance.md for the fast-path/anti-pattern playbook and lore/databases/{indexing-and-query-plans,resilience-and-observability}.md.

## Sources
- cassandra.apache.org/doc/latest/cassandra/developing/cql/indexing/sai/{sai-query,sai-faq,sai-overview}.html (SAI operators, ranges, collections, limits)
- cassandra.apache.org/doc/latest/cassandra/developing/cql/dml.html (WHERE/clustering/IN/token/ORDER BY/ALLOW FILTERING rules)
- cassandra.apache.org/doc/latest/cassandra/reference/cql-commands/create-index.html (CREATE INDEX ... USING 'sai', KEYS/VALUES/ENTRIES, options)

# PostgreSQL — Partitioning & Scale

Current stable 18; supported line 14→18. Declarative partitioning is the engine feature — treat legacy inheritance + `constraint_exclusion` (default `partition`) as legacy: plan-time only, degrades past ~100 children. Partition to shrink hot indexes and make bulk data lifecycle cheap — "never assume more partitions are better."

## Pick the method by access pattern
- **RANGE** (time-series, monotonic IDs): cheap retention — `DETACH`+`DROP TABLE` of an old partition is metadata-only versus a giant `DELETE`+`VACUUM`. Bounds are lower-inclusive, upper-exclusive (`10` lands in `[10,20)`).
- **LIST**: discrete keys (region, tenant class).
- **HASH** (`MODULUS m, REMAINDER r`): even write spread, but **no pruning on range predicates** — only equality on the key prunes.

Updating a row's partition-key value moves it to the right partition (row movement). A `DEFAULT` partition catches unmatched rows; without one, an unroutable INSERT errors.

## Pruning is the point — and it only reads the partition key
`enable_partition_pruning` is `on`. The planner prunes at **plan time** from key predicates; for prepared-statement params or subquery/nested-loop values it prunes at **execution time** — see `Subplans Removed` and `(never executed)` in `EXPLAIN (ANALYZE, BUFFERS)`. Pruning is driven by partition-**key** constraints, **not indexes**: a query that doesn't filter the partition key touches every partition. Gotcha: partitions pruned at executor *init* are still **locked** at statement start, so lock count scales with partitions even when scans don't.

## Keys, uniqueness, indexes
A UNIQUE/PRIMARY KEY is enforced per-partition, so its columns **must include every partition-key column**, and the key **can't be an expression**; there is no global cross-partition unique index. Exclusion constraints must compare all partition-key columns for equality. `CREATE INDEX CONCURRENTLY` is unsupported on the parent — build it bottom-up without long locks:
```sql
CREATE INDEX ON ONLY parent (col);                 -- invalid parent stub
CREATE INDEX CONCURRENTLY p1_col ON part1 (col);   -- per partition
ALTER INDEX parent_col ATTACH PARTITION p1_col;     -- parent flips valid once all attach
```

## ATTACH / DETACH without an outage
`ATTACH PARTITION` takes only `SHARE UPDATE EXCLUSIVE` on the parent (since 12) but **full-scans the new table under ACCESS EXCLUSIVE** to validate the bound — pre-add a matching `CHECK` so the scan is skipped, then drop it. A present `DEFAULT` partition is also scanned unless it carries a `CHECK` excluding the new range. `DETACH PARTITION CONCURRENTLY` (14+) uses a reduced lock across two transactions; it **cannot run in a transaction block** and is refused when a `DEFAULT` partition exists — finish an interrupted one with `DETACH PARTITION ... FINALIZE`. Pre-14, `DETACH` needs `ACCESS EXCLUSIVE`. Since 14, UPDATE/DELETE also use execution-time pruning with far less planner overhead.

## Partitionwise join/aggregate: off by default
`enable_partitionwise_join` and `enable_partitionwise_aggregate` are both **`off`**. They help only when both inputs share identical partition bounds on the join/`GROUP BY` keys, and each makes the count of `work_mem`-bounded plan nodes grow linearly with partitions and planning far heavier in CPU/memory. Enable per-session for large matched-partition analytics, never globally on OLTP.

## Count discipline & scale-out
Keep partitions to at most a few thousand, and only when pruning leaves a handful per query: each partition's catalog metadata loads into **every session's** local memory, and unpruned partitions inflate planning time and memory. For read scale, add hot-standby physical replicas (streaming replication) and route reads there; front all backends with an external pool. FK constraints **referencing** a partitioned table work since 12. Cross-node "sharding" via `postgres_fdw` foreign-table partitions is possible, but joins/pruning run largely per foreign-scan and aren't automatically parallel — read the plan before relying on it.

## Sources
- postgresql.org/docs/18/ddl-partitioning.html (methods, pruning, ATTACH/DETACH, key/index limits, best practices)
- postgresql.org/docs/18/runtime-config-query.html (partition_pruning + partitionwise defaults & memory caveats, constraint_exclusion)
- postgresql.org/docs/18/sql-altertable.html (DETACH CONCURRENTLY/FINALIZE locks & restrictions, ATTACH lock levels)
- postgresql.org/docs/release/14.0/ and /release/12.0/ (DETACH CONCURRENTLY + exec-time UPDATE/DELETE pruning in 14; FK-referencing + reduced ATTACH lock + many-partition perf in 12)

# MySQL — Indexing and EXPLAIN

Version: 8.4 LTS / 9.x. Gates: invisible (8.0.0), descending (8.0.1), histograms (8.0.3), functional key parts + skip scan (8.0.13), multi-valued JSON (8.0.17), `EXPLAIN ANALYZE` + hash join (8.0.18). Never on 5.7. InnoDB=BTREE (+FULLTEXT/SPATIAL).

## Clustered structure
InnoDB clusters rows on the PK (else first UNIQUE NOT NULL, else hidden rowid). Secondary leaves store key **+ PK**, so a wide PK bloats every index and non-covering lookups pay a 2nd descent (bookmark lookup). Keep PK small/monotonic.

## Composite: leftmost prefix + skip scan
`(a,b,c)` serves `a`, `a,b`, `a,b,c` + a **range on the last used part only**; anything right of a range/`IN` is dead for equality. Order equality-first, range-last; `ORDER BY` after them (free sort). A **covering** index (all SELECT+WHERE cols) needs no row read. No predicate on `a` normally kills it; **skip scan** (`Using index for skip scan`) may rescue: cost-based, favored when `a` has **few distinct values** (preference, not a gate); needs single-table, index-only (no `GROUP BY`/`DISTINCT`), equality on leading parts.

## Reading EXPLAIN
`type` best→worst: `system`>`const`>`eq_ref`>`ref`>`range`>`index`>`ALL` (last two = full scans). `key_len` = composite parts used; short = a trailing part unused. `rows × filtered/100` = rows to next table; low `filtered` on `ALL`/`index` is the flag. `Extra`: `Using index`=covering; `index condition`=ICP; `filesort`/`temporary`=no index for `GROUP BY`/`ORDER BY`; `index_merge`=single-col indexes combined (add a composite). `EXPLAIN ANALYZE` (8.0.18, `FORMAT=TREE`): actual vs estimated rows, big gap = stale stats/bad selectivity; the only view of hash joins.

## Special index types
- **Descending** `(a ASC, b DESC)`: real reverse storage → mixed-direction `ORDER BY`, no filesort.
- **Invisible** — `ALTER TABLE t ALTER INDEX x INVISIBLE`: maintained but planner-ignored; toggle via `optimizer_switch='use_invisible_indexes=on'`. PKs can't be invisible.
- **Functional** `((col1+col2))`: hidden virtual generated column; expression must match **exactly**, no prefixes, not in FKs.
- **Multi-valued** JSON arrays: `CAST(js->'$.tags' AS UNSIGNED ARRAY)` via `MEMBER OF`/`JSON_CONTAINS`/`JSON_OVERLAPS`; never covering, no range scan, `ALGORITHM=COPY`.
- **Prefix** `col(20)`: can't cover or fully serve `ORDER BY`.

## Statistics
`ANALYZE TABLE` refreshes index cardinality (sampled) under a **read lock**. **Histograms** (`ANALYZE TABLE t UPDATE HISTOGRAM ON col`) give selectivity for **un-indexed** cols to sharpen `filtered`/join order; no new access path.

## DON'T
- Coercion: a string col vs number (`WHERE vc = 1`) casts the *column* per row → full scan. Non-sargable: leading-wildcard `LIKE '%x'`, a bare function on a column (use a functional index).
- Don't join on mismatched charset/collation — conversion disables the index on the join side.
- Don't index low-cardinality leading cols or over-index write-heavy tables — each index is a B-tree to maintain, bloating the clustered pointer.
- Don't trust `rows` (InnoDB estimate) or leave stats stale after bulk loads — re-`ANALYZE`.
- **MariaDB**: no `EXPLAIN ANALYZE` (use `ANALYZE SELECT`, `r_rows`/`r_filtered`); no functional/multi-valued JSON (generated cols); histograms + ignored-index syntax differ.

## Sources
- refman/8.4/en/: explain-output.html, explain.html, create-index.html, {index-condition-pushdown,index-merge,range,hash-joins,analyze-table}-optimization.html

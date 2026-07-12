# Polars — core

Version: target Polars ≥1.0 (stable). Pre-1.0 renamed `apply`→`map_elements`, `groupby`→`group_by`. Strict schema; own engine (not PyArrow/pandas).

DO
- Go lazy: `pl.scan_csv/scan_parquet(...).filter(...).group_by(...).agg(...).collect()` — enables predicate + projection pushdown. Inspect with `.explain()`.
- Work via expressions in contexts: `select`, `with_columns`, `filter`, `group_by().agg()`. Separate exprs run in parallel; `pl.col(...)` expands over many/typed cols.
- Chain one query; let the optimizer reorder. Larger-than-RAM: `q.collect(engine="streaming")`.
- On LazyFrame use `.collect_schema()` — `.schema/.columns/.width` raise PerformanceWarning.

DON'T
- No `read_csv` + eager chains when you'll filter/select — you load unused rows/cols; use `scan_*`.
- No `map_elements`/per-row Python UDF (slow) — use native exprs or `map_batches`; pass `return_dtype`.
- No pandas habits: no index; no `iterrows`/row loops; mutate via `with_columns`, not `df[c]=`.
- `collect(streaming=True)` is legacy → `engine="streaming"`. `.get`/`.gather` raise on OOB (`null_on_oob=True` for old).

Commands: `pip install -U polars`; `pl.show_versions()`.

Deep dive when writing non-trivial polars — read lore/polars/{lazy-and-expressions}.md

Sources: docs.pola.rs — concepts/lazy-api, expressions-and-contexts, streaming, user-defined-python-functions, releases/upgrade/1

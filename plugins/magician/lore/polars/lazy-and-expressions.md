# polars — Lazy API & expressions

Scope: expression API, lazy vs eager, query optimization, streaming, contexts. Assumes Python foundation lore exists separately. Verified against docs.pola.rs (Polars **1.x** stable; 1.0.0 shipped 2024). State the version; give fallbacks.

## Mental model (read first)

- An **expression** (`pl.col(...).mean()`) is a *lazy description* of a transform. It computes nothing until placed in a **context**.
- The four contexts: `select`, `with_columns`, `filter`, `group_by(...).agg(...)`. Same expression can yield different results per context.
- **Eager** (`read_*`, `df.select(...)`) runs immediately. **Lazy** (`scan_*`, `.lazy()`, `.collect()`) builds a plan, optimizes, then runs. The eager API calls lazy under the hood and collects immediately.

## DO — expressions over loops

- **Vectorize everything.** Express row logic as column expressions; never iterate rows in Python.
- **`pl.col`** selects by name, dtype, or many at once — enables *expression expansion* (one expr → many columns, run in parallel):
  ```python
  df.select((pl.col(pl.Float64) * 1.1).name.suffix("_x11"))   # all Float64 cols
  df.select(pl.col("weight", "height").mean().name.prefix("avg_"))
  ```
- **Conditionals** with `when/then/otherwise` (chainable; branches computed in parallel):
  ```python
  df.with_columns(
      pl.when(pl.col("v") < 5).then(pl.lit("low"))
        .when(pl.col("v") < 12).then(pl.lit("med"))
        .otherwise(pl.lit("high")).alias("bucket")
  )
  ```
  Omitting `.otherwise` yields null.
- **Window functions** `.over(...)` = grouped aggregation that keeps row count. Pick `mapping_strategy`:
  ```python
  pl.col("speed").rank("dense", descending=True).over("type")          # group_to_rows (default)
  pl.col("speed").mean().over("type")                                  # scalar broadcast per group
  pl.all().sort_by("rank").over("country", mapping_strategy="explode") # fastest; REORDERS rows
  pl.col("rank").sort().over("country", mapping_strategy="join")       # aggregates to list per row
  ```
- Use `group_by().agg()` when you want one row per group; `.over()` when you want the original shape back.
- Prefer `pl.len()` (row count), `pl.first()`, `pl.sum(...)` — expression constructors, not Python `len`.

## DON'T — pandas reflexes

- **`polars != pandas`.** Pandas-shaped code often runs, but slower. No index, no `.loc/.iloc`, no `SettingWithCopyWarning` — position-based, Arrow-backed (not NumPy).
- **DON'T litter `.pipe` / chained `with_columns`.** Each separate context runs sequentially with zero parallelism. Write functions that *return expressions* and drop them all into one `with_columns`.
- **DON'T round-trip through pandas.** `to_pandas()` / `.to_numpy()` copy, break laziness, and force full materialization. Stay in Polars; convert once at the boundary. For NumPy interop use `to_numpy()` only at the edge.

## Lazy vs eager

DO make lazy the default. Only go eager for exploration or when you need intermediate results.

```python
lf = pl.scan_parquet("data/*.parquet")          # lazy: nothing read yet
out = (lf.filter(pl.col("region") == "EU")
         .group_by("sku").agg(pl.col("rev").sum())
         .collect())                             # optimize + execute here
```

- `scan_csv/scan_parquet/scan_ndjson/scan_ipc...` → LazyFrame. `read_*` → eager DataFrame.
- `df.lazy()` promotes an in-memory frame into the optimizer.
- `.collect()` triggers execution (single batch, must fit in RAM).
- **DON'T** `read_csv(...).lazy()` when you can `scan_csv(...)` — scanning lets pushdown skip rows/columns *at the file*.

## Query optimization (why lazy wins)

The optimizer applies (verified names): **predicate pushdown** (filter at scan), **projection pushdown** (read only needed columns), **slice pushdown**, **common subplan elimination**, **simplify expressions** (constant folding), **join ordering**, **type coercion**, **cardinality estimation** (group-by strategy).

- DO inspect before running: `lf.explain()` shows the optimized plan; `lf.profile()` times each node.
- DO put `filter` and column selection early — but the optimizer will push them anyway; readability first.
- DON'T assume LazyFrames cache: reusing one recomputes unless subplans coincide. For diverging queries collect together:
  ```python
  a, b = pl.collect_all([lf1, lf2])   # shared subplans execute once
  ```
- Note: order-sensitive ops (e.g. `group_by`) may need `maintain_order=True`.

## Streaming (larger-than-RAM)

Polars **1.x** ships a new streaming engine. Current API:

```python
lf.collect(engine="streaming")          # batched execution, low peak memory
```

- **Version note:** the older `collect(streaming=True)` keyword is legacy — prefer `engine="streaming"` on 1.x. If pinned to an early release where `engine=` is unavailable, fall back to `streaming=True`.
- For results bigger than RAM, **sink to disk** instead of collecting:
  ```python
  lf.sink_parquet("out.parquet")        # streams, never fully materializes
  lf.sink_csv("out.csv")
  ```
- Not every operation streams; the engine falls back to in-memory for unsupported nodes. Verify with `explain(streaming=True)` / profiling on your version.

## Version-adaptivity cheatsheet

- **Polars 1.0+ (2024) = stable API.** Pin `polars>=1` for new work.
- Pre-1.0 → 1.0 renames to fix if you inherit old code: `groupby`→`group_by`, `with_column`→`with_columns`, `pl.count()`→`pl.len()`, `apply`→`map_elements`, `.map`→`map_batches`, `fetch()`→scan + `.head().collect()`.
- Reproducibility: pass explicit `seed=` to sampling/shuffle ops; don't rely on defaults.
- No data leakage: fit encoders/stats on train split only, then apply to val/test.

## Reviewer checklist

- [ ] `scan_*` (not `read_*`) for files; `.collect()` once at the end.
- [ ] Row logic is expressions, not Python loops.
- [ ] Related column ops share one `with_columns` (parallel), not chained pipes.
- [ ] No `to_pandas()`/`to_numpy()` mid-pipeline.
- [ ] `.over()` uses the right `mapping_strategy`; `explode` reorder is intentional.
- [ ] Larger-than-RAM path uses `engine="streaming"` or `sink_*`.
- [ ] `polars>=1`; no pre-1.0 method names.

## Sources

- https://docs.pola.rs/
- https://docs.pola.rs/user-guide/concepts/lazy-vs-eager/
- https://docs.pola.rs/user-guide/concepts/expressions-and-contexts/
- https://docs.pola.rs/user-guide/concepts/lazy-api/
- https://docs.pola.rs/user-guide/lazy/optimizations/
- https://docs.pola.rs/user-guide/lazy/execution/
- https://docs.pola.rs/user-guide/expressions/window-functions/
- https://docs.pola.rs/user-guide/migration/pandas/

# pandas — Idioms & performance

Senior-reviewer checklist. Assumes Python foundation lore. Version-adaptive: **1.x** / **2.x** / **3.0** (current, released 2026-01-21; docs 3.0.4). State the target pandas version before asserting behavior — the copy/view and dtype defaults changed hard between majors.

## Copy-on-Write (CoW) — the defining 2.x→3.0 shift

Timeline: opt-in **1.5.0**; most optimizations **2.0**; all **2.1**; `"warn"` preview mode **2.2**; **default and only mode in 3.0**.

Rule under CoW: *any* indexing result or method returning a new object **behaves as a copy**. The only way to mutate an object is to modify that object directly. pandas uses views internally and copies lazily only when a shared object is written.

### DO
- Target 3.0 behavior for new code. To modify in place, index the real object once:
  ```python
  df.loc[df["bar"] > 5, "foo"] = 100          # correct
  ```
- On 2.2, before upgrading, surface breakage: `pd.options.mode.copy_on_write = "warn"` (noisy but exhaustive). Upgrade path: get clean on **2.3** → then 3.0.
- Reassign to the same name to drop the old reference and avoid a defensive copy:
  ```python
  df = df.reset_index(drop=True)
  df.iloc[0, 0] = 100                          # no copy; old ref gone
  ```

### DON'T
- Don't chain-assign — it silently stopped working under CoW (raises `ChainedAssignmentError`):
  ```python
  df["foo"][df["bar"] > 5] = 100              # BROKEN
  ```
- Don't rely on `SettingWithCopyWarning` — **removed in 3.0**. Don't sprinkle defensive `.copy()` to silence a warning that no longer exists.
- Don't expect a sub-selection to write back:
  ```python
  sub = df["foo"]; sub.iloc[0] = 100          # does NOT touch df
  df["foo"].replace(1, 5, inplace=True)       # does NOT touch df
  ```
  Use `df.loc[...]` or `df["foo"] = df["foo"].replace(1, 5)`.
- Don't mutate `df.to_numpy()` — returns a **read-only** view under CoW (`ValueError: destination is read-only`). Call `.to_numpy(copy=True)`.
- Don't set `pd.options.mode.copy_on_write` on 3.0 — no effect, deprecated, removed in 4.0.

## inplace / the `copy` keyword

### DO / DON'T
- Prefer functional reassignment (`df = df.method(...)`) over `inplace=True`. `inplace` rarely saves memory and blocks method chaining.
- On 3.0, in-place methods (`replace`, `fillna`, `ffill`, `bfill`, `interpolate`, `where`, `mask`, `clip`) with `inplace=True` now **return `self`**, not `None`.
- Drop the `copy=` keyword from `astype`/`merge`/`rename`/`reindex`/etc. — no effect since 3.0, removed in 4.0.

## Vectorize — never loop over rows

### DO
- Use vectorized column ops, `.groupby().agg()`, `merge`, `map`, `np.where`, `.str`/`.dt` accessors — `groupby().agg()` far beats `.apply()` for standard reductions.
- If you must apply a scalar Python function elementwise, `Series.map` beats a row loop.

### DON'T
- Don't use `iterrows` / `itertuples` / `apply(axis=1)` as the primary compute path — they are Python-level loops (orders of magnitude slower, and `iterrows` also loses dtypes by boxing each row to a Series).
  ```python
  df["c"] = df["a"] + df["b"]                 # DO
  df["c"] = df.apply(lambda r: r.a + r.b, axis=1)  # DON'T
  ```

## Indexing: `.loc` / `.iloc` / `.at` / `.iat`

### DO
- `.loc` = **labels** (both slice endpoints **inclusive**); `.iloc` = **integer positions** (stop **excluded**).
- Scalar access → `.at` (label) / `.iat` (position); faster than `.loc`/`.iloc`.
- Group boolean masks with parentheses (Python precedence): `df[(df.a > 0) & (df.b < 1)]`.
- Possibly-missing labels: `s.reindex(keys)` (missing → NaN) or `s.loc[s.index.intersection(keys)]`.
- To bypass `.loc` axis-alignment on assignment, feed raw values: `df.loc[:, ["B","A"]] = df[["A","B"]].to_numpy()`.

### DON'T
- Don't chain `[]` for either read or write — `df["a"]["b"]`; use one `.loc[row, col]`.
- Don't pass a boolean **Series** to `.iloc` (needs a boolean **array**: `df.iloc[mask.values]`); `.loc` accepts the Series.

## merge / join / groupby

### DO
- Use `merge(how=..., on=...)`; set `validate="one_to_many"` (etc.) to assert cardinality and catch dup-key row explosions early.
- `join` on the index is fastest; set the index first when repeatedly joining on the same key.
- Pass `sort=False` to `groupby` when order doesn't matter (skips a sort).
- Use named aggregation for clarity: `df.groupby("k").agg(total=("x","sum"), n=("x","size"))`.
- Add `observed=True` on categorical groupers to avoid the full cartesian product of unused categories. (Default flipped to `True` in 3.0.)

### DON'T
- Don't merge without checking key uniqueness — silent many-to-many blowups. Don't ignore `_merge` from `indicator=True` when debugging missing rows.

## dtypes — nullable & pyarrow backend

pandas has **three** dtype families: NumPy (legacy), NumPy-nullable masked (`Int64`, `boolean`, `Float64`), and Arrow-backed (`int64[pyarrow]`, via `ArrowDtype`).

### DO
- Request nullable/arrow output at read time (added **2.0**):
  ```python
  df = pd.read_csv(f, dtype_backend="numpy_nullable")   # masked nullable
  df = pd.read_csv(f, dtype_backend="pyarrow")          # Arrow-backed
  ```
  Supported on `read_csv/parquet/json/...`, `to_numeric`, `convert_dtypes`. Requires `pyarrow` (min 7.0.0 in 2.0).
- Prefer nullable dtypes for integer columns that carry missing data — avoids silent upcast to `float64`.
- On **3.0**, string columns infer the dedicated `str` dtype by default (PyArrow-backed if installed, else NumPy `object`; NaN missing sentinel). Don't assume `object`.
- Use Arrow backend for large string/categorical data, fast IO, and zero-copy interop with Polars/cuDF.

### DON'T
- Don't conflate `"string[pyarrow]"` (→ `StringDtype`, NumPy-backed nullable results) with `pd.ArrowDtype(pa.string())` (→ `ArrowDtype`). Different result dtypes.
- Don't leave numeric columns as `object` — check `df.dtypes`; downcast/convert explicitly.

## Method chaining

### DO
- Chain with `.assign()`, `.pipe()`, `.loc[lambda d: ...]` for readable, copy-safe pipelines (callables avoid intermediate-variable chained-assignment traps):
  ```python
  out = (df
      .query("x > 0")
      .assign(z=lambda d: d.a / d.b)
      .groupby("k").agg(z=("z","mean"))
      .loc[lambda d: d.z > 1])
  ```

### DON'T
- Don't break a chain with `inplace=True` (returns `self` on 3.0 but still muddies intent) or with hidden temporaries.

## Large data — read in chunks

### DO
- Stream when it won't fit in memory: `for chunk in pd.read_csv(f, chunksize=100_000): ...` (returns a `TextFileReader` iterator).
- Reduce footprint at read: `usecols=`, `dtype=`, `parse_dates=`, `dtype_backend="pyarrow"`.
- Prefer columnar formats (`read_parquet`/`read_feather`) with `columns=` push-down over CSV.
- For out-of-core / lazy work beyond pandas, hand off to Polars, DuckDB, or Dask.

### DON'T
- Don't load full multi-GB CSVs into one frame; don't re-read the same file per operation.

## Reproducibility & correctness

- Seed sampling: `df.sample(n, random_state=42)`. No leakage: fit encoders/scalers/imputers on **train only**, then transform test.

## Sources
- https://pandas.pydata.org/docs/user_guide/copy_on_write.html
- https://pandas.pydata.org/docs/whatsnew/v3.0.0.html
- https://pandas.pydata.org/docs/whatsnew/v2.0.0.html
- https://pandas.pydata.org/docs/user_guide/pyarrow.html
- https://pandas.pydata.org/docs/user_guide/indexing.html
- https://pandas.pydata.org/docs/

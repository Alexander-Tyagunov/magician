# numpy — Arrays & vectorization

Version-adaptive: **1.x** vs **2.x** (2.0 released 2024-06; 2.x is current). Detect at runtime:
```python
import numpy as np
NP2 = np.lib.NumpyVersion(np.__version__) >= "2.0.0b1"
```
Assumes Python foundation lore exists separately.

## ndarray & dtype

DO
- Treat `ndarray` as (data buffer + metadata: `shape`, `dtype`, `strides`). Same buffer + new metadata = view.
- Set dtype explicitly for memory/precision: `np.zeros(n, dtype=np.float32)`, `np.array(x, dtype=np.int64)`.
- Inspect: `a.shape`, `a.dtype`, `a.ndim`, `a.nbytes`, `a.flags`.
- Prefer `np.asarray(x)` over `np.array(x, copy=False)` — same speed, no copy unless needed.

DON'T
- Don't rely on default int width. On 2.x, default integer is `np.intp` (64-bit on 64-bit Windows too; was C `long` before). Pin dtype when width matters.
- Don't grow arrays in a loop (`np.append`/`concatenate` per row reallocates each time). Preallocate, or build a list then `np.array(list)` once.
- Don't assume `object` dtype is fast — it's a boxed-Python fallback with no vectorization.

## Vectorized ops (no Python loops)

DO
- Express element-wise math on whole arrays; ufuncs run in C: `a * b + 2`, `np.sqrt(a)`, `np.where(cond, x, y)`.
- Reduce with axis: `a.sum(axis=0)`, `a.mean(axis=1)`, `np.maximum.reduce(...)`.
- Use `out=` and in-place ops to avoid temporaries on hot paths: `np.multiply(a, b, out=a)`.

DON'T
- Don't `for i in range(len(a)): a[i] = ...`. Rewrite as array expressions or masks.
- Don't reach for `np.vectorize` for speed — it's a convenience loop, not vectorization.
- Don't `+=` across mismatched dtypes expecting upcast; in-place keeps the LHS dtype and can overflow/truncate.

## Broadcasting

Rule: compare shapes **right-to-left**. Dims are compatible when **equal** or **one is 1**; missing leading dims are treated as 1; result dim = max of the two.

```
(256,256,3) + (3,)      -> (256,256,3)     # ok
(8,1,6,1)  + (7,1,5)    -> (8,7,6,5)       # ok
(4,3)      + (4,)       -> ValueError      # trailing 3 vs 4
```

DO
- Add axes to align: `a[:, np.newaxis] + b` (or `a.reshape(-1, 1)`) for outer-style ops.
- Read the error: "operands could not be broadcast together with shapes ..." names the two shapes.

DON'T
- Don't broadcast a `(n,)` against `(n,1)` blindly — you get an `(n,n)` matrix, rarely intended.

## Views vs copies

- **Views** (share buffer, mutation propagates): basic slicing `a[1:3]`, `.T`/`.transpose()`, `.reshape()` *when possible*, `.ravel()`, `.view()`.
- **Copies** (independent buffer): fancy indexing `a[[1,2]]`, boolean indexing `a[a>5]`, `.flatten()`, `.copy()`.

DO
- Verify with `np.shares_memory(a, b)` (exact) or `np.may_share_memory` (fast, conservative). `.base` tells view (`is orig`) vs copy (`None`) but is fragile on chains.
- Use `.reshape(-1)` over `.flatten()` when a view is acceptable (avoids a copy).
- `.copy()` explicitly before mutating a slice you don't want to alias.

DON'T
- Don't assume `reshape` is free after `.T` — transpose is non-contiguous, so `x.T.reshape(-1)` copies. Check `a.flags['C_CONTIGUOUS']`/`['F_CONTIGUOUS']`.
- Don't mutate a slice and expect the original untouched — slices are views.

## Axis semantics

- `axis=0` collapses rows (per-column result); `axis=1` collapses columns (per-row). `axis=None` reduces all.
- Keep rank for broadcasting: `a - a.mean(axis=1, keepdims=True)`.
- Negative axes count from the end (`axis=-1` = last).

## Fancy & boolean indexing

DO
- Boolean mask to select/assign: `a[a < 0] = 0`; combine with `&`/`|` and **parenthesize**: `a[(a>0) & (a<1)]`.
- Integer arrays to gather/reorder: `a[[3,1,2]]`, `a[rows[:,None], cols]`.
- Assignment through fancy/boolean index writes in place (no copy): `a[idx] = vals`.

DON'T
- Don't use `and`/`or` on arrays — raises "truth value ambiguous". Use `&`/`|`/`~` (bitwise) with parens.
- Don't expect a returned fancy/boolean selection to alias the source — it's a copy.

## Memory layout

- C-order (row-major, default) vs F-order (column-major). Iterate along the contiguous axis for cache locality.
- `np.ascontiguousarray(a)` before handing to C/BLAS code expecting C-contiguous.
- Strided views are zero-copy but may hurt downstream perf; materialize with `.copy()` when a kernel needs contiguity.

## Randomness (reproducibility)

DO — modern `Generator`:
```python
rng = np.random.default_rng(seed=12345)   # PCG64; carry the object explicitly
rng.random((3, 3))                         # was np.random.rand
rng.integers(0, 10, size=5)                # was randint; endpoint=False (half-open)
rng.standard_normal(1000)                  # was randn
rng.choice(['A','B','C'], size=10, p=[.5,.3,.2])
children = rng.spawn(4)                     # independent parallel streams
```

DON'T
- Don't use global legacy state (`np.random.seed`/`np.random.rand`/`randint`/`randn`) in new code — no isolation, harder to reason about.
- Don't assume cross-version bit-stream stability from `Generator`; if you need it, use legacy `np.random.RandomState`.

## NumPy 2.0 breaking changes (migrate off 1.x)

Automate with Ruff: `ruff check --select NPY201` (ruff ≥ 0.4.8).

- **Removed constant aliases:** `np.NaN→np.nan`, `np.Inf/np.Infinity/np.infty/np.PINF→np.inf`, `np.NINF→-np.inf`, `np.PZERO→0.0`, `np.NZERO→-0.0`.
- **Removed dtype aliases:** `np.float_→np.float64`, `np.complex_→np.complex128`, `np.int0/np.uint0→np.intp/np.uintp`, `np.bool8→np.bool_`, `np.object0→np.object_`, `np.str0/np.unicode_→np.str_`, `np.bytes0/np.string_→np.bytes_`, `np.longfloat→np.longdouble`.
- **Removed funcs:** `np.round_→np.round`, `np.product→np.prod`, `np.cumproduct→np.cumprod`, `np.alltrue→np.all`, `np.sometrue→np.any`, `np.asfarray→np.asarray(..., dtype=float)`, `np.find_common_type→np.result_type`/`np.promote_types`.
- **Moved:** `arr.ptp(...)→np.ptp(arr, ...)` (method removed); `np.trapz→np.trapezoid` (deprecated alias); `np.in1d→np.isin`; `np.row_stack→np.vstack`; `np.core→np._core` (private).
- **`copy=False` now strict:** `np.array(x, copy=False)` raises `ValueError` if a copy is required. Use `np.asarray(x)`, or `copy=None` for "copy only if needed".
- **NEP 50 promotion:** scalars keep precision — `np.float32(3) + 3.` stays `float32` (was `float64`). Watch integer overflow. Debug with `np._set_promotion_state("weak_and_warn")`; cast explicitly or use `.item()`.
- **ABI break:** C-extension packages must be recompiled against 2.x.

Version-guard imports that moved:
```python
if np.lib.NumpyVersion(np.__version__) >= "2.0.0b1":
    from numpy.exceptions import AxisError
else:
    from numpy import AxisError
```

## Sources
- https://numpy.org/doc/stable/
- https://numpy.org/doc/stable/numpy_2_0_migration_guide.html
- https://numpy.org/doc/stable/reference/random/generator.html
- https://numpy.org/doc/stable/user/basics.broadcasting.html
- https://numpy.org/doc/stable/user/basics.copies.html

# NumPy — core digest

Current: 2.x (2.5). NEP 50 scalar promotion is default: `np.float32(3)+3.` stays float32 — watch precision loss / int overflow. Migrate 1.x→2.x with `ruff --select NPY201`.

DO
- Vectorize: array ops in C, never Python loops over rows (`a*2+1`, not comprehensions).
- Reproduce with `rng = np.random.default_rng(seed)`; `rng.integers/normal/random`. PCG64, no global state.
- Broadcast (dims equal or 1) instead of tiling/copies.
- Prefer views; use `.copy()` when you must not alias source data.
- Check with `arr.dtype`, `arr.shape`; cast explicitly (`arr.astype(np.float64)`).

DON'T
- Use removed 2.0 aliases: `np.float_`→`float64`, `np.NaN/np.Inf`→`nan/inf`, `np.product/round_/sometrue/alltrue`→`prod/round/any/all`, `np.in1d`→`isin`, `np.trapz`→`trapezoid`, `np.row_stack`→`vstack`.
- Rely on legacy `np.random.seed`/global funcs for new code.
- Call removed methods: `arr.ptp()`→`np.ptp(arr)`, `arr.newbyteorder()`→`arr.view(...)`.
- Pass `np.array(x, copy=False)` expecting no-copy — now raises if copy needed; use `np.asarray(x)`.
- Compare floats with `==`; use `np.isclose/allclose`. Test emptiness with `arr.size==0`, never truthiness of arrays.

Commands: `ruff check . --select NPY201` (2.0 autofix); `np.__version__`; `np.lib.NumpyVersion(np.__version__) >= '2.0.0'` for version gates.

Deep dive when writing non-trivial numpy — read lore/numpy/{arrays-and-vectorization}.md

Sources: numpy.org/doc/stable/ + /numpy_2_0_migration_guide.html

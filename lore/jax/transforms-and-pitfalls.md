# jax — Transforms & pitfalls

Current: **JAX 0.10.2** (Jun 2026). Assumes Python lore exists separately. JAX = NumPy-style API + composable transforms (`jit`, `grad`, `vmap`, sharding) over XLA on CPU/GPU/TPU. Transforms only work on **pure functions over immutable arrays**. Break purity and you get silently stale results, not errors.

## DO — write pure, functional code
- Route all input through args, all output through returns. Same inputs → same outputs.
- Keep transient state local (local dicts, loop vars are fine); never read/write module globals inside a transformed fn.
- Pass arrays, not Python lists/tuples — each element becomes a separate traced var (linear tracing cost). `jnp.sum(jnp.array(xs))`.

```python
@jax.jit
def step(params, x):        # pure: no globals, no I/O
    return params @ x
```

## DON'T — rely on side effects
- `print`/logging inside a `jit`'d fn fires only on the **first** trace; later calls hit the cached compilation. Use `jax.debug.print(...)` for runtime values.
- Don't capture globals expecting freshness — they're frozen at first trace. Don't feed iterators (hidden state) to `jit`/`scan`/`fori_loop`.

## DO — treat arrays as immutable
- No item assignment. Use the functional `.at` API (returns a new array; XLA elides the copy inside `jit`).

```python
x = x.at[idx].set(y)      # not x[idx] = y
x = x.at[idx].add(y)      # also .mul/.min/.max/.get
```

## DON'T — expect NumPy mutation semantics
- `x += 1` **rebinds** the name (no `__iadd__` on arrays); it does not mutate in place.
- Out-of-bounds is silent (accelerators can't throw): gathers **clamp** to edge, scatters are **dropped**. Guard with `x.at[i].get(mode='fill', fill_value=jnp.nan)`.

## DO — manage PRNG state explicitly
- Modern typed keys: `jax.random.key(seed)` (JEP 9263). `PRNGKey` is the legacy raw-key API — prefer `key` for new code.
- Consume via explicit key arg; **split** to fork independent streams. A key is not mutated by consumption — reusing it repeats the draw.

```python
key = jax.random.key(0)
key, sub = jax.random.split(key)     # advance; discard old
val = jax.random.normal(sub, (3,))
key, *subs = jax.random.split(key, 5)  # fan out
```

## DON'T — reuse or thread keys naively
- Never pass the same key to two draws expecting independence — correlated outputs.
- No sequential-equivalence guarantee vs NumPy: N single draws ≠ one batched draw (this is what makes `vmap` over keys correct). For per-example randomness, `vmap` a fn that takes a split key.

## DO — use structured control flow on traced values
- Python `if`/`for`/`while` branch on **concrete** values only. Under trace, predicates are tracers with no value → use `lax` primitives (also keeps compile fast / rolls loops).

```python
y = jax.lax.cond(p > 0, lambda: f(x), lambda: g(x))
carry, ys = jax.lax.scan(body, init, xs)   # loop with carry
i = jax.lax.fori_loop(0, n, body, i0)
```

## DON'T — branch/shape on traced data
- `ConcretizationTypeError` / `TracerBoolConversionError` = you used a traced value in Python control flow, `bool()`, or `.item()`.
- Shapes must be **static** (value-independent) under transforms. Boolean/mask indexing `x[mask]` fails (`NonConcreteBooleanIndexError`) — use `jnp.where(mask, x, 0)`.
- Mark genuinely-static args with `static_argnums`/`static_argnames` (triggers recompile per distinct value — don't make hot floats static).

## DON'T — leak tracers
- A `Tracer` escaping its transform (stored in a global/attr, returned via side channel) → `UnexpectedTracerError`. Return values; don't stash them.

## DO — compose transforms
- They nest freely: `jax.jit(jax.grad(jax.vmap(f)))`.
- `grad` needs scalar output; use `has_aux=True` for `(loss, aux)`, `value_and_grad` for both. `grad` differentiates arg 0 by default (`argnums=`).
- `vmap(f, in_axes=..., out_axes=...)` vectorizes — replace Python row loops with it. Batch over PRNG keys, not shared state.

## DO — parallelize with sharding (not pmap)
- Prefer **automatic parallelism**: put arrays on a device mesh and let `jit`/XLA partition. `pmap` is the older single-axis API; use sharding / `shard_map` for new multi-device code.

```python
mesh = jax.make_mesh((len(jax.devices()),), ('x',))
sh = jax.sharding.NamedSharding(mesh, jax.sharding.PartitionSpec('x'))
xd = jax.device_put(x, sh)      # jit'd fns then run distributed
```

- `shard_map` gives explicit per-shard code + manual collectives when you need control.

## Numerics & debugging
- **float32 by default**; float64 requests silently truncate. Enable **at startup**: `jax.config.update("jax_enable_x64", True)` or `JAX_ENABLE_X64=True`. (XLA lacks 64-bit convs on some backends.)
- Chase bad values with `jax.config.update("jax_debug_nans", True)` (and `jax_debug_infs`).
- Type-promotion and unsafe-cast rules differ from NumPy (JAX clamps where NumPy wraps).

## Ecosystem (verify pins per project)
- **Flax** — neural nets. `flax.nnx` (NNX) is the current API for new work; `flax.linen` is the prior functional API. **Optax** — composable optimizers/schedules (`optax.adam`, `chain`, `apply_updates`). **Orbax** — checkpointing. All keep JAX's pure/functional contract: params are pytrees you thread explicitly.

## Sources
- https://docs.jax.dev/en/latest/notebooks/Common_Gotchas_in_JAX.html
- https://docs.jax.dev/en/latest/random-numbers.html
- https://docs.jax.dev/en/latest/multi_process.html
- https://docs.jax.dev/en/latest/changelog.html
- https://docs.jax.dev/en/latest/

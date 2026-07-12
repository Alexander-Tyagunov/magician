# JAX — core

Version: 0.10.x (2026). `import jax.numpy as jnp`. Functional + immutable; transforms compose: `jit`, `grad`, `vmap`.

DO keep functions pure — inputs via args, outputs via return; no side effects (`print`, global mutation) inside `jit`/`scan`/`cond` (they run once at trace, then cache).
DON'T mutate arrays: `x[i]=y` errors. DO `x = x.at[i].set(y)` (also `.add`, `.get`, out-of-place).
DO random with typed keys: `k=random.key(0)`; split before reuse `k,sub=random.split(k)`; NEVER reuse a key (same input→same output). Prefer `key()` over legacy `PRNGKey()`.
DON'T use Python `if`/`for` on traced values under `jit` — use `lax.cond`/`lax.scan`/`lax.fori_loop`. Mark value-dependent args `static_argnums=`.
DON'T boolean-mask index (`x[mask]`) under `jit` (dynamic shape) → `jnp.where(mask, x, 0)`. Shapes must be static.
DON'T pass lists: `jnp.sum([1,2])` errors → `jnp.array(x)`.
KNOW out-of-bounds is silent: gather clamps, scatter skips; set `.at[i].get(mode='fill', fill_value=jnp.nan)`.
KNOW default is float32. Enable 64-bit at startup only: `jax.config.update("jax_enable_x64", True)` or `JAX_ENABLE_X64=True`.
DO seed all randomness via keys for reproducibility. Vectorize with `vmap`, not Python row loops. `pmap` is legacy → prefer `jit` + sharding/`shard_map`.
DEBUG NaNs: `jax.config.update("jax_debug_nans", True)`.

Deep dive when writing non-trivial jax — read lore/jax/{transforms-and-pitfalls}.md

Sources: docs.jax.dev (Common_Gotchas, random-numbers, changelog 0.10.2)

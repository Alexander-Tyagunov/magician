Common AI mistakes: chained indexing (`df['a']['b']`) causing SettingWithCopyWarning; modifying a slice; iterating with `iterrows` instead of vectorized operations.
Commands: test: `pytest`, lint: `ruff check .`.
Gotchas: use `.loc` and `.iloc` for indexing; `copy()` explicitly when you need an independent DataFrame; `groupby` + `agg` is faster than `apply` for standard aggregations.

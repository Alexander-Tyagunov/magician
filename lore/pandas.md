# pandas — core

Version cue: 3.0 (Jan 2026) makes Copy-on-Write default+only & string dtype default (Arrow-backed); 2.x has CoW opt-in (`pd.options.mode.copy_on_write=True`), stable since 2.1. Check `pd.__version__`.

DO
- Assign with `df.loc[mask, "col"] = v` — single-step, label-based.
- Vectorize: column ops, `.map`, `np.where`, `.groupby().agg`; reach for `.apply(axis=1)` only as last resort.
- Reassign (`df = df.assign(...)`); treat every derived frame as a copy (CoW). Add explicit `.copy()` when you need an independent frame.
- Read big/typed data with `dtype`/`parse_dates`/`usecols`; consider `dtype_backend="pyarrow"`.
- Use `pd.NA`/nullable dtypes; test missing with `.isna()`.

DON'T
- No chained assignment `df[m]["c"]=v` — raises `ChainedAssignmentError` under CoW (silent/warn pre-3.0).
- Don't rely on `inplace=` mutating a parent through a column view; won't propagate under CoW — reassign.
- Don't loop `for i,row in df.iterrows()` to compute — slow; vectorize.
- Don't chase `SettingWithCopyWarning` — gone under CoW; use `.loc`.
- Don't mutate `df.to_numpy()` result (read-only under CoW); don't compare with `== np.nan`; don't assume `object` string cols in 3.0.

Commands: test `pytest`; lint `ruff check .`.

Deep dive when writing non-trivial pandas — read lore/pandas/{idioms-and-performance}.md

## Sources
pandas.pydata.org/docs/user_guide/copy_on_write.html; /docs/whatsnew/v3.0.0.html; /docs/whatsnew/index.html

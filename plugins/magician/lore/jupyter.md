# JUPYTER — core digest

Version: JupyterLab 4.6 current; Notebook 7 (built on JupyterLab) replaced classic Notebook 6 — 7.0 needs Python 3.8+, current 7.6 needs 3.10+. `nbclassic` = legacy-UI compat shim only — don't build new work on it.

DO
- Restart Kernel & Run All before trusting/committing — hidden state & out-of-order cells lie. `[n]` = execution order, not top-to-bottom.
- Strip outputs before commit: `jupyter nbconvert --clear-output --inplace` or nbstripout — outputs bloat diffs & leak data.
- Diff/merge with nbdime, never a raw-JSON git merge.
- CI/headless reproducibility: `jupyter nbconvert --to notebook --execute`.
- Set seeds; pin the env; confirm the kernel via `jupyter kernelspec list` (a notebook may run a different env than your shell).
- Editing imported modules: `%load_ext autoreload` then `%autoreload 2`.

DON'T
- No secrets/API keys in cells or outputs — use env vars; outputs persist in the .ipynb.
- Don't trust stale state after edits — restart kernel to reclaim memory & re-validate.
- Don't install mid-notebook unrecorded — breaks reproducibility.
- Don't assume `!pip` targets the kernel's env; use `%pip install`.

Magics: `%timeit` · `%%time` · `%matplotlib inline` · `%pip`
Commands: `jupyter lab` · `jupyter notebook` · `jupyter nbconvert` · `jupyter kernelspec list`

## Sources
docs.jupyter.org/en/latest · jupyterlab.readthedocs.io (4.6 changelog) · jupyter-notebook.readthedocs.io/migrate_to_notebook7

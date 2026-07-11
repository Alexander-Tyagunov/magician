Common AI mistakes: not restarting kernel to verify reproducibility; hidden state from out-of-order cell execution; not clearing outputs before committing; mixing exploration and production logic in notebooks.
Commands: run: `jupyter notebook`, convert: `jupyter nbconvert --to script notebook.ipynb`.
Gotchas: Cell execution order matters — always restart and run all before sharing; use `%matplotlib inline` for inline plots; `nbstripout` helps keep diffs clean.

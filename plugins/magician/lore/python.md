Common AI mistakes: mutable default arguments (`def f(x=[])`); not using f-strings (Python 3.6+); shadowing builtins (list, dict, type); bare `except:` catching everything including KeyboardInterrupt.
Commands: test: `pytest`, lint: `ruff check .`, format: `ruff format .`, type-check: `mypy .`.
Gotchas: walrus operator (:=) available Python 3.8+; `dataclasses` preferred over manual `__init__`; use `pathlib.Path` not `os.path`.

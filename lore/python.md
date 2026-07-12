# Python — core digest

Version cue: 3.12+ `type`/`def f[T]` params (PEP695), f-string nesting (PEP701); 3.11+ `ExceptionGroup`/`except*`, `asyncio.TaskGroup`, `tomllib`; 3.10+ `match`, `X|Y` (PEP604); 3.9+ builtin generics `list[int]` (PEP585). Newest stable 3.14; 3.9 EOL. Free-threading experimental in 3.13 (PEP703), officially supported in 3.14 (PEP779); JIT (PEP744) still experimental.

DO type public APIs; check with mypy/pyright. Prefer `list[int]`/`str | None`; on 3.8/3.9 add `from __future__ import annotations` to backport syntax.
DO use `pathlib.Path` over `os.path`; use `with` for files/locks/conns.
DO raise specific exceptions; log with `%`-args (`log.info("x=%s", v)`), not f-strings.
DO prefer `@dataclass`/`enum` over ad-hoc tuples/dicts; `frozen=True` for value objects.
DON'T use mutable default args (`def f(x=[])`) — use a `None` sentinel.
DON'T `except:` bare or swallow errors; don't `assert` for runtime checks (`-O` strips them).
DON'T block the event loop in async; don't rely on the GIL for safety on 3.13t builds.

Commands: `uv sync` / `uv add pkg` / `uv run pytest -q`; `uvx ruff check --fix && uvx ruff format`; `uvx mypy .`.

Deep dive when writing non-trivial Python — read lore/python/{language-and-idioms,typing,asyncio,errors-and-resources,performance-and-concurrency,packaging-and-envs,testing-and-tooling}.md

## Sources
docs.python.org/3/whatsnew (3.10–3.14); peps.python.org (585,604,634,654,680,695,701,703,744); docs.astral.sh/{uv,ruff}; docs.pytest.org; mypy.readthedocs.io

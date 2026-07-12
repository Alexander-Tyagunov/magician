# Python — Testing & tooling

Modern stack (2026): **pytest** for tests, **ruff** for lint+format, **mypy** or **pyright** for types, **coverage.py** for coverage, **nox/tox** for matrices, **pre-commit** for gates. Prefer these over stdlib `unittest` boilerplate when they are available.

Current versions: pytest 9.x, ruff 0.15.x, mypy 2.x, pyright 1.1.x, coverage 7.15.x, tox 4.x, nox, pre-commit 4.x. Version floors matter: pytest 9, mypy 2, coverage 7.15, tox, nox, and pre-commit all require **Python 3.10+**. On Python 3.9 pin `pytest<9` and `mypy<2`; Python 3.8 is EOL and needs older still (`pytest<8.4` — 8.4 dropped 3.8). ruff and pyright run on 3.7+.

## pytest

DO
- Write plain functions named `test_*` with bare `assert`; pytest rewrites asserts to show rich diffs. No `self.assertEqual`.
- Use **fixtures** for setup/teardown. `yield` splits setup from teardown; the code after `yield` runs even if the test fails.
- Scope fixtures: `@pytest.fixture(scope="function"|"class"|"module"|"session")`. Default is `function`.
- Put shared fixtures in **`conftest.py`** — auto-discovered up the directory tree, no import needed.
- Parametrize with `@pytest.mark.parametrize("a,b,expected", [(1,2,3),(4,5,9)])`; add `ids=...` for readable case names. Stack decorators for a cross product.
- Use built-in fixtures: **`tmp_path`** (a `pathlib.Path`, per-test temp dir), `tmp_path_factory` (session scope), `capsys`/`capfd` (capture output), `caplog` (assert log records).
- Use **`monkeypatch`** for scoped patching — auto-undone: `setattr`, `setenv`, `delenv(raising=False)`, `setitem`, `chdir`, `syspath_prepend`.
- Assert exceptions with the context manager and a regex: `with pytest.raises(ValueError, match="bad input"):`. Inspect via `excinfo.value`.
- Register custom markers in config (`[tool.pytest.ini_options] markers=[...]`) to avoid `PytestUnknownMarkWarning`; select with `pytest -m "slow and not flaky"`.
- Configure once in `pyproject.toml` under `[tool.pytest.ini_options]` (`testpaths`, `addopts`, `markers`).

DON'T
- Don't share mutable state across tests via module globals — use a fresh fixture.
- Don't `os.chdir`/`os.environ[...]=` manually — use `monkeypatch` so it's reverted.
- Don't write to the repo tree or `/tmp` by hand — use `tmp_path`.
- Don't put a bare `pytest.raises(Exception)` with no `match` — it hides the wrong error.
- Don't overuse `autouse=True` fixtures; they run everywhere and hide dependencies.

```python
import pytest

@pytest.fixture
def client(tmp_path):
    db = tmp_path / "test.db"
    c = make_client(db)
    yield c
    c.close()                      # teardown after yield

@pytest.mark.parametrize("n,expected", [(0, 1), (5, 120)], ids=["zero", "five"])
def test_factorial(n, expected):
    assert factorial(n) == expected

def test_rejects_negative():
    with pytest.raises(ValueError, match="negative"):
        factorial(-1)

def test_env(monkeypatch):
    monkeypatch.setenv("MODE", "test")
    assert load_config().mode == "test"
```

## ruff — one tool for lint + format

DO
- Use `ruff` to replace black + flake8 + isort + pyupgrade (and dozens of plugins) — 10–100x faster.
- Lint: `ruff check .`  ·  auto-fix: `ruff check --fix .`  ·  format: `ruff format .`.
- CI-safe format check: `ruff format --check .`.
- Configure in `pyproject.toml`; set `target-version` so pyupgrade/syntax rules match your floor.

```toml
[tool.ruff]
line-length = 88
target-version = "py310"          # gate rules to your minimum Python

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]  # pycodestyle, pyflakes, isort, pyupgrade, bugbear
ignore = ["E501"]                    # line length handled by formatter
```

DON'T
- Don't run black/isort/flake8 alongside ruff — redundant and conflicting. Pick ruff.
- Don't hand-sort imports — ruff's `I` rules do it.
- Don't skip `target-version`; without it `UP` rules may rewrite to syntax your runtime lacks.

## Types — mypy or pyright

DO
- Type public functions; run `mypy .` or `pyright` in CI. Start lax, ratchet up.
- Enable strictness gradually: `[tool.mypy] strict = true` (or per-flag) once clean.
- Match `python_version` to your floor so version-specific type checks apply.

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
```

DON'T
- Don't sprinkle `# type: ignore` without a code — use `# type: ignore[arg-type]`.
- Don't use pre-3.9 `typing.List/Dict/Optional` on new code when your floor allows built-ins (see version notes).

## coverage.py

DO
- Run through coverage: `coverage run -m pytest` then `coverage report -m` (`-m` shows missing lines); `coverage html` for `htmlcov/`.
- Enable **branch coverage** and fail-under threshold in config.

```toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
show_missing = true
fail_under = 85
```

DON'T
- Don't chase 100% — assert branches and error paths, not trivial getters.
- `pytest-cov` (`pytest --cov=src`) is convenient but usually unnecessary; plain `coverage run -m pytest` works.

## Matrices — nox / tox

DO
- Use **tox** (declarative, `tox.ini`/`pyproject.toml`) or **nox** (Python-scripted `noxfile.py`) to test across interpreters/deps.
- Reserve them for real matrices; a single-env project just runs `pytest`.

```python
# noxfile.py
import nox
@nox.session(python=["3.10", "3.11", "3.12", "3.13"])
def tests(session):
    session.install(".[test]")
    session.run("pytest")
```

## pre-commit

DO
- Add a `.pre-commit-config.yaml` with ruff (lint + format) hooks; run `pre-commit install` once, `pre-commit run --all-files` to backfill. Pin `rev:` to a released tag.

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.21
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

DON'T
- Don't leave `rev:` unpinned or floating — reproducibility breaks.

## Version-adaptive reminders (affect type hints & syntax in tests)

- **3.9**: built-in generics `list[int]`, `dict[str, int]` (no `typing.List`).
- **3.10**: `X | Y` unions (`int | None` over `Optional[int]`), structural `match`.
- **3.11**: `ExceptionGroup`/`except*`, `asyncio.TaskGroup`, `tomllib` (read TOML config without a dep). pytest 8+ supports asserting `ExceptionGroup`.
- **3.12**: PEP 695 `type` aliases and `def f[T](...)` generics; improved f-string grammar.
- **3.13**: experimental free-threaded (no-GIL) build and experimental JIT — coverage 7.15 supports free-threading; expect flakier third-party support.
Give the modern form when the target allows it, the older fallback otherwise — never emit syntax newer than the project's `target-version`/`python_version`.

## Sources
- pytest — https://docs.pytest.org/en/stable/
- pytest monkeypatch — https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- ruff — https://docs.astral.sh/ruff/
- ruff configuration — https://docs.astral.sh/ruff/configuration/
- coverage.py — https://coverage.readthedocs.io/en/latest/
- mypy — https://mypy.readthedocs.io/en/stable/
- pyright — https://microsoft.github.io/pyright/
- nox — https://nox.thea.codes/  · tox — https://tox.wiki/
- pre-commit — https://pre-commit.com/  · ruff-pre-commit — https://github.com/astral-sh/ruff-pre-commit
- PyPI release metadata (versions/requires-python) — https://pypi.org/
- Python version features — https://docs.python.org/3/whatsnew/  · PEP 695 — https://peps.python.org/pep-0695/

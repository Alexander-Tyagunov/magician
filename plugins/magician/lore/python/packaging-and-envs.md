# Python — Packaging & environments

`pyproject.toml` is the single config file (PEP 621 `[project]` metadata + PEP 517/518 `[build-system]`). `uv` is the modern default toolchain; `pip`+`venv` is the always-available baseline. Never install into system Python; never commit code without a lockfile.

## DO — modern default (uv)
- DO use `uv` — one Rust tool replacing `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `virtualenv`, `twine`. It manages the interpreter, the `.venv`, and the lockfile.
- DO scaffold with `uv init` (app) / `uv init --package` (distributable, wires the `uv_build` backend). It writes `pyproject.toml` + `.python-version`.
- DO add deps with `uv add httpx` (writes to `[project].dependencies` with a bound + updates `uv.lock`); remove with `uv remove`. Constrain inline: `uv add "httpx>=0.27"`.
- DO run everything through `uv run <cmd>` — it auto-locks and auto-syncs the env first, so it is always current. No manual activate needed.
- DO commit `uv.lock` (a universal, cross-platform lockfile). In CI use `uv sync --locked` (errors if the lock is stale) or `--frozen` (use lock as-is, no check).
- DO refresh explicitly: `uv lock --upgrade` (uv never auto-upgrades on new releases). Verify with `uv lock --check`.
- DO manage interpreters with uv: `uv python install 3.12`, `uv python pin 3.12`.

## DO — baseline (pip + venv), no uv
- DO create/activate a venv (stdlib `venv`, Python 3.3+):
  ```bash
  python -m venv .venv
  source .venv/bin/activate      # Windows: .venv\Scripts\activate
  python -m pip install -U pip
  ```
- DO invoke pip as `python -m pip` (targets the active interpreter unambiguously).
- DO pin transitively. `pip freeze > requirements.txt` captures the flat set; better, use `pip-tools`: hand-author `requirements.in`, compile `pip-compile` → hashed `requirements.txt`, install `pip-sync`. Commit the compiled file.
- DO recreate venvs, never move/copy them (shebangs hold absolute paths). Since Python 3.13 `venv` writes a `.gitignore` automatically.

## DON'T
- DON'T `pip install` into system/OS Python or globally. Always a venv (or `uv`/`pipx`). On externally-managed distros pip refuses this by default (PEP 668) — respect it, don't `--break-system-packages`.
- DON'T commit `.venv/` — it's disposable and non-portable.
- DON'T ship an app without a committed lockfile (`uv.lock` / `poetry.lock` / compiled `requirements.txt`). Loose ranges = non-reproducible builds.
- DON'T hand-edit `uv.lock`. Regenerate via `uv lock`/`uv add`.
- DON'T use bare `requirements.txt` from `pip freeze` as your source of truth — it flattens direct vs. transitive and loses intent.

## pyproject.toml — the contract
```toml
[project]                                   # PEP 621, static metadata
name = "mypkg"
version = "0.1.0"                            # or: dynamic = ["version"]
requires-python = ">=3.9"
dependencies = ["httpx>=0.27", "rich"]      # PEP 508 specifiers

[project.optional-dependencies]             # extras: published, install via mypkg[plot]
plot = ["matplotlib"]

[project.scripts]                           # console entry point
mycli = "mypkg.cli:main"

[dependency-groups]                         # PEP 735 (Final, 2024), local-only, NOT published
dev = ["pytest", "mypy", "ruff"]
lint = ["ruff"]
test = ["pytest", {include-group = "lint"}] # groups can include other groups

[build-system]                              # PEP 518 requires + PEP 517 backend
requires = ["hatchling"]
build-backend = "hatchling.build"
```
- Extras (`optional-dependencies`) vs. dependency groups (`[dependency-groups]`): extras are **published** package metadata and require building a dist; groups are **dev-time only**, never appear in the wheel/sdist, and work for non-package projects. Use groups for test/lint/typecheck tooling.
- uv maps `uv add --dev X` → `dev` group; `uv add --group lint X` → named group; `uv sync` includes `dev` by default (`--no-dev` / `--only-group` / `--all-groups` to control). The legacy `[tool.uv] dev-dependencies` is deprecated — use `[dependency-groups]`.

## Build backends (PEP 517)
Choose one; declared in `[build-system]`:
- `hatchling` → `hatchling.build` — modern, common default.
- `setuptools` → `setuptools.build_meta` — legacy/extension modules (C).
- `flit_core` → `flit_core.buildapi` — minimal pure-Python.
- `pdm-backend` → `pdm.backend`.
- `uv_build` → `"uv_build"` — uv's own, fast, **pure-Python only** (use hatchling/setuptools for native extensions).

## Editable installs (dev the package while it changes)
- uv: `uv add --editable ./libs/foo`, or `uv pip install -e .`. Workspace members are editable by default.
- pip: `pip install -e .` (installs a `.pth` link; source edits take effect without reinstall).

## Poetry (alternative)
- `poetry init` / `poetry add pkg` / `poetry install`; lock in `poetry.lock` (commit it); `poetry run <cmd>`.
- Modern Poetry (2.x) reads standard PEP 621 `[project]`; older configs used `[tool.poetry]` tables. Prefer standard `[project]` for portability.

## Reading pyproject.toml in code
- Python 3.11+: stdlib `tomllib` (read-only, open file `"rb"`). Older: `tomli` (same API). Compat shim:
  ```python
  try:
      import tomllib          # 3.11+
  except ModuleNotFoundError:
      import tomli as tomllib # <=3.10
  ```

## Version cues
- `venv` stdlib 3.3+; auto-`.gitignore` in the venv 3.13+.
- `tomllib` stdlib 3.11+ (else `tomli`).
- PEP 668 externally-managed-environment marker (system pip refuses global installs) — mainstream since ~2023 (Python 3.11+ era distros).
- PEP 735 dependency groups — Final Oct 2024; needs current uv / pip 25.1+ (`pip install --group`) / tooling that adopted it.
- `requires-python` gates installs — set it to your real floor (3.9..3.14).

Commands: setup `uv sync` (or `python -m venv .venv && pip install -e ".[dev]"`); add dep `uv add X`; lock check `uv lock --check`; run `uv run pytest`.

## Sources
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- https://packaging.python.org/en/latest/specifications/pyproject-toml/
- https://packaging.python.org/en/latest/tutorials/managing-dependencies/
- https://peps.python.org/pep-0621/
- https://peps.python.org/pep-0735/
- https://docs.astral.sh/uv/
- https://docs.astral.sh/uv/concepts/projects/dependencies/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/concepts/build-backend/
- https://docs.python.org/3/library/venv.html
- https://docs.python.org/3/library/tomllib.html

# Indexing — building and keeping the graph fresh

## Build

```bash
kg init            # build the graph for the current repo
kg init --max 5000 # cap files (sampling a slice of a huge repo)
kg init --all      # confirm you really want to index a >50k-file repo
```

Prints `indexed N files · M symbols · E edges · parser=… · Ts`. The build never touches your code — it writes only under `~/.claude/magician/knowledge-graph/`.

## What gets indexed

Files are enumerated via `git ls-files` (fast, respects `.gitignore`) or an `os.walk` fallback. Language is by extension, or by **shebang** for extensionless scripts (so `bin/`-style tools are included). Ignored: `.git`, `node_modules`, `vendor`, `dist`/`build`/`out`, `.venv`, `target`, `__pycache__`, generated dirs, and files larger than `KG_MAX_FILE` (1 MB default).

## Parser cascade (best available, always works)

1. **tree-sitter** — precise AST symbols + line spans, if the `tree_sitter_language_pack`/`tree_sitter_languages` wheel is importable.
2. **universal-ctags** — accurate multi-language symbols in one batch pass, if the `ctags` binary is on PATH.
3. **regex** — a stdlib floor (approximate; flagged) covering ~15 languages.

Force one with `KG_PARSER=treesitter|ctags|regex`. `kg status` shows which ran (`parser=…`).

## Incremental refresh

```bash
kg stale      # list files changed since the last index (content-hash based)
kg refresh    # re-parse only those files, rebuild edges + ranks
```

Staleness is **content-hash** based, not mtime — a `touch` with no edit is not stale. Refresh is the steady-state path; full `kg init` is only needed for a first build or after large structural change.

## Performance levers

- **Parallel parsing:** opt-in via `KG_JOBS=N` (off by default). For typical repos **serial is faster** — ctags batch-parses in one process and per-file work is light, so process-spawn overhead dominates (measured ~14× slower in parallel at 500 files). Only worth it on very large trees parsed via tree-sitter (heavy per-file work); workers fall back to serial on any error.
- **Fast hashing:** uses `blake3`/`xxhash` if importable, else stdlib `blake2b`.
- **numpy:** if importable, PageRank runs as a vectorized mat-vec; otherwise a pure-Python power iteration (correct, just slower) — fine at repo scale.

## Monorepos

Over ~50k files, `kg init` stops and asks for `--all` or `--max N` so you don't accidentally index a giant tree. For genuinely huge graphs, a native backend (`KG_BACKEND=cozo|kuzu|duckdb`) is the opt-in escape hatch; SQLite remains the default and is more than fast enough for typical repos.

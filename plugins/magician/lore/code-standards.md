# Match the project's code standards — before you write, and before you commit

Auto-formatting (the `PostToolUse` `format.sh` hook) handles *whitespace*. It does **not** know a
project's **conventions** — "use async/await, never `.then` chains", import order, error-handling
patterns, naming, test structure. Those live in a repo's own docs and linter config, and a code
reviewer (human or bot) *will* flag them. Reading them up front is the difference between one clean
PR and going "over and over in circles" fixing style after review.

## 1. Discover + read the conventions BEFORE implementing

At the start of any implementation task in a repo, find and read (whichever exist — don't guess):
- **`CLAUDE.md` / `AGENTS.md`** at repo root and in the working subtree.
- **Code-standards docs:** `code-review.md`, `CODE_REVIEW.md`, `CONTRIBUTING*.md`, `STYLEGUIDE*.md`,
  `CODING_STANDARDS*.md`, and anything under `docs/`, `.github/`, or a `standards/` dir. Grep the
  repo for these; a team's review bot often cites one by name.
- **Linter/formatter config** for the stack — treat these as the machine-readable rules:
  - JS/TS: `.eslintrc*` / `eslint.config.*`, `.prettierrc*`, `biome.json`, `.editorconfig`, `tsconfig`
  - Python: `pyproject.toml` / `ruff.toml` / `.flake8` / `setup.cfg`, `mypy.ini`
  - Java/Kotlin: `checkstyle.xml`, `spotless`/`ktlint` config, `.editorconfig`
  - Go: `.golangci.yml`; Rust: `rustfmt.toml`, `clippy.toml`
- **The neighbours:** the files you're about to touch and their siblings — mirror the patterns
  already there (promise style, DI, logging, test naming) over your own defaults.

Note the conventions that a formatter can't enforce (e.g. async/await over `.then`, no `console.log`,
FR-CA vs FR, error-wrapping) and **apply them as you write** — not after a reviewer points them out.

## 1b. Magician's bundled language lore — a baseline, below the repo's own rules

Magician ships per-language guidance under the plugin's `lore/` directory. The SessionStart hook
already injects the concise core `lore/<stack>.md` for each **detected** stack. Some stacks also
have a **deep-dive directory** (`lore/<stack>/<topic>.md` — e.g. Rust: `ownership-and-errors`,
`type-safety`, `performance`, `async`, `patterns-and-api`, `clippy-lints`). When you're about to
write **non-trivial** code in such a stack, read the relevant topic file first — resolve it under
the plugin root (`${CLAUDE_PLUGIN_ROOT}/lore/<stack>/…` in Claude Code, `$PLUGIN_ROOT/lore/<stack>/…`
in Codex), or via the relative link a skill gives you.

**Precedence:** the repo's own conventions and linter config (step 1) always win on any conflict.
This bundled lore is the default you reach for when the repo is silent — not an override of it. The same
`lore/<stack>/` model now also covers **databases**: per-engine cores + a `performance` playbook (e.g.
`lore/postgres/…`, `lore/mongodb/…`, `lore/pinecone/…`) plus the shared `lore/databases/…` foundation,
injected when an engine is detected. **Escape hatch:** if the bundled lore ever conflicts with the user's
project/local knowledge, it's fully switchable off — `magician-ui lore off`, a per-project
`.magician/lore.off`, or `MAGICIAN_LORE=0` (the status bar then shows `📚 lore:off`).

## 2. Style is a commit GATE, not a post-review fixup

Before committing a unit, run the project's **formatter + linter** (the real ones the CI/reviewer
uses, discovered above — e.g. `npm run lint` / `eslint --fix`, `ruff check --fix`, `golangci-lint
run`, `mvn spotless:apply checkstyle:check`), plus type-check. **Fix style/lint before the commit.**
A convention violation the reviewer would flag is a failing gate — resolve it now, don't ship it and
wait for the round-trip. If a documented convention isn't lint-enforced (it lived only in
`code-review.md`), you still hold to it — you read it in step 1.

Reuse over reinvention: run the repo's configured tools; never hand-roll a formatter or invent style
rules the project doesn't use.

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

## 2. Style is a commit GATE, not a post-review fixup

Before committing a unit, run the project's **formatter + linter** (the real ones the CI/reviewer
uses, discovered above — e.g. `npm run lint` / `eslint --fix`, `ruff check --fix`, `golangci-lint
run`, `mvn spotless:apply checkstyle:check`), plus type-check. **Fix style/lint before the commit.**
A convention violation the reviewer would flag is a failing gate — resolve it now, don't ship it and
wait for the round-trip. If a documented convention isn't lint-enforced (it lived only in
`code-review.md`), you still hold to it — you read it in step 1.

Reuse over reinvention: run the repo's configured tools; never hand-roll a formatter or invent style
rules the project doesn't use.

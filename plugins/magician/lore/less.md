# Less (core)

CSS preprocessor, framework-agnostic (any stack). Compiles `.less`→CSS via Node `lessc`. "CSS with a little more."

Version: current **v4.x** (4.6.x) vs prior **v3.x**. v4 migration headline: **`/` no longer divides outside parens** — `10px / 2` emits literally; wrap in parens `(10px / 2)` or use `calc()`. Maps added v3.5; property/value accessors `[@x]` v3.5.

DO
- Use `@var` for variables (NOT `$` — that's Sass); lazy-eval, last-in-scope wins.
- Nest with parent selector `&`: `&:hover`, `&-item`.
- Parametric mixins with guards: `.m(@c) when (iscolor(@c)){...}`.
- `:extend` (or `&:extend(.x all)`) over mixins when you want to merge selectors and shrink output.
- Scope math/vars: wrap in `(...)`; import reuse-only files with `@import (reference) "base";`.
- `@import (optional)` missing files; `(inline)` raw CSS; `(once)` (default).
- Add JS functions via `@plugin "p.js";` (v2.5+).
- Precompile with `lessc` (or Vite/webpack `less-loader`) for prod.

DON'T
- Don't ship browser `less.js` runtime to prod — dev only.
- Don't rely on optional mixin parens (`.m` vs `.m()`) — deprecated; always call `.m()`.
- Don't use `>` / whitespace between namespaces — deprecated.
- Don't unlock caller-scope vars/mixins — use accessors `[@result]` instead.
- Don't expect division from bare `/` in v4.

Commands: `npm i -D less` · `npx lessc src.less out.css` · `npx lessc --source-map src.less out.css`

## Sources
lesscss.org/features/ · lesscss.org/usage/ · npm `less` 4.6.7

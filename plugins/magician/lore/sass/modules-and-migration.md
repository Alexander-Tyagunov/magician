# sass — Module system & migration

Framework-agnostic preprocessor (React/Vue/Svelte/Angular/plain — anything a bundler compiles). **Dart Sass is the only maintained implementation.** LibSass reached EOL 2025-10-23; `node-sass` (LibSass wrapper) EOL 2024-07-24; Ruby Sass dead. If a project still runs `node-sass`, that is a finding — migrate to `sass` or `sass-embedded`. Current line: Dart Sass 1.x (1.101.0+).

## DO — use the module system (`@use` / `@forward`)

- **`@use` to load a stylesheet.** Members are namespaced and loaded **exactly once**, no matter how many files `@use` it. Introduced **Dart Sass 1.23.0**.
  ```scss
  @use 'src/corners';           // namespace = filename => corners.$radius
  @use 'src/corners' as c;      // custom namespace => c.$radius
  .box { border-radius: corners.$radius; @include corners.rounded; }
  ```
- **`@use` must come first** — before every rule except `@forward`. One URL per rule, always quoted.
- **Configure with `with`** (variables must be `!default`; config allowed **once per module**, first load only):
  ```scss
  @use 'library' with ($black: #222, $border-radius: 0.1rem);
  ```
- **`@forward` to build a single entrypoint** for a library. Re-exports members to downstream `@use`rs but does **not** make them available in the forwarding file itself (add a separate `@use` for that). Write `@forward` before `@use` of the same module so config applies.
  ```scss
  @forward 'src/list';
  @forward 'src/list' as list-*;                 // prefix every member
  @forward 'src/list' show mixin-a, $var-b;      // allowlist
  @forward 'src/list' hide $internal-gap;        // denylist
  ```
- **`@forward ... with (... !default)`** to set opinionated defaults while still letting downstream override (Dart Sass **1.24.0**+).
- **Partials**: name shared files `_name.scss`; omit the `_` when loading (`@use 'name'`). `_index.scss` in a folder auto-loads on `@use 'folder'`.
- **Privacy**: prefix a member with `-` or `_` (`$-radius`) to keep it out of the public API. Don't `@forward` a module to keep it package-private.
- **Load built-in modules explicitly** and call functions namespaced:
  ```scss
  @use 'sass:math';
  @use 'sass:map';
  @use 'sass:color';
  .a { width: math.div($w, 2); }
  .b { color: color.adjust($c, $lightness: -10%); }
  $v: map.get($theme, 'primary');
  ```
  Seven modules: `sass:math`, `sass:string`, `sass:color`, `sass:list`, `sass:map`, `sass:selector`, `sass:meta`.

## DON'T

- **Don't `@import`.** Deprecated as of **Dart Sass 1.80.0** (2024-10-17); **removed in Dart Sass 3.0.0.** It pollutes global scope, forces member prefixing, makes `@extend` global, re-emits CSS on every import (bloat), and has no privacy. Prefer `@use`.
- **Don't use `/` for division.** Use `math.div($a, $b)`; slash-as-division is a removed behavior. `/` now means separation/`calc`.
- **Don't rely on global function names** (`map-get`, `lighten`, `adjust-hue`, …). They survive only for LibSass back-compat and the team will deprecate them — load the module and namespace the call.
- **Don't use legacy global color functions** (`lighten`/`darken`/`saturate`/`mix` globals) — breaking change. Prefer `color.adjust` / `color.scale` / `color.mix`, and the CSS-space constructors `color()`, `lab()`, `lch()`, `oklab()`, `oklch()`, global `hwb()` (Dart Sass **1.78.0**+). `color.hwb()` is deprecated for global `hwb()`.
- **Don't use the Sass `if()` function.** Deprecated in favor of CSS `if()`; supported only until Dart Sass 3.0.0. (Ternary `@if`/`@else` control flow is unaffected.)
- **Don't reconfigure a module twice** or configure after first load — errors. Set config on the first `@use`/`@forward`.
- **Don't `@use ... as *`** for third-party code — only for your own stylesheets, to avoid name collisions.

## Migration — `sass-migrator`

Automated, one feature per command. Install: `npm install -g sass-migrator` (also brew/choco/standalone).

```bash
# @import -> @use/@forward across the whole graph
sass-migrator --migrate-deps module style.scss

# preview only, verbose
sass-migrator -nv module style.scss

# also generate @forward barrels; strip a legacy prefix
sass-migrator -d module --forward=all style.scss
sass-migrator -d module --remove-prefix=app- style.scss

# / -> math.div ; legacy colors -> color-space fns ; Sass if() -> CSS if()
sass-migrator --migrate-deps division style.scss
sass-migrator --migrate-deps color style.scss
sass-migrator --migrate-deps 'if()' style.scss
```

`module` adds namespaces, converts overridden defaults to `with (...)`, strips `-`/`_` prefixes, and rewrites nested imports via `meta.load-css()`. Key flags: `--migrate-deps`/`-d`, `--dry-run`/`-n`, `--verbose`/`-v`, `--load-path`/`-I`, `--forward=none|all|prefixed`, `--remove-prefix`/`-p`, `--pessimistic` (division), `namespace` migration with `--rename`/`--force`.

## JS API — use the modern compile API

- **Modern (required going forward):** `compile(path)` / `compileString(source)` and async `compileAsync` / `compileStringAsync`. Returns a `CompileResult`.
  ```js
  import * as sass from 'sass';
  const { css } = sass.compile('style.scss');
  const out = sass.compileString('a { color: red }').css;
  ```
- **Legacy `render` / `renderSync` is deprecated** — marked deprecated in Dart Sass **1.45.0**, warnings emit since **1.79.0**, **removed in Dart Sass 2.0.0**. Do not write new code against it.
- **Packages:** `sass` (pure-JS Dart Sass, ships the CLI) or `sass-embedded` (native wrapper, generally faster, same API). Most bundlers (Vite, webpack) already call the modern API — just install `sass`. Don't add `node-sass`.

## Review checklist

- `@import` present → migrate to `@use`/`@forward`.
- `node-sass` / LibSass in deps → replace with `sass`/`sass-embedded`.
- Bare global fns (`map-get`, `lighten`, `/` division) → namespace via built-in modules / `math.div`.
- `render`/`renderSync` in build config → switch to `compile*`.
- Config vars not `!default`, or `with` used twice → will error.

## Sources

- https://sass-lang.com/documentation/at-rules/use/
- https://sass-lang.com/documentation/at-rules/forward/
- https://sass-lang.com/documentation/at-rules/import/
- https://sass-lang.com/documentation/modules/
- https://sass-lang.com/documentation/cli/migrator/
- https://sass-lang.com/documentation/js-api/
- https://sass-lang.com/documentation/breaking-changes/legacy-js-api/
- https://sass-lang.com/blog/import-is-deprecated/
- https://sass-lang.com/blog/libsass-is-deprecated/
- https://sass-lang.com/blog/node-sass-is-end-of-life/

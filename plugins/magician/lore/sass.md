# Sass (core)

Framework-agnostic CSS preprocessor (React/Vue/Svelte/Angular/plain). Use `.scss`. Dart Sass is the only live impl.

Version cue: modern `@use`/`@forward` (since 1.23.0) is current; legacy `@import` deprecated 1.80.0, removed in 3.0.0 — migrate now via `sass-migrator module --migrate-deps in.scss`.

DO
- `@use "abc"` then call `abc.$var` / `abc.fn()`; namespace = last URL segment (`as x` to rename, `as *` to flatten your own files).
- `@use` loads each file once; place `@use`/`@forward` before other rules.
- Configure libs once: `@use "lib" with ($primary: red)`; declare configurables `!default`.
- Aggregate a public API with `@forward "buttons"`.
- Import built-ins: `@use "sass:math"`, `sass:color`, `sass:map`, `sass:meta`. Use `math.div($a,$b)` not `$a/$b`; recolor with `color.adjust`/`color.scale`/`color.mix`.
- Mark privates with leading `-`/`_` (excluded from module API).

DON'T
- Don't use `@import` (global scope, re-loads, collisions) — dead in 3.0.0.
- Don't call the color fns deprecated in 1.79 (`lighten`/`darken`/`saturate`/`adjust-hue`/`opacify`/…) — use `color.adjust`/`color.scale`. `color.mix` is fine.
- Don't use `node-sass`/LibSass — deprecated since 2020, unmaintained, no `@use`. Use Dart Sass + modern JS API (`compile`/`compileString`), not legacy `render`.

Commands: `npm i -D sass`; CLI `sass in.scss out.css --watch`.

Deep dive when writing non-trivial sass — read lore/sass/{modules-and-migration}.md

Sources: sass-lang.com/documentation {at-rules/use, modules, breaking-changes/import, breaking-changes/color-functions}

# vanilla-extract (core)

Zero-runtime, type-safe CSS-in-TS. Compiles to static `.css` at build. Framework-agnostic (React/Vue/Svelte/Angular/plain); needs a bundler plugin.

Version cue: `@vanilla-extract/css` stable 1.x; `sprinkles` 1.x; `recipes` still 0.x (pre-1.0, pin it). `layer`/`globalLayer` + `createContainer` are recent 1.x — check version first.

DO
- Styles live in `*.css.ts` only; import the exported class-name string.
- Use build-time-static values in `style`/`recipe`. Theme via `createTheme`/`createThemeContract`; reference vars, don't hardcode.
- Runtime-dynamic values: `assignInlineVars`/`setElementVars` from `@vanilla-extract/dynamic` — set CSS vars via inline style, keep the rule static.
- Variants → `recipe` (`@vanilla-extract/recipes`); atomic utils → `defineProperties`+`createSprinkles` (`@vanilla-extract/sprinkles`); type props via `RecipeVariants<typeof x>`.
- Global rules only via `globalStyle`/`createGlobalTheme`/`globalLayer`.

DON'T
- No dynamic (props/state/runtime) values inside `style()` — extraction errors.
- No styles outside `.css.ts`. Don't `style` a bare selector — use `globalStyle`.
- Don't ship without the bundler plugin; no runtime CSS engine exists.

Commands: `npm i @vanilla-extract/css` + dev plugin (`@vanilla-extract/vite-plugin` | webpack-plugin | esbuild-plugin | next-plugin); add-ons `recipes|sprinkles|dynamic`.

Deep dive when writing non-trivial vanilla-extract — read lore/vanilla-extract/{zero-runtime-landscape}.md

Sources: vanilla-extract.style/documentation/*; npm @vanilla-extract/*

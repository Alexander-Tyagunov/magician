# Mantine — core digest (styling)

React-only. v9 current (needs React 19.2+). v7 was the watershed: dropped Emotion for native CSS Modules + CSS variables.

DO import `@mantine/core/styles.css` once at root; wrap app in `<MantineProvider>`; theme via `createTheme()`.
DO style with CSS Modules; override inner parts via `classNames` (Styles API), outer via `className`; theme via CSS vars (`--mantine-color-*`, `--mantine-spacing-*`).
DO use postcss-preset-mantine: `light-dark(a,b)`, `rem()`/`em()` (em in media queries), `@mixin hover`, `@mixin smaller-than $mantine-breakpoint-sm`, `alpha()/lighten()/darken()`.
DO add `<ColorSchemeScript>` + spread `mantineHtmlProps` on `<html>` for SSR.

DON'T use `createStyles`, `sx`, `theme.fn`, or `theme.colorScheme` — all removed in v7.
DON'T nest selectors in the `styles` prop (v7+) — use `classNames` + CSS Modules.
DON'T pass `color` to Text/Anchor (v9 → use `c`); `Grid gutter`→`gap`, `Collapse in`→`expanded` (v9); dates take `YYYY-MM-DD` strings, not Date objects (v8+).
DON'T forget the preset or `postcss-simple-vars` — mixins/functions silently no-op without them.

Version cue: v9 (React 19.2, defaultRadius md) ← v8 (date strings) ← v7 (Emotion→CSS Modules). Pre-v7 = Emotion/createStyles; migrate.

Commands: `npm i @mantine/core @mantine/hooks` + `npm i -D postcss postcss-preset-mantine postcss-simple-vars`.

Deep dive when writing non-trivial mantine — read lore/mantine/{styling-and-core}.md

## Sources
mantine.dev/getting-started, /styles/css-modules, /styles/postcss-preset, /changelog/{7,8,9}-0-0

# mantine — Styling & core setup

React-only component library. **v7 (Sept 2023) dropped Emotion/CSS-in-JS** for native CSS Modules + CSS variables + a PostCSS preset. This is the defining break from v6. Current line is v9.x; the v7 architecture below is unchanged through v9. Not framework-agnostic — no official Vue/Svelte/Angular port.

## Core setup — DO

- Install runtime: `@mantine/core @mantine/hooks`. Dev: `postcss postcss-preset-mantine postcss-simple-vars`.
- Import core CSS **once** at app root, before your own styles: `import '@mantine/core/styles.css';`. Required for every `@mantine/*` package.
- Wrap the app in `MantineProvider`, pass a theme from `createTheme`:
  ```tsx
  import { createTheme, MantineProvider } from '@mantine/core';
  import '@mantine/core/styles.css';
  const theme = createTheme({ primaryColor: 'blue' });
  <MantineProvider theme={theme}>{children}</MantineProvider>
  ```
- `postcss.config.cjs` — preset + breakpoint vars for the `smaller-than`/`larger-than` mixins:
  ```js
  module.exports = {
    plugins: {
      'postcss-preset-mantine': {},
      'postcss-simple-vars': { variables: {
        'mantine-breakpoint-xs': '36em', 'mantine-breakpoint-sm': '48em',
        'mantine-breakpoint-md': '62em', 'mantine-breakpoint-lg': '75em',
        'mantine-breakpoint-xl': '88em' } },
    },
  };
  ```
- SSR (Next.js): put `<ColorSchemeScript />` in `<head>` and spread `mantineHtmlProps` on `<html>` to avoid a hydration/flash mismatch.

## Core setup — DON'T

- DON'T skip `styles.css` — components render unstyled.
- DON'T author theme values in JS just to reference them in CSS — everything is a CSS variable (below).
- DON'T forget `postcss-simple-vars` if you use `@mixin smaller-than $mantine-breakpoint-sm`.

## Styling components — DO

- Prefer **CSS Modules** (`*.module.css`) — the recommended, zero-runtime path.
- Style the root with `className`; style inner elements with `classNames` (Styles API), keyed by the component's element names:
  ```tsx
  import cls from './Demo.module.css';
  <TextInput classNames={{ input: cls.input, label: cls.label }} />
  ```
- Reference theme via CSS variables, never a JS theme object:
  ```css
  .input { background: var(--mantine-color-blue-5); padding: var(--mantine-spacing-md); }
  ```
- Use **style props** for one-off root styling (shorthand → inline style on root):
  `m mt mb ml mr mx my` (margin), `p pt pb px py` (padding, → `theme.spacing`), `w h miw maw mih mah`, `c` (color), `bg` (background), `bd` (border), `bdrs` (radius), `fz` (font-size → `theme.fontSizes`), `fw ff lh ta tt td fs lts`, `pos top left inset display flex opacity`.
  - Scale keywords: `mt="xs"`, negatives `mt="-md"`, numbers → rem (`mt={16}` ⇒ `1rem`), colors `c="blue"` / `bg="orange.1"`, adaptive `c="dimmed"` / `c="bright"`.
  - Responsive object syntax (min-width breakpoints): `w={{ base: 320, sm: 480, lg: 640 }}`.
- Target variants/states via `data-*` attributes — Mantine's model is "one class + `data-*` modifiers":
  ```css
  .control { color: var(--mantine-color-black); }
  .control[data-disabled] { color: var(--mantine-color-gray-5); }        /* boolean */
  .section[data-position='left'] { margin-right: .5rem; }                 /* valued */
  ```
- Add your own data attributes with the `mod` prop: `mod={{ opened: true }}` ⇒ `data-opened`; `mod={{ someValue: 'x' }}` ⇒ `data-some-value="x"` (false ⇒ omitted).

## Styling components — DON'T

- DON'T use responsive style props in large lists — they emit per-instance media queries (slow).
- DON'T put nested selectors (`&:focus`, `@media`) in the `style`/`styles` props — v7 dropped nested-selector support there. Move them into a CSS module class.

## PostCSS preset (`postcss-preset-mantine`) — DO

Bundles `postcss-nested`, `postcss-mixins` (Mantine mixins), and `rem`/`em` functions.
- Color-scheme mixins → compile to `[data-mantine-color-scheme='...']`:
  ```css
  .root { background: var(--mantine-color-white); @mixin dark { background: var(--mantine-color-dark-7); } }
  ```
  Also `light`, `light-root`/`dark-root` (for `:root`/`html`), low-specificity `where-light`/`where-dark`.
- Breakpoints: `@mixin smaller-than $mantine-breakpoint-sm` / `larger-than` (converted to em).
- `@mixin hover` → `@media (hover: hover){&:hover}` + touch fallback. `rtl`/`ltr`/`not-rtl`/`not-ltr`.
- Functions: `rem(16px)` ⇒ `calc(1rem * var(--mantine-scale))`, `em(320px)` (media queries), `light-dark(a, b)`, `alpha(c, .5)`, `lighten`/`darken` (all via `color-mix`).
- `autoRem: true` auto-converts px→rem in `.css` (skips media/`calc`/`var`/`clamp`/`url`/`content`/color fns).

## PostCSS preset — DON'T

- DON'T call `light-dark()` on `:root`/`html` — use `light-root`/`dark-root` mixins there.
- DON'T assume `alpha`/`lighten`/`darken` work on ancient browsers — they need `color-mix`.

## CSS variables — DO

Pattern `--mantine-{category}-{key}`. Key groups:
- Colors: `--mantine-color-{name}-0..9` (10 shades **required** for custom colors); variants `-filled -filled-hover -light -light-hover -outline`; semantic `-text -body -error -default -default-border -dimmed -bright`; `--mantine-primary-color-{shade}`.
- Spacing `--mantine-spacing-{xs..xl}`, radius `--mantine-radius-{xs..xl}` + `-default`, shadows `--mantine-shadow-{xs..xl}`, font-size `--mantine-font-size-{xs..xl}`, `--mantine-line-height`, z-index `--mantine-z-index-{app|modal|popover|overlay|max}`.
- Inject custom vars with `cssVariablesResolver` on `MantineProvider` → returns `{ variables, light, dark }`.

## Dark mode — DO

- Set `defaultColorScheme="light" | "dark" | "auto"` on `MantineProvider` (and matching `ColorSchemeScript`).
- MantineProvider writes `data-mantine-color-scheme` on `<html>`; all component styles key off it.
- Read/toggle with `useMantineColorScheme()` (`setColorScheme`, `toggleColorScheme`, `clearColorScheme`); use `useComputedColorScheme()` for a resolved `'light'|'dark'` (never `auto`) in toggle logic.
- Style per-scheme with the `light`/`dark` mixins or `light-dark()` — NOT by branching on the JS `colorScheme` value.
- `forceColorScheme="dark"` locks it (must match on both provider + script; ignores managers).

## Dark mode — DON'T

- DON'T render conditionally on `colorScheme` in SSR apps — server has no localStorage → hydration mismatch. Use `light`/`dark` mixins or `lightHidden`/`darkHidden` props.

## v6 → v7 migration — DON'T (removed in v7)

- `createStyles` — **removed** from `@mantine/core`. → CSS Modules (`.root { background: var(--mantine-color-red-5); }`).
- `sx` prop — **removed**. → `className` or `style`.
- `styles` prop nested selectors — **removed**. → `classNames` (Styles API) + CSS module classes.
- `<Global>` component + theme global styles — **removed**. → import a global `.css` at entry.
- `theme.colorScheme` — **removed** from theme. → `useMantineColorScheme` / `light-dark` / mixins.
- Escape hatch: `@mantine/emotion` (added in v7.9) restores `createStyles`/`sx`/`styles` nesting for teams that must keep CSS-in-JS — opt-in, not the default. Prefer migrating to CSS Modules.

## Sources

- https://mantine.dev/getting-started/
- https://mantine.dev/styles/css-modules/
- https://mantine.dev/styles/postcss-preset/
- https://mantine.dev/styles/css-variables/
- https://mantine.dev/styles/style-props/
- https://mantine.dev/styles/data-attributes/
- https://mantine.dev/theming/color-schemes/
- https://mantine.dev/guides/6x-to-7x/

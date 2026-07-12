# mui — Theming & styling

React-only component library implementing Material Design. Styling = theme + `sx` + `styled()`.
Version cue: **v9 current** (unified major, Apr 2026), prior **v7** — there is **no MUI v8** (the number was skipped; migration path is v7→v9). Historical majors that
matter: v5 (Emotion default), v6 (Pigment CSS opt-in + stable CSS theme variables + Grid2), v7
(slots/slotProps consolidation), v9 (deprecations removed, `GridLegacy` gone). **Emotion is
still the default engine through v9** — Pigment CSS never became default.

Install (Emotion default): `npm i @mui/material @emotion/react @emotion/styled`.
styled-components engine (no SSR): `npm i @mui/material @mui/styled-engine-sc styled-components`.
Peer deps: React 17/18/19. Import styling APIs from `@mui/material/styles`.

## Theme (createTheme + ThemeProvider)

DO
- Create once at module scope; wrap the root: `<ThemeProvider theme={theme}><CssBaseline/>…`.
- Read tokens in components via `useTheme()` (or `theme` arg in `sx`/`styled`).
- Build dependent tokens in steps: `let t=createTheme({...}); t=createTheme(t,{palette:{info:{main:t.palette.secondary.main}}})`.
- Add custom tokens (`createTheme({ status:{ danger:'#…' } })`) + TS module augmentation of `Theme`/`ThemeOptions`.

DON'T
- Don't recreate the theme inside render (new object every render = full re-style).
- Don't name a custom key `vars` — reserved for CSS variables.

```js
import { createTheme, ThemeProvider, useTheme } from '@mui/material/styles';
const theme = createTheme({
  palette: { primary: { main: '#1976d2' }, secondary: { main: '#9c27b0' } },
  typography: { fontFamily: 'Inter, sans-serif', h1: { fontSize: '2rem' } },
  spacing: 8, // theme.spacing(2) → "16px"
});
```

## Tokens

- `palette`: `primary/secondary/error/warning/info/success`, each `main/light/dark/contrastText`; plus `background`, `text`, `grey`, `mode`.
- `typography`: `fontFamily`, `fontSize`, variants `h1…h6/body1/body2/button/caption/overline`.
- `spacing`: default factor **8** → `theme.spacing(2)` = `16px`; `sx` shorthand `p:2` = 16px.
- `breakpoints.values` (px): `xs:0 sm:600 md:900 lg:1200 xl:1536`. Helpers: `up/down/only/not/between`.
- Also `zIndex`, `transitions`, `shadows`, `shape.borderRadius`, `components` (per-component `defaultProps`/`styleOverrides`/`variants`).

## sx prop

Per-instance overrides on any MUI component. Theme-aware: color keys (`'success.main'`), spacing
numbers, and nested selectors (`'& .MuiSlider-thumb'`). Responsive via breakpoint objects.

```jsx
<Box sx={{ width: { xs: '100%', md: 300 }, color: 'success.main', p: 2,
           '& .MuiSlider-thumb': { borderRadius: 1 } }} />
```

DO use `sx` for one-off tweaks. Use the array form + `theme.applyStyles` for mode-conditional styles.
DON'T inline heavy `sx` objects in hot lists / large trees — with Emotion each render re-serializes
the object (runtime cost). Hoist to `styled()` or a static const outside render for repeated rows.

## styled()

For reusable styled components + prop-driven dynamic styles.

```js
import { alpha, styled } from '@mui/material/styles';
const Fancy = styled(Slider, { shouldForwardProp: p => p !== 'active' })(({ theme, active }) => ({
  color: theme.palette.success.main,
  ...(active && { boxShadow: `0 0 0 8px ${alpha(theme.palette.success.main, 0.16)}` }),
}));
```

DO use `shouldForwardProp` to keep custom props off the DOM. DO hoist `<GlobalStyles>` to a static
constant (else its `<style>` recomputes each render).

## CSS theme variables + dark mode (v6+ stable)

DO enable `cssVariables:true` for `--mui-*` CSS vars (no FOUC, SSR-friendly, native `prefers-color-scheme`).
Define `colorSchemes.light/dark`. Reference `theme.vars.palette.*` and switch with `theme.applyStyles('dark', {…})`.

```js
const theme = createTheme({
  cssVariables: true,
  colorSchemes: { light: { palette:{…} }, dark: { palette:{…} } },
});
```

DON'T use `theme.palette.mode` to branch light/dark when using CSS vars — causes flicker; use
`theme.applyStyles('dark', …)`. For SSR manual toggle, inject `InitColorSchemeScript` before hydration.

## CssBaseline

`import CssBaseline from '@mui/material/CssBaseline'` — global reset (normalize-like, `box-sizing:border-box`,
theme background/typography). Place inside `ThemeProvider`. `<CssBaseline enableColorScheme />` sets native
`color-scheme` (scrollbars, form controls). `ScopedCssBaseline` for partial adoption — import it first to
avoid box-sizing conflicts.

## Pigment CSS (zero-runtime, opt-in)

Zero-runtime CSS-in-JS: extracts colocated styles to `.css` at build time → hashed classes + CSS vars,
smaller bundle, **RSC-compatible** (theme resolved at build time). Introduced **v6** as opt-in.
Packages: `@pigment-css/react` + `@pigment-css/nextjs-plugin` (`withPigment` in `next.config`) or
`@pigment-css/vite-plugin` (`pigment()` plugin); import `@pigment-css/react/styles.css` at root.

DON'T reach for it as default: it's **alpha and development is on hold** (latest ~0.0.31). Emotion
stays the recommended/default engine. Constraint: all styles must be statically known at build time
(no arbitrary runtime values).

## Migration (v7→v9)

- `GridLegacy` removed → `Grid` with `size` prop (`<Grid size={{xs:12, md:6}}>`), no `item`/breakpoint props.
- `components`/`componentsProps` fully removed → `slots`/`slotProps` (Alert, Dialog, Drawer, Menu, Modal, Popper, Tooltip, Autocomplete, …).
- Raised browser targets (Chrome 117, Firefox 121, Safari 17). `disableEscapeKeyDown` removed → check `reason` in `onClose`.
- Codemods: `npx @mui/codemod@latest v9.0.0/system-props <path>`; `deprecations/<component>-props`.
- Bump companions to matching major: `@mui/system`, `@mui/icons-material`, `@mui/material-nextjs`, `@mui/utils`, `@mui/lab`. MUI X versions separately.

## Sources
- https://mui.com/material-ui/getting-started/installation/
- https://mui.com/material-ui/customization/theming/
- https://mui.com/material-ui/customization/how-to-customize/
- https://mui.com/material-ui/customization/breakpoints/
- https://mui.com/material-ui/customization/css-theme-variables/usage/
- https://mui.com/material-ui/react-css-baseline/
- https://mui.com/material-ui/migration/upgrade-to-v9/
- https://mui.com/material-ui/migration/upgrade-to-v6/
- https://github.com/mui/pigment-css

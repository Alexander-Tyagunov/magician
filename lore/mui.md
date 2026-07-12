# MUI (Material UI) — core

React-only; styles via Emotion `styled-engine`; implements Material Design 2. General CSS/framework lore lives elsewhere.

VERSION: current **v9** (unified with MUI X; jumped v7→v9, no v8). Prior **v7**; v6/v5 still maintained. Codemods: `@mui/codemod`.

DO
- Wrap app once: `<ThemeProvider theme={createTheme(...)}>` + `<CssBaseline/>`.
- Style with `sx` (one-offs) or `styled()` (reusable); read `theme` tokens (spacing/palette), never hardcode px.
- CSS vars: `createTheme({ cssVariables: true })` (stable v6); dark via `colorSchemes`.
- Dark styles: `theme.applyStyles('dark', {...})` (v6+), not `theme.palette.mode==='dark'`.
- Grid: `<Grid size={{ xs:12, md:6 }}>`.
- Zero-runtime/RSC: opt into Pigment CSS (`@mui/material-pigment-css`, since v6).

DON'T
- No inline `style=` (bypasses theme/vars) — use `sx`.
- No `Grid item`/`xs=`/`GridLegacy` (removed v9); no system props on Box/Stack/Typography (removed v9) — use `sx`.
- No `components`/`componentsProps` — use `slots`/`slotProps` (v9).
- No `createMuiTheme`/`experimentalStyled` (removed v7); import ≤1 level deep only.
- Don't use the styled-components engine for SSR — use Emotion.

Commands: `npm i @mui/material @emotion/react @emotion/styled` (React 17–19). Migrate: `npx @mui/codemod@latest deprecations/all .`

Deep dive when writing non-trivial mui — read lore/mui/{theming-and-styling,versions-and-md}.md
Sources: mui.com/material-ui {getting-started/installation, customization/theming, migration/upgrade-to-v7, migration/upgrade-to-v9}

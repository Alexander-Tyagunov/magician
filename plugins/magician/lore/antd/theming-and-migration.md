# antd — Theming (v5 tokens) & migration

React-only component lib (`antd`). Version cue: **v6 current** (v6.0.0 = 2025-11-22; docs at 6.5.x) = CSS-in-JS tokens + semantic `classNames`/`styles`, CSS vars default, `zeroRuntime`. **v5 prior** = introduced CSS-in-JS design tokens, dropped less. **v4 = legacy** (less + moment; do not target). `ant-design-vue` / other-framework ports are separate community projects — this lore is `antd` (React) only.

Theme model (v5+): **Seed → Map → Alias** derivation. Map derives from Seed via an *algorithm*; Alias derives from Map. Editing Seed (`colorPrimary`) regenerates whole palettes — prefer it. Defaults: `colorPrimary` #1677ff, `borderRadius` 6, `fontSize` 14, `controlHeight` 32, `wireframe` false.

## DO — v5/v6 theming
- Configure via `ConfigProvider theme={{ token, components, algorithm, cssVar, hashed, inherit }}`.
  ```tsx
  import { ConfigProvider, theme } from 'antd';
  <ConfigProvider theme={{
    token: { colorPrimary: '#1677ff', borderRadius: 8 },
    algorithm: [theme.darkAlgorithm, theme.compactAlgorithm], // array = combine
    components: { Button: { colorPrimary: '#00b96b', algorithm: true } },
  }}>{children}</ConfigProvider>
  ```
- Use the 3 built-ins: `theme.defaultAlgorithm` / `darkAlgorithm` / `compactAlgorithm`. Pass an **array** to stack (e.g. dark + compact).
- Dark/dynamic mode = swap `algorithm` at runtime; no rebuild, no CSS file swap.
- Component-level tokens under `components.<Name>`. `algorithm` there is `false` by default (v5.8.0+) → tokens only override global; set `true` (or a fn/array) to re-run algorithm.
- Read tokens in React: `const { token } = theme.useToken();`. Outside React (e.g. build a less/JS map): `theme.getDesignToken(config)`.
- `cssVar: true` emits CSS variables (`--ant-*`); one style block, cheaper theme switching, needed for `zeroRuntime`. Config `{ prefix, key }`.
- v6.0.0: `zeroRuntime` — no runtime style gen; you must import a precompiled CSS (build with `@ant-design/static-style-extract`).
- Nest `ConfigProvider` to scope a subtree; unset tokens inherit parent.
- SSR: wrap in `@ant-design/cssinjs` `StyleProvider cache={createCache()}`, then `extractStyle(cache, true)` into `useServerInsertedHTML`. Next.js App Router: use `@ant-design/nextjs-registry` `<AntdRegistry>`.

## DON'T — v5/v6 theming
- Don't feed `theme` between `undefined` and an object — toggling adds/removes a Provider layer and **remounts** components. Use `{}` not `undefined`.
- Don't rely on `ConfigProvider` for `message.*` / `notification.*` / `Modal.*` static calls — they read no context. Use `App.useApp()` / `Modal.useModal()` + `contextHolder`.
- Don't hand-edit Map/Alias tokens to shift a palette — set the Seed and let the algorithm derive.
- Don't hardcode antd internal class names in overrides (they carry hashes; DOM changed again in v6).

## Override / specificity (Tailwind/plain-CSS interop)
- v5+ wraps rules in `:where(...)` (since 5.0.0) to **lower** specificity so your CSS wins easily.
- Need higher priority (old browsers) → `StyleProvider hashPriority="high"` removes `:where` (turns it into a class selector).
- Prefer `@layer` (antd support since **5.17.0**): `StyleProvider layer` puts antd styles in `@layer antd` — always beatable by unlayered app CSS. With `zeroRuntime`, import the precompiled CSS into the same layer: `@import url(antd.css) layer(antd);`.
- Legacy-browser transformers via StyleProvider: `legacyLogicalPropertiesTransformer`, `px2remTransformer`.

## DO — migrate v4 → v5 (the big one)
- Run codemod first (commit first): `npx -p @ant-design/codemod-v5 antd5-codemod src`. Not exhaustive — review by hand.
- Remove less: all `.less` files & less variables are gone; delete `~antd/es/style/...` imports. `antd/dist/antd.css` removed — import `antd/dist/reset.css` for base resets (or wrap app in `<App>` to avoid global pollution).
- Drop `babel-plugin-import` — CSS-in-JS is on-demand natively.
- moment → dayjs (built-in). Migrate locale imports; watch dayjs plugin gaps. Keep moment only via `@ant-design/moment-webpack-plugin`.
- Popup API unified: `dropdownClassName`→`popupClassName`; controlled `visible`→`open`.
- Moved out: `Comment`→`@ant-design/compatible`, `PageHeader`→`@ant-design/pro-components`.
- Keep v4 look / less vars: `@ant-design/compatible@v5-compatible-v4` (`convertLegacyToken` → less-loader `modifyVars`).

## DON'T — v4 → v5
- Don't ship to IE — support dropped in v5. Don't expect global `.ant-*` less overrides to work; re-express as tokens.

## DO — migrate v5 → v6 (mostly technical)
- Upgrade to latest v5, clear all console deprecation warnings first, then `antd@6`.
- React **18+** required (16/17 dropped). Upgrade `@ant-design/icons` to **v6 in lockstep** (icons@6 ≠ antd@5). Remove `@ant-design/v5-patch-for-react-19` (unneeded).
- CSS vars are default; IE unsupported. Use the Ant Design CLI upgrade helper to scan deprecated APIs.
- Migrate deprecated props: per-part styling `xxxStyle`/`headStyle`/`bodyStyle` → `styles.*` & `classNames.*`; `bordered`→`variant`; `dropdownRender`→`popupRender`; `dropdownMatchSelectWidth`→`popupMatchSelectWidth`; `Button.Group`/`Dropdown.Button`→`Space.Compact`; `size="default"`→`"medium"`. Deprecated in v6, removed in v7.

## DON'T — v5 → v6
- Don't target internal component DOM in CSS — v6 restructured many components. Re-check custom selectors.

Sources: ant.design/docs/react/introduce · /customize-theme · /compatible-style · /migration-v6 (v5→v6) · GitHub ant-design 5.x-stable docs/react/migration-v5 (v4→v5) · github.com/ant-design/cssinjs

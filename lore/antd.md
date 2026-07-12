# antd (Ant Design, React-only)

Version cue: v6 current (React ≥18; dropped 16/17), v5 prior — both theme via CSS-in-JS design tokens. v4 legacy used less vars/`modifyVars`. v5→v6: clear v5 deprecation warnings first (removed in v7).

DO theme via `ConfigProvider theme={{ token, components, algorithm }}` — `token` is global, `components.X` isolates per-component. Derive dark/compact from `theme.darkAlgorithm`/`compactAlgorithm` (array to combine); never fork the stylesheet.
DO read tokens with the `useToken` hook (or `getDesignToken` outside React), not hardcoded hex.
DO wrap the tree in `<App>` and use `App.useApp()` / `message.useMessage()`+`{contextHolder}` — static `message.x`/`Modal.x`/`notification.x` ignore ConfigProvider theme.
DO import per-component (`import { Button } from 'antd'`) — tree-shaken; TS types are built in.
DO SSR-extract styles via `@ant-design/cssinjs` `StyleProvider`; `theme.zeroRuntime` (v6) needs manual CSS import.

DON'T pass `theme={undefined}` — use `{}` to avoid remount. DON'T mix `@ant-design/icons` <6 with antd 6, or keep `@ant-design/v5-patch-for-react-19`.
DON'T use removed v6 APIs: `bordered`→`variant`, `bodyStyle`→`styles.body`, `dropdownXxx`→`popupXxx`, `Button.Group`/`Input.Group`→`Space.Compact`, `BackTop`→`FloatButton.BackTop`; size enums→`large|medium|small`; composition→`items`.

Commands: `npm i antd @ant-design/icons`.

Deep dive when writing non-trivial antd — read lore/antd/{theming-and-migration}.md

## Sources
ant.design/docs/react/introduce, /customize-theme, /migration-v6, /getting-started

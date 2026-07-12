# chakra — v2 vs v3 (major rewrite)

React-only component + styling library. **v3 (current: 3.36.x) is a ground-up rewrite.** Theming engine
rebuilt around a Panda-CSS-style token system; interactive components rebuilt on **Ark UI** (Zag.js state
machines, same author). Runtime is still Emotion. Almost every v2 theming/provider API is gone. Detect the
major before touching config — `extendTheme` = v2, `createSystem` = v3.

Assume JS/TS + React lore live separately. This file is STYLING/theming specifics only.

## DO — v3 setup (the rewrite)
- Install the real deps. Emotion `react` is still required; `styled` and framer-motion are NOT.
  ```bash
  npm i @chakra-ui/react @emotion/react   # Node 20+; next-themes pulled via snippets
  ```
- Build a **system**, not a theme. `createSystem(defaultConfig, config)`; wrap every token value in `{ value }`.
  ```ts
  import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"
  const config = defineConfig({
    theme: {
      tokens:         { colors: { brand: { 500: { value: "#3b82f6" } } } },
      semanticTokens: { colors: { brand: { solid: { value: "{colors.brand.500}" } } } },
    },
  })
  export const system = createSystem(defaultConfig, config)
  ```
- Provide via `value`, not `theme`.
  ```tsx
  import { ChakraProvider, defaultSystem } from "@chakra-ui/react"
  <ChakraProvider value={system /* or defaultSystem */}>{children}</ChakraProvider>
  ```
- Generate boilerplate compositions (Provider, color-mode, toaster, tooltip) with the CLI:
  ```bash
  npx @chakra-ui/cli snippet add
  ```
  The generated `Provider` composes `ChakraProvider` + `ThemeProvider` from **next-themes**.
- Color mode = **next-themes**. Read/toggle with `useTheme()` from `next-themes`; force a mode with
  `className="light" | "dark"`. The snippet ships a `useColorMode`/`ColorModeButton` wrapper if you want it.
- Style component variants with **recipes** (`cva` / config `recipes`) and multi-part components with
  **slot recipes** (`sva` / config `slotRecipes`). This replaces `styleConfig`/`multiStyleConfig`.
- Use compound (dot-notation) components: `Dialog.Root/Trigger/Content`, `Field.Root`, `Menu.Root`, etc.
- Reset control: `preflight: false` (or `{ scope: ".chakra-reset" }`) in the config — not a provider prop.
- Migrate mechanically first: `npx @chakra-ui/codemod upgrade` (`--dry` to preview). It renames components,
  props, imports, and restructures into compound components.

## DON'T — dead v2 APIs
- DON'T call `extendTheme` / pass `<ChakraProvider theme={...}>`. Both removed. Use `createSystem` + `value`.
- DON'T import `ThemeProvider`, `ColorModeProvider`, `ColorModeScript`, `useColorMode`, `useColorModeValue`,
  `LightMode`, `DarkMode` from Chakra — gone. Color mode is next-themes now.
- DON'T ship `@emotion/styled`, `framer-motion`, `@chakra-ui/icons`, or `@chakra-ui/next-js` — all dropped.
  Icons → `lucide-react`/`react-icons`; Next integration → `asChild` (`<Box asChild><NextImage/></Box>`).
- DON'T write bare token values in config. `fonts: { heading: "Inter" }` is v2; v3 needs `{ value: "Inter" }`.
- DON'T use `resetCss` on the provider — use `preflight`.
- DON'T reach for removed components: `Modal`→`Dialog`, `FormControl`→`Field`, `Divider`→`Separator`,
  `Collapse`→`Collapsible`, `AlertDialog`→`Dialog role="alertdialog"`, `StackDivider`→explicit `Separator`,
  `Show`/`Hide`→`hideFrom`/`hideBelow` props, `Fade`/`ScaleFade`/`Slide`→`Presence` (CSS animations).

## DO — v3 prop renames (silent no-ops if missed)
- Booleans drop `is`: `isOpen`→`open`, `isDisabled`→`disabled`, `isInvalid`→`invalid`, `isRequired`→`required`,
  `defaultIsOpen`→`defaultOpen`, `isLoading`→`loading` (Button).
- `colorScheme`→`colorPalette`; `spacing`→`gap`; `noOfLines`→`lineClamp`; `truncated`→`truncate`;
  `hasArrow`→`showArrow` (Tooltip).
- Nested styles: use `css` with `&`, not `sx`/`__css`.
- Gradients split: `bgGradient="to-r" gradientFrom="…" gradientTo="…"`.

## DON'T — v2 patterns to stop
- DON'T rely on `colorScheme` — it silently does nothing in v3.
- DON'T custom-`forwardRef` from Chakra — use React's `forwardRef` directly.
- DON'T assume the hooks package — only `useBreakpointValue`, `useDisclosure`, `useControllableState`,
  `useMediaQuery`, `useCallbackRef` remain.

## Notes
- **v2 recap** (legacy apps): `extendTheme` object theme, `<ChakraProvider theme={theme}>`, Emotion +
  framer-motion required, `useColorModeValue`/`ColorModeScript`, `styleConfig`/`multiStyleConfig`, `colorScheme`.
- **Runtime cost:** v3 is still Emotion runtime CSS-in-JS. The token engine mirrors Panda CSS, and a
  zero-runtime future is on the roadmap, but as of 3.36 there is no zero-runtime mode. For strict zero-runtime,
  reach for Panda CSS / vanilla-extract instead.
- **React-only.** No official Vue/Svelte/Angular port. (Ark UI underneath is multi-framework, but Chakra is not.)

## Sources
- https://chakra-ui.com/docs/get-started/migration
- https://chakra-ui.com/docs/get-started/installation
- https://chakra-ui.com/docs/theming/overview
- https://chakra-ui.com/docs/components/concepts/composition

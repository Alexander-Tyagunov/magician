# Chakra UI — core digest

Version: current **v3** (ground-up rewrite, Oct 2024) vs prior **v2** (2022). React-only. Migration = large; see deep dive.

DO wrap app in the CLI-generated `<Provider>` (composes `ChakraProvider` + next-themes). DON'T use bare `ChakraProvider theme=` — v3 renamed the prop to `value` and takes a system, not a theme.
DO build the system with `createSystem(defaultConfig, {...})`. DON'T call `extendTheme` — removed in v3.
DO wrap every token value: `{ colors: { brand: { value: "#f00" } } }`. DON'T pass raw values — v3 requires the `value` key.
DO use compound parts: `Dialog.Root`, `Card.Root`, `Tabs.Root`, `Accordion.Root` (v3). DON'T use `Modal`/flat `Card` — replaced.
DO use boolean props without `is`: `open`, `disabled`, `invalid`, `checked`. DON'T use v2 `isOpen`/`isDisabled`/`isInvalid`.
DO use `colorPalette`, `gap`, `lineClamp`, `truncate`. DON'T use v2 `colorScheme`/`spacing`/`noOfLines`/`truncated`.
DO style via the `css` prop and prefix nested selectors with `&`. DON'T use `sx`/`__css` — dropped.
DO prefer `asChild` over `as` for polymorphism. DON'T import `@chakra-ui/icons`, `framer-motion`, `useColorMode`/`useColorModeValue` — removed; use `react-icons`/`lucide-react` + next-themes.
DO `preflight: false` to skip reset. DON'T use `resetCss`.

Commands: `npm i @chakra-ui/react @emotion/react` · `npx @chakra-ui/cli snippet add` (Node 20+, tsconfig `@/*` alias).

Deep dive when writing non-trivial chakra — read lore/chakra/{v2-vs-v3}.md

## Sources
chakra-ui.com/docs/get-started {migration, installation} (v3.x, 2026)

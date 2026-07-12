# Radix — core (always-injected)

React-only (Primitives + shadcn/ui). Unstyled/headless: WAI-ARIA, focus/keyboard, uncontrolled by default — you supply all CSS. Primitives ≠ Radix Themes (styled) ≠ Radix Colors.

VERSION: single `radix-ui` pkg (Jan 2025) exposes all primitives — `import { Dialog } from "radix-ui"`. Prior/still-valid: per-component `@radix-ui/react-*` (1.x). shadcn/ui: Tailwind v4 + React 19 since Feb 2025; July 2026 default backend switched Radix→Base UI.

Commands: `npm i radix-ui`. shadcn: `npx shadcn@latest init`, then `npx shadcn@latest add <component>` — copies source into your repo (you own/edit it; NOT a dependency).

DO
- Compose Parts: `Dialog.Root/Trigger/Portal/Overlay/Content`; keep `Portal` for overlays.
- Merge onto your own element with `asChild` (single child; spreads props+ref) — not wrapper divs.
- Style off `[data-state=open]`/`[data-side]` attrs, not JS state.
- shadcn v4: `data-slot` hooks, `@theme inline` + OKLCH vars, `tw-animate-css`, `sonner` over Toast.

DON'T
- No forwardRef in shadcn v4 comps (removed); leave `components.json` `tailwind.config` blank for TW v4.
- Don't change `style`/`baseColor`/`cssVariables` after init; `new-york` is default style (`default` deprecated).
- Don't ship Primitives unstyled or confuse them with Radix Themes.

Deep dive when writing non-trivial radix — read lore/radix/{shadcn-and-composition}.md

Sources: radix-ui.com/primitives/docs/overview/{introduction,releases}; ui.shadcn.com/docs/{installation,components-json,tailwind-v4,changelog}

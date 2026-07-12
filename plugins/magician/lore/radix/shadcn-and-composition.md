# radix — shadcn/ui & composition

React-only. Radix **Primitives** = unstyled, accessible, composable behavior. **shadcn/ui** = copy-in components (NOT an npm dep), built on Radix + Tailwind + CVA + `tailwind-merge`. Radix **Themes** (prebuilt, styled) is a separate product — don't conflate. Assume JS/TS + React lore live elsewhere; this is STYLING/composition. Verify version facts before asserting.

## What's what
- **Radix Primitives** — headless. Ships no CSS; you style with anything (Tailwind, CSS Modules, vanilla-extract). WAI-ARIA patterns, focus management, keyboard nav handled for you.
- **shadcn/ui** — a distribution model, not a library. CLI copies component *source* into your repo (`components/ui/*`); you own and edit it. No version to bump.
- **Radix Themes** — opinionated styled kit (`@radix-ui/themes`, `<Theme>` wrapper). Batteries-included; NOT for when you want to own styling.

## Radix packages & versions
DO
- Prefer the current unified package: `npm i radix-ui`, then `import { Dialog, Tooltip } from "radix-ui"` (tree-shakeable).
- Using scoped packages (`@radix-ui/react-dialog`, `@radix-ui/react-slot`, …)? Upgrade them **together** — mismatched versions duplicate shared internals.

DON'T
- Mix unified `radix-ui` and scoped `@radix-ui/react-*` for the same primitive.

## asChild — the core composition primitive
DO
- Every Radix part that renders a DOM node accepts `asChild` — it merges the part's props/behavior onto **your** single child instead of rendering Radix's default element.
```jsx
<Tooltip.Trigger asChild>
  <a href="/">Radix</a>          {/* trigger behavior on an <a>, not a <button> */}
</Tooltip.Trigger>
```
- Child components you pass MUST spread props and forward ref, or Radix's wiring is dropped:
```jsx
const MyButton = React.forwardRef((props, ref) => <button {...props} ref={ref} />);
```
- Nest `asChild` to stack behaviors (one DOM node, two triggers):
```jsx
<Tooltip.Trigger asChild>
  <Dialog.Trigger asChild>
    <MyButton>Open</MyButton>
  </Dialog.Trigger>
</Tooltip.Trigger>
```

DON'T
- Swap a trigger to a non-interactive element (`div`) — keep it a real `button`/`a` or lose semantics.
- Pass **multiple** children to an `asChild` part — it clones exactly one. Multi-child: use `Slottable` (below).
- Assume props auto-merge if your child eats them. No spread = no behavior.

## Building your own asChild (Slot)
DO
- Use `Slot` from `radix-ui` (or `@radix-ui/react-slot`) to give your components an `asChild` API:
```jsx
import { Slot } from "radix-ui";      // Slot.Root, Slot.Slottable
function Button({ asChild, ...props }) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp {...props} />;
}
```
- With extra children (icons), wrap the swappable child in `Slot.Slottable` so merged props land on the right node: `<Comp>{left}<Slot.Slottable>{children}</Slot.Slottable>{right}</Comp>`.

DON'T
- Forget event-handler merge order: `Slot` runs the **child's** `onClick` first, then the slot's; a child `e.preventDefault()` shows up via `e.defaultPrevented`.

## Controlled / uncontrolled
DO
- Default to **uncontrolled** — Radix owns internal state; use `defaultOpen`/`defaultValue` for initial state. Less code, fewer bugs.
- Go **controlled** only when you need to drive state (close after async submit): pair `open` + `onOpenChange` (`value` + `onValueChange`, etc.).

DON'T
- Pass `open` without `onOpenChange` (freezes it), or mix `defaultOpen` and `open` on one instance.

## Portals & focus
DO
- Wrap overlay/content in `<Dialog.Portal>` (default `document.body`) to escape `overflow`/`z-index`/stacking traps. Redirect via `container={el}` for scoped roots (Shadow DOM).
- Trust built-in focus management: modal traps focus; `Esc` closes and returns focus to trigger. Tune via `onOpenAutoFocus`/`onCloseAutoFocus` (`e.preventDefault()` to override).
- Use `modal` (default `true`) intentionally: `false` = non-modal (content behind stays interactive, no trap).

DON'T
- Rebuild focus trapping / scroll lock by hand — Radix does it; manual `ref.focus()` fights the primitive.

## shadcn/ui — current stack (Tailwind v4 + React 19)
DO
- Scaffold: `npx shadcn@latest init`; add: `npx shadcn@latest add button dialog`. Config in `components.json`.
- `components.json` keys: `style` (now **`new-york`**; `default` deprecated, immutable post-init), `rsc` (adds `"use client"`), `tsx`, `tailwind.{config,css,baseColor,cssVariables,prefix}`, `aliases.{components,utils,ui,lib,hooks}`, `iconLibrary`. For **Tailwind v4 leave `tailwind.config` blank**.
- Style variants with **CVA** + merge with `cn`:
```ts
// lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
```
```tsx
const buttonVariants = cva("inline-flex …", {
  variants: { variant: { default:"…", outline:"…" }, size: { default:"…", sm:"…", icon:"…" } },
  defaultVariants: { variant: "default", size: "default" },
});
function Button({ className, variant, size, asChild, ...props }) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
```
- **Own the code** — edit copied components freely. Style/extend via the `data-slot` attr every primitive now emits. Prefer `size-4` (v3.4+) over `w-4 h-4`.

DON'T
- Treat shadcn as a versioned dependency — no runtime pkg to import or upgrade. Re-running `add` overwrites; diff first.
- Use the removed `toast` — use **`sonner`**. Keep deps fresh: `@radix-ui/*`, `cmdk`, `lucide-react`, `recharts`, `tailwind-merge`, `clsx`.

## Tailwind v4 vs v3 in shadcn (migration)
DO (v4)
- Import via `@import "tailwindcss";`; theme tokens live in CSS under `@theme` / `@theme inline`. Move `:root`/`.dark` **out of** `@layer base`, wrap values in `hsl()` at declaration, use `@theme inline` referencing them.
- Colors are **OKLCH** in v4 projects; charts drop the wrapper: `var(--chart-1)` not `hsl(var(--chart-1))`.
- Animations: `@import "tw-animate-css";` (the `tailwindcss-animate` plugin was deprecated 2025-03-19).

DON'T (v3 → v4)
- Leave `forwardRef` in migrated components — v4 shadcn dropped it: use `React.ComponentProps<…>`, delete `ref={ref}`, add `data-slot`. Codemod: `remove-forward-ref`.
- Keep `tailwind.config.js` wired in `components.json` for v4 (blank it). v3 projects keep `@tailwind base/components/utilities;` + JS config and still work — the CLI won't force-upgrade existing v3/React-18 apps.

## Cross-framework note
Radix Primitives and shadcn/ui are **React only**. Community Vue/Svelte/Solid ports exist but are separate projects — don't assume API parity. For framework-agnostic styling, see the Tailwind / vanilla-extract lore.

## Sources
- https://www.radix-ui.com/primitives/docs/overview/introduction
- https://www.radix-ui.com/primitives/docs/guides/composition
- https://www.radix-ui.com/primitives/docs/utilities/slot
- https://www.radix-ui.com/primitives/docs/components/dialog
- https://ui.shadcn.com/docs
- https://ui.shadcn.com/docs/tailwind-v4
- https://ui.shadcn.com/docs/components-json
- https://ui.shadcn.com/docs/installation/manual
- https://ui.shadcn.com/docs/components/button

# svelte — Components, props & stores

Svelte 5 (runes) is current. Version-adaptive: notes mark runes-mode (5) vs legacy-mode (4) syntax. Both compile in 5 — but don't mix modes in one component; using any rune makes the whole file runes-mode. Assumes JS/TS lore is separate.

## Component structure

`.svelte` file = `<script module>?` + `<script>` + markup + `<style>`. `<script module>` (5) runs once per module (replaces `<script context="module">` from 4) — for shared constants/exports, no per-instance state.

DO
- Put per-instance logic in plain `<script>`. Top-level bindings are visible in markup.
- Use `.svelte.js` / `.svelte.ts` modules to share rune-based reactive logic across components (5).

DON'T
- Don't put `$state`/`$derived` in `<script module>` — module scope is shared across all instances (and across SSR requests → data leak).

## Props — `$props` (5) vs `export let` (4)

DO (5) — one rune destructures all inputs:
```svelte
<script lang="ts">
  interface Props { adjective?: string; count: number; children?: import('svelte').Snippet }
  let { adjective = 'happy', count, ...rest }: Props = $props();
</script>
```
- Defaults in destructuring — apply when prop is missing or `undefined`. Fallbacks are NOT reactive proxies.
- Rename reserved words: `let { class: klass } = $props()`.
- Rest props: `{...rest}` — spread onto an element `<div {...rest}>`.
- `$props.id()` (5.20+) — SSR-stable unique id for `for`/`aria-*`.

DON'T
- Don't mutate a prop you don't own — mutating a plain object is a no-op; mutating a `$state` proxy prop fires `ownership_invalid_mutation`. Communicate up via callback props or `$bindable`.
- Don't reach for `export let` in new code — that's legacy (4). `export const`/`export function` there expose non-overridable members.

## Two-way binding — `$bindable` (5)

Props are one-way by default. Opt a prop into `bind:` with `$bindable`:
```svelte
<!-- child --> let { value = $bindable('') } = $props();  <input bind:value />
<!-- parent --> <FancyInput bind:value={message} />
```
DON'T overuse — it makes data flow unpredictable. Parent may still pass a plain prop (fallback applies).

## Events — callback props (5) vs `createEventDispatcher` (4)

DO (5) — events are just props/attributes:
```svelte
<!-- child --> let { onincrement } = $props();  <button onclick={onincrement}>+</button>
<!-- parent --> <Stepper onincrement={() => n++} />
```
- DOM handlers are plain attributes: `onclick`, `oninput` (lowercase, no colon). `onclick={handler}`.
- Spreading `{...rest}` including an `onclick` merges/forwards handlers automatically.

DON'T
- `createEventDispatcher` is **deprecated** (5) — don't use in new code. No `dispatch('x', detail)`, no parent `on:x`.
- Event modifiers (`on:click|preventDefault`) are gone in runes mode — call `e.preventDefault()` in the handler, or use a wrapper. `capture`/`once`/`passive` available as attribute suffixes: `onclickcapture`.
- (4 legacy: `const d = createEventDispatcher()` + `on:name` on parent; component events don't bubble.)

## Snippets (5) vs slots (4)

Slots are **deprecated** in 5 — use snippets. Snippets are reusable markup chunks, passable as props.

DO (5)
```svelte
{#snippet row(item)}<td>{item.name}</td>{/snippet}
{@render row(fruit)}
```
- Default content = the `children` snippet: nested content between tags → `children` prop; render with `{@render children?.()}`.
- Named/param snippets replace named + scoped slots. Declared inside a component tag → implicit props: `<Table>{#snippet row(x)}…{/snippet}</Table>`.
- Type: `import type { Snippet } from 'svelte'`; params are a tuple: `row: Snippet<[Item]>`. Generic via `generics="T"`.
- Optional: `{@render header?.()}`; fallback via `{#if header}…{:else}…{/if}`.

DON'T
- Don't name a prop `children` while also nesting default content — collision.
- (4 legacy: `<slot name="header" {item}/>` + parent `<div slot="header" let:item>`.)

## Context API

`setContext`/`getContext` from `'svelte'`. Ancestor→descendant value sharing without prop-drilling. Prefer over module globals (globals leak between SSR requests; context does not).

DO
- Call `setContext(key, value)` / `getContext(key)` **synchronously during component init** — not in handlers or after `await`.
- Share reactive state: put a `$state` object in context, mutate its fields in children (`ctx.count++`). Works because the proxy identity is stable.
- `createContext<T>()` (5.40+) returns typed `[getX, setX]` — no string keys, better type safety. Prefer it.
- `hasContext(key)`, `getAllContexts()` available.

DON'T
- Don't **reassign** a context state object (`ctx = {…}`) — breaks the reactive link. Mutate instead.
- Don't call `getContext` outside init (e.g. in `onclick`) — returns nothing.

## Stores — `svelte/store`

Still valid in 5, NOT deprecated — but runes are preferred for component/shared state. Use stores for complex async streams, RxJS interop, or fine manual subscription control.

DO
- `writable(init, start?)` — `.set(v)`, `.update(fn)`; `readable(init, start)` — no external set; `derived(deps, fn)` — recompute from one store or `[a,b]`.
- Auto-subscribe with `$store` in a component — subscribes at init, unsubscribes on destroy, `$store = v` calls `.set`. Store must be top-level (not in `if`/function).
- `start(set,update)` runs on 0→1 subscribers, returns a stop fn for 1→0 (timers, sockets).
- `get(store)` for a one-off read (subscribes+reads+unsubscribes) — avoid in hot paths. `readonly(store)` to hand out read-only access.
- Custom store = anything with the contract: `.subscribe(fn)` (calls fn sync immediately + on change, returns unsubscribe) + optional `.set`.

DON'T
- Don't use stores just to extract/share logic in 5 — export a `$state` object from a `.svelte.js` module and mutate it directly:
  ```js
  // counter.svelte.js
  export const counter = $state({ n: 0 });
  ```
- Don't `$store`-autosubscribe outside a `.svelte` component — that's `$`-prefix component sugar only. In `.js`, subscribe manually or use `get`.

## Derived & effects (runes, quick contrast)

- `$derived(expr)` / `$derived.by(() => …)` — cached computed; pure, no side effects. Replaces `$:` reactive statements (4) for values.
- `$effect(() => { … return cleanup })` — DOM/side effects after mount; auto-tracks deps read synchronously. Replaces `onMount`-for-reactivity and `$:` side-effect statements. `$effect.pre` for before-DOM (was `beforeUpdate`).
- `onMount`/`onDestroy` still valid (5) for one-time mount/teardown. `beforeUpdate`/`afterUpdate` deprecated → use `$effect.pre`/`$effect`.

## Sources

- https://svelte.dev/docs/svelte/what-are-runes
- https://svelte.dev/docs/svelte/$props
- https://svelte.dev/docs/svelte/$bindable
- https://svelte.dev/docs/svelte/snippet
- https://svelte.dev/docs/svelte/legacy-on (component events, createEventDispatcher)
- https://svelte.dev/docs/svelte/context
- https://svelte.dev/docs/svelte/stores
- https://svelte.dev/docs/svelte/svelte (module exports, lifecycle, deprecations)

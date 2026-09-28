# svelte — deep dive

> On-demand companion to `lore/svelte.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Runes & reactivity (Svelte 5)](#runes-and-reactivity) · [Components, props & stores](#components-and-stores)

## Runes & reactivity (Svelte 5) <a id="runes-and-reactivity"></a>

Runes are `$`-prefixed compiler keywords (Svelte 5+, `.svelte`/`.svelte.js`/`.svelte.ts`). Not imported, not values — can't be assigned to a variable or passed as args. If the codebase uses `export let` / `$:` / `let x = 0` for reactive state, it's Svelte 4 (legacy) — match the surrounding style; don't mix modes in one file.

### Detect the version first

DO check `svelte` in `package.json`. `^5` → runes. `^4`/`^3` → legacy.
DON'T write runes in a Svelte 4 file or `$:` in a runes file. Runes mode is auto-enabled once any rune appears in a component.

### $state — reactive state

DO: `let count = $state(0)`. Read/write like a plain variable: `count++`.
DO rely on deep reactivity for arrays/plain objects — they become recursive proxies; `todos[0].done = true` and `arr.push(x)` trigger granular updates.
DO use `$state` in class fields: `class Todo { done = $state(false); text = $state(''); }`.
DO use `$state.raw(...)` for large/immutable data you only ever reassign (perf) — mutating properties does nothing; replace the whole value: `person = {...person, age: 50}`.
DO use `$state.snapshot(value)` before passing proxied state to external libs / `structuredClone` / `postMessage`.
DO use reactive builtins from `svelte/reactivity` (`SvelteMap`, `SvelteSet`, `SvelteDate`, `SvelteURL`) — raw `Map`/`Set` aren't reactive.

DON'T destructure reactive state and expect reactivity — `let { a } = obj` captures the value at that point (plain JS).
DON'T pass a class method as a handler bare: `onclick={todo.reset}` loses `this`. Use `onclick={() => todo.reset()}` or an arrow class field `reset = () => {...}`.
DON'T export a reassigned `$state` from a `.svelte.js` module — export an object and mutate its properties, or expose getter functions.

### $derived — computed state

DO: `let doubled = $derived(count * 2)`. Recomputed lazily (push-pull) when a synchronously-read dependency changes.
DO use `$derived.by(() => {...})` for multi-statement logic. `$derived(x)` ≡ `$derived.by(() => x)`.
DO reassign a derived for optimistic UI (Svelte 5.25+, non-`const`): the override holds until a dependency changes and recomputes it.

DON'T put side effects or state mutations inside `$derived` — the compiler forbids it.
DON'T reach for `$effect` to compute a value — that's what `$derived` is for.

### $effect — side effects (escape hatch, use sparingly)

Runs after mount, browser-only (never during SSR), batched in a microtask after DOM updates. Auto-tracks `$state`/`$derived`/`$props` read **synchronously** in its body.

DO use for genuinely external work: third-party libs, canvas drawing, manual DOM, analytics, subscriptions.
DO return a teardown function — runs before each re-run and on destroy: `$effect(() => { const id = setInterval(f); return () => clearInterval(id); })`.
DO use `$effect.pre(() => {...})` to run *before* DOM updates (e.g. capture scroll position).

DON'T use `$effect` to sync/derive state (`$effect(() => doubled = count * 2)`) — use `$derived`. This is the #1 misuse (like React `useEffect` overuse).
DON'T write to state you also read in the same effect → infinite loop; if unavoidable, wrap the read in `untrack(() => ...)` (from `svelte`).
DON'T rely on values read after `await` or inside `setTimeout` — async reads are NOT tracked as dependencies.
DON'T expect property-level tracking on a bare object — an effect reruns when the object reference it read changes, per the values read on the last run (conditional branches change deps).
`$effect.root(fn)` and `$effect.tracking()` are advanced (manual scopes / library authoring) — skip unless required.

### $props — component inputs

DO: `let { adjective = 'happy', ...rest } = $props();`. Fallbacks apply when the prop is missing/`undefined`.
DO rename reserved words: `let { super: trouper } = $props()`.
DO type them (TS): `let { adjective }: { adjective: string } = $props()`, or an `interface Props {...}`. Type `children` and snippets with `Snippet` from `'svelte'`.
DO use `$props.id()` (5.20.0+) for SSR-stable unique ids linking `<label for>`/`<input id>`.

DON'T mutate props — fallbacks aren't reactive proxies; use callbacks or `$bindable`.

### $bindable — opt-in two-way prop

DO mark a prop bindable in the child: `let { value = $bindable() } = $props()` (fallback: `$bindable('x')`). Parent binds: `<Child bind:value={message} />`.
DON'T overuse — it makes data flow hard to trace. Prefer one-way props + callback events. Binding is optional; a normal prop still works.

### Svelte 4 → 5 migration map

| Svelte 4 (legacy) | Svelte 5 (runes) |
|---|---|
| `let count = 0` | `let count = $state(0)` |
| `$: sum = a + b` | `let sum = $derived(a + b)` |
| `$: { total = 0; for (…) total += … }` | `let total = $derived.by(() => {…})` |
| `$: console.log(x)` (side effect) | `$effect(() => console.log(x))` |
| `export let name` | `let { name } = $props()` |
| `export let value` + `bind:value` | `let { value = $bindable() } = $props()` |

Legacy `$:` gotchas (why runes exist): compile-time deps miss values read only inside called functions; indirect ordering can leave stale values; `$:` runs during SSR (guard browser-only code).

### Stores (svelte/store) — de-emphasized, NOT deprecated

DO prefer runes for cross-component shared state in Svelte 5: export a `$state` object from `.svelte.js`/`.svelte.ts` and mutate it (universal reactivity), instead of `writable`.
DO keep/adopt stores for complex async streams, manual update control, or RxJS interop — they still work.
DO use `$store` auto-subscription in components (top-level only; auto-unsubscribes). `writable(v)`→`.set`/`.update`; `readable`; `derived`; `get(store)` (avoid in hot paths — it sub/reads/unsubs each call).
DON'T `$`-prefix non-store locals; DON'T declare a store subscription inside an `if`/function.

### Sources

- https://svelte.dev/docs/svelte/what-are-runes
- https://svelte.dev/docs/svelte/$state
- https://svelte.dev/docs/svelte/$derived
- https://svelte.dev/docs/svelte/$effect
- https://svelte.dev/docs/svelte/$props
- https://svelte.dev/docs/svelte/$bindable
- https://svelte.dev/docs/svelte/legacy-reactive-assignments
- https://svelte.dev/docs/svelte/stores

## Components, props & stores <a id="components-and-stores"></a>

Svelte 5 (runes) is current. Version-adaptive: notes mark runes-mode (5) vs legacy-mode (4) syntax. Both compile in 5 — but don't mix modes in one component; using any rune makes the whole file runes-mode. Assumes JS/TS lore is separate.

### Component structure

`.svelte` file = `<script module>?` + `<script>` + markup + `<style>`. `<script module>` (5) runs once per module (replaces `<script context="module">` from 4) — for shared constants/exports, no per-instance state.

DO
- Put per-instance logic in plain `<script>`. Top-level bindings are visible in markup.
- Use `.svelte.js` / `.svelte.ts` modules to share rune-based reactive logic across components (5).

DON'T
- Don't put `$state`/`$derived` in `<script module>` — module scope is shared across all instances (and across SSR requests → data leak).

### Props — `$props` (5) vs `export let` (4)

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

### Two-way binding — `$bindable` (5)

Props are one-way by default. Opt a prop into `bind:` with `$bindable`:
```svelte
<!-- child --> let { value = $bindable('') } = $props();  <input bind:value />
<!-- parent --> <FancyInput bind:value={message} />
```
DON'T overuse — it makes data flow unpredictable. Parent may still pass a plain prop (fallback applies).

### Events — callback props (5) vs `createEventDispatcher` (4)

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

### Snippets (5) vs slots (4)

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

### Context API

`setContext`/`getContext` from `'svelte'`. Ancestor→descendant value sharing without prop-drilling. Prefer over module globals (globals leak between SSR requests; context does not).

DO
- Call `setContext(key, value)` / `getContext(key)` **synchronously during component init** — not in handlers or after `await`.
- Share reactive state: put a `$state` object in context, mutate its fields in children (`ctx.count++`). Works because the proxy identity is stable.
- `createContext<T>()` (5.40+) returns typed `[getX, setX]` — no string keys, better type safety. Prefer it.
- `hasContext(key)`, `getAllContexts()` available.

DON'T
- Don't **reassign** a context state object (`ctx = {…}`) — breaks the reactive link. Mutate instead.
- Don't call `getContext` outside init (e.g. in `onclick`) — returns nothing.

### Stores — `svelte/store`

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

### Derived & effects (runes, quick contrast)

- `$derived(expr)` / `$derived.by(() => …)` — cached computed; pure, no side effects. Replaces `$:` reactive statements (4) for values.
- `$effect(() => { … return cleanup })` — DOM/side effects after mount; auto-tracks deps read synchronously. Replaces `onMount`-for-reactivity and `$:` side-effect statements. `$effect.pre` for before-DOM (was `beforeUpdate`).
- `onMount`/`onDestroy` still valid (5) for one-time mount/teardown. `beforeUpdate`/`afterUpdate` deprecated → use `$effect.pre`/`$effect`.

### Sources

- https://svelte.dev/docs/svelte/what-are-runes
- https://svelte.dev/docs/svelte/$props
- https://svelte.dev/docs/svelte/$bindable
- https://svelte.dev/docs/svelte/snippet
- https://svelte.dev/docs/svelte/legacy-on (component events, createEventDispatcher)
- https://svelte.dev/docs/svelte/context
- https://svelte.dev/docs/svelte/stores
- https://svelte.dev/docs/svelte/svelte (module exports, lifecycle, deprecations)

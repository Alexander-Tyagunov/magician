# vue — Patterns & pitfalls

Scope: Vue-specific guidance. Assume JS/TS lore lives elsewhere. Current stable: **Vue 3.5** (Vue 2 EOL 2023-12-31). Default to **Composition API + `<script setup>` + SFC** for apps; Options API is fine for build-less/low-complexity. Version-tag every feature below.

## Composables for reuse

DO
- Extract stateful logic into `useX()` composables returning refs/computed. Name `useMouse`, `useFetch`.
- Accept reactive inputs as **getters or refs**, then normalize with `toValue()` inside the composable so callers can pass a ref, getter, or plain value.
```js
export function useFetch(url) { // url: string | Ref | () => string
  const data = ref(null)
  watchEffect(() => { fetch(toValue(url)).then(/*...*/) }) // re-runs when url changes
  return { data }
}
```
- Register lifecycle/watchers **synchronously** at composable top level so they bind to the owner and auto-dispose.
- Return refs (not `reactive()` bundles); let callers destructure without losing reactivity.

DON'T
- Don't call composables conditionally or inside callbacks/`await` — lifecycle hooks and injections won't bind.
- Don't take a plain unwrapped value expecting it to stay reactive; a bare `url` string is a snapshot.

## State: Pinia, not Vuex

DO
- Use **Pinia** for new apps (official, Vue-core-maintained; Composition-style API, strong TS inference, devtools/HMR/SSR).
- Prefer setup stores: `defineStore('id', () => { const n = ref(0); ... return { n } })`.
- Destructure state with `storeToRefs(store)` to keep reactivity; call actions directly off the store.

DON'T
- Don't start new projects on **Vuex** — maintenance mode, no new features.
- Don't destructure state straight off the store (`const { n } = store`) — that drops reactivity. Use `storeToRefs`.
- Don't reach for a store when a composable or props/emit suffices.

## Avoiding reactivity loss

DO
- Keep access on the reactive source: `state.count`, `props.foo`, `store.n`.
- Use `toRefs(reactive_obj)` / `toRef()` to destructure a `reactive()` object without losing tracking.
- Pass reactive values into functions as getters (`() => x`) and read with `toValue()`.

DON'T
- Don't destructure a `reactive()` object directly — `const { count } = reactive({count:0})` yields a disconnected primitive.
- Don't spread/`Object.assign` a reactive object and expect reactivity to survive.
- Don't replace a `reactive` object wholesale via reassignment; mutate its properties or use a `ref`.

## Reactive Props Destructure (3.5)

DO (3.5+)
- Destructure `defineProps` freely — the compiler rewrites refs to `props.foo` in the same `<script setup>`. Native defaults work: `const { size = 'md' } = defineProps<{ size?: string }>()`.
- When passing a destructured prop to `watch`/composable, wrap in a getter: `watch(() => foo, cb)`, `useX(() => foo)`.

DON'T
- Don't assume this in **≤3.4** — there destructured props are static constants; use `props.foo` or `toRefs`.
- Don't do `watch(foo, cb)` — that watches a value, not a source (compiler warns).

## Prop mutation

DO
- Treat props as read-only (one-way down). Seed a local `ref(props.initial)` for editable initial values.
- Derive with `computed(() => props.size.trim())` for transforms.
- Emit an event (or `defineModel()`, stable 3.4) for two-way; let the parent own the write.

DON'T
- Don't assign to a prop (`props.foo = x`) — warns, and gets overwritten on parent re-render.
- Don't mutate nested fields of object/array props; Vue won't stop you but data flow breaks. Emit instead.

## Keys in v-for / v-if

DO
- Give `v-for` a **stable unique** `:key="item.id"`.
- Split `v-if` off `v-for`: filter via a `computed`, or move `v-if` to a wrapping `<template>`.

DON'T
- Don't use array **index** as key when the list reorders/inserts/deletes — causes state bleed and wrong patches.
- Don't put `v-if` and `v-for` on the same element — `v-if` has higher priority (3.x) and can't see the loop var.

## Watch cleanup & lifetime

DO
- Register async-side-effect cleanup. Two options:
  - `onWatcherCleanup(fn)` (**3.5+**) — must be called **synchronously**, before any `await`.
  - `onCleanup` arg — 3rd arg of `watch` cb, 1st arg of `watchEffect`; not subject to the sync constraint.
```js
watch(id, (n) => {
  const c = new AbortController()
  fetch(`/api/${n}`, { signal: c.signal })
  onWatcherCleanup(() => c.abort()) // aborts stale request on re-run/unmount
})
```
- Create watchers **synchronously** in setup so they auto-stop on unmount.
- Use `{ once: true }` (**3.4+**) for fire-once; `{ immediate: true }` to run eagerly.

DON'T
- Don't create watchers inside `setTimeout`/async callbacks without stopping them — they won't bind and leak. Capture the returned stop handle and call it, or keep the watch synchronous with a conditional body.
- Don't call `onWatcherCleanup()` after an `await` — it won't register.
- Don't blanket `{ deep: true }` on large objects; deep watch traverses everything. In **3.5+** cap with `deep: <number>` (max depth).

## Performance

DO
- `shallowRef()` / `shallowReactive()` for large immutable-ish payloads (big lists, API blobs); replace the whole `.value` to trigger, or `triggerRef()` after in-place edits.
- `v-memo="[a, b]"` (**3.2+**) on hot `v-for` rows (length ~>1000). Put it on the **same element** as `v-for`; `:key` is auto-inferred into the memo.
- `v-once` for truly static subtrees rendered once. `v-memo="[]"` ≡ `v-once`.
- Prefer `computed` over methods for cached derived values.

DON'T
- Don't under-specify the `v-memo` array — a missing dependency skips updates that should apply.
- Don't nest `v-memo` inside `v-for` (only works on the loop element itself).
- Don't deep-reactive-wrap large data you never mutate field-by-field — use `shallowRef`.

## Composition helpers (3.5)

DO
- `useTemplateRef('name')` (**3.5+**) for template refs instead of matching a same-named `ref`.
- `useId()` (**3.5+**) for SSR-stable unique ids (a11y `for`/`aria-*`).
- `useModel()` underlies `defineModel()`; prefer the `defineModel()` macro (**3.4 stable**).

DON'T
- Don't hand-roll SSR-safe id generation — hydration mismatches; use `useId()`.

## Sources
- https://vuejs.org/guide/introduction.html
- https://vuejs.org/api/
- https://vuejs.org/guide/essentials/watchers.html
- https://vuejs.org/guide/scaling-up/state-management.html
- https://vuejs.org/guide/components/props.html
- https://vuejs.org/api/built-in-directives.html
- https://pinia.vuejs.org

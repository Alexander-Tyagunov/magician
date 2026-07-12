# vue — Components & SFC

Vue 3 (Composition API + `<script setup>`) is the default. Version-adaptive: notes mark 3.3/3.4/3.5 features and Vue 2 fallbacks. Assumes JS/TS lore is separate.

## SFC + `<script setup>`

DO
- Default to `<script setup>` — least boilerplate, best TS inference. Top-level bindings auto-expose to template.
- Use compiler macros (no import): `defineProps`, `defineEmits`, `defineExpose`, and `defineModel` (3.4+), `defineOptions`/`defineSlots` (3.3+).
- Type props/emits with generics: `defineProps<{ id: number; label?: string }>()` and the succinct emit tuple form (3.3+): `defineEmits<{ change: [id: number] }>()`.
- Prop defaults: destructure defaults are reactive in 3.5+ — `const { msg = 'hi' } = defineProps<Props>()`. On ≤3.4 use `withDefaults(defineProps<Props>(), { msg: 'hi' })` (wrap array/object defaults in a factory fn).
- `defineExpose({...})` to surface members to a template ref — components are closed by default.

DON'T
- Don't mix runtime and type declaration in one `defineProps`/`defineEmits` — compile error.
- Don't reference local `setup` variables inside `defineProps`/`defineEmits`/`defineOptions` — they hoist to module scope (imports are fine).
- Don't mutate props. Emit an event or use `defineModel`.
- Don't reach for `useSlots()`/`useAttrs()` in templates — use `$slots`/`$attrs`. They're for script logic only.

## v-model (component)

Vue 3 default = `modelValue` prop + `update:modelValue` event (Vue 2 was `value`/`input`). `.sync` and the `model` option are removed — use `v-model:arg`.

DO (3.4+)
```vue
<!-- child -->
<script setup>
const model = defineModel()            // modelValue
const title = defineModel('title', { required: true })  // named
</script>
```
- Multiple bindings: `<C v-model:first-name="a" v-model:last-name="b" />` with a `defineModel('firstName')` each.
- Modifiers: `const [model, mods] = defineModel({ set: v => mods.trim ? v.trim() : v })`. Named-arg modifiers land as `arg + "Modifiers"` prop.

DON'T
- On ≤3.3, `defineModel` doesn't exist — declare the prop + `emit('update:modelValue', v)` manually, or use a writable computed.
- Don't set a `default` on `defineModel` unless the parent may omit the binding — it desyncs parent (`undefined`) vs child (default).

## Slots

DO
- Named slots via `<slot name="header">`; parent supplies `<template #header>` (`#` = `v-slot:` shorthand). Unnamed = `default`.
- Provide fallback: `<slot>Fallback</slot>` renders only when no content passed.
- Scoped slots: child does `<slot :row="item" />`, parent destructures `<template #row="{ row }">`.
- Guard optional regions with `v-if="$slots.header"`. Dynamic names: `<template #[name]>`.

DON'T
- Slot content compiles in the PARENT scope — it can't see child data except via scoped-slot props.
- Don't put `v-slot` on the component tag when also using named slots — use explicit `<template #default>` (mixing errors out).

## Lifecycle hooks (Composition API)

Call synchronously in `setup`/`<script setup>`. Import from `vue`.

`onBeforeMount` `onMounted` `onBeforeUpdate` `onUpdated` `onBeforeUnmount` `onUnmounted` `onErrorCaptured` `onActivated`/`onDeactivated` (KeepAlive) `onServerPrefetch` (SSR) `onRenderTracked`/`onRenderTriggered` (dev-only).

DO
- `onMounted` for DOM/refs and side effects; pair every subscription/timer with `onUnmounted` cleanup.
- `onErrorCaptured((err, inst, info) => false)` — return `false` to stop propagation.

DON'T
- Vue 3 renamed `beforeDestroy`→`onBeforeUnmount`, `destroyed`→`onUnmounted`. Don't use the old names.
- Don't register hooks in async callbacks/`await` — must be sync during setup.

## v-if vs v-show

- `v-if`: real conditional, mounts/unmounts (lazy, cheaper init, costlier toggle). Supports `v-else`/`v-else-if` and `<template>`.
- `v-show`: always rendered, toggles CSS `display` (cheaper toggle). No `<template>`, no `v-else`.
- DO use `v-show` for frequent toggles; `v-if` for rarely-changing conditions.

## v-for + key

DO
- Always bind a stable, unique, primitive `:key` (`item.id`) so Vue reorders instead of in-place patching stateful nodes.
- Put `:key` on `<template v-for>`, not the inner element.
- Filter with a computed, not inline `v-if`.

DON'T
- Don't use array index as key when the list reorders/filters/mutates — breaks form/component state.
- Don't put `v-if` + `v-for` on the same element. In Vue 3 `v-if` evaluates FIRST (Vue 2: `v-for` first), so `v-if` can't see the loop variable. Move `v-for` to a wrapping `<template>`.
- `v-for="n in 10"` starts at 1, not 0. Object form: `(value, key, index)`.

## Dynamic components

DO
- `<component :is="tab" />` — `is` takes a component (import ref) or, in-DOM templates, a registered name/string.
- Wrap in `<KeepAlive>` to preserve state of swapped components; use `onActivated`/`onDeactivated` there.

DON'T
- With `<script setup>`, `:is` needs the actual component in scope (imported), not a bare name string.

## Teleport

Vue 3.

DO
- `<Teleport to="body">…</Teleport>` for modals/overlays escaping `overflow`/`transform`/`z-index` ancestors. Logical tree (props/inject/events) unchanged.
- `:disabled` to render inline conditionally (e.g. mobile). Multiple teleports to one target append in order.
- `defer` (3.5+) when the target renders later in the same tick.

DON'T
- Target must exist in the DOM when Teleport mounts (unless `defer`).

## Async components & Suspense

DO
```js
const Comp = defineAsyncComponent(() => import('./Comp.vue'))
```
- Advanced: `{ loader, loadingComponent, delay: 200, errorComponent, timeout }`.
- Lazy hydration (3.5+, SSR only): `hydrate: hydrateOnVisible()` / `hydrateOnIdle()` / `hydrateOnInteraction('click')` / `hydrateOnMediaQuery(...)` — import each strategy for tree-shaking.
- `<Suspense>`: `#default` holds async children, `#fallback` shows while resolving.

DON'T
- `<Suspense>` is still experimental (API may change) — don't rely on it for critical prod flows without guarding.
- Don't wrap `defineAsyncComponent` call itself in the render — define it at module scope.

## Vue 2 fallbacks (only if on Vue 2)
- No `<script setup>`/Composition macros (unless `@vue/composition-api`). Use Options API: `data/computed/methods/props`.
- v-model = `value`/`input`; multiple bindings via `.sync`; rename via `model` option.
- Slots: legacy `slot`/`slot-scope` (deprecated) → `v-slot`. No Teleport/Suspense/`defineModel`.

## Sources
- https://vuejs.org/api/sfc-script-setup.html
- https://vuejs.org/guide/components/v-model.html
- https://vuejs.org/guide/components/slots.html
- https://vuejs.org/api/composition-api-lifecycle.html
- https://vuejs.org/guide/essentials/conditional.html
- https://vuejs.org/guide/essentials/list.html
- https://vuejs.org/guide/built-ins/teleport.html
- https://vuejs.org/guide/components/async.html
- https://vuejs.org/guide/built-ins/suspense.html

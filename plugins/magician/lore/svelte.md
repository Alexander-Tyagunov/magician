# Svelte — core digest

Version cue: Svelte 5 (current) = runes + snippets + `onclick` attrs. Svelte 4 = `export let`, `$:`, `on:`, `<slot>`, stores. Runes work only in `.svelte`/`.svelte.js`/`.svelte.ts`; not imported, assigned, or passed as args.

DO declare state `let x = $state(0)`; mutate deeply (`arr.push`, `obj.a=1`)—it's proxied. DON'T destructure `$state` (loses reactivity) or export a reassigned `$state` from a module (mutate a property or expose getters instead).
DO derive with `$derived(expr)` / `$derived.by(fn)`. DON'T sync state in `$effect`—it's a browser-only escape hatch (analytics, DOM); avoid updating state inside it; link values via function bindings/callbacks, not effects.
DO props: `let { a, b = 1 } = $props()`; two-way via `$bindable()`. DON'T use `export let` (Svelte 4).
DO events as attributes `onclick={fn}` (case-sensitive); no `|preventDefault` modifier—call `e.preventDefault()` in the handler. DON'T use `on:click` or `createEventDispatcher`—pass callback props.
DO pass content via `{#snippet row()}...{/snippet}` + `{@render row()}`. DON'T use `<slot>` (legacy).
DO `$state.raw` for large immutable data (reassign, never mutate); `$state.snapshot(x)` before handing state to external libs. Class instances aren't proxied.

Commands: `npx sv create app` · `sv add <addon>` · `sv migrate svelte-5` · `sv check`

Deep dive when writing non-trivial svelte — read lore/svelte/{runes-and-reactivity,components-and-stores}.md
Sources: svelte.dev/docs/svelte {what-are-runes,$state,$effect,basic-markup}, svelte.dev/docs/cli

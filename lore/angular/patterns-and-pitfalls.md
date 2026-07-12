# angular — Patterns & pitfalls

Scope: Angular-specific guidance. Assume JS/TS lore lives elsewhere. Latest stable: **v22** (2026-06-03); v20/v21 are LTS. Default to **standalone components + signals + built-in control flow**. NgModules still supported but legacy for new code. Version-tag every feature; verify against angular.dev before relying on anything below v-tagged "dev preview".

## Change detection: zone.js → zoneless / OnPush

DO
- New apps: enable zoneless. `bootstrapApplication(App, { providers: [provideZonelessChangeDetection()] })`. Stable API since **v20**; **default in v21+** (no provider needed — just don't add `provideZoneChangeDetection`).
- On v18/v19 (dev preview): use `provideExperimentalZonelessChangeDetection()` and drop `zone.js` from `polyfills`.
- Until zoneless: set `changeDetection: ChangeDetectionStrategy.OnPush` on every component. It bounds CD to input identity changes, signal reads, events, and `async` pipe emissions. (v21 renamed `.Default` → `.Eager` and makes OnPush the default.)
- Zoneless/OnPush notify triggers: signal update read in template, `async` pipe, `ComponentRef.setInput`, template/host listeners, `markForCheck()`. Ensure every state mutation hits one.

DON'T
- Don't mutate arrays/objects in place under OnPush and expect a re-render — replace the reference (`this.items = [...this.items, x]`) or use a signal.
- Don't call `detectChanges()`/`ApplicationRef.tick()` to paper over missed notifications — find the missing trigger.
- Don't rely on `setTimeout`/`Promise`/rxjs to auto-trigger CD once zoneless — only the notify triggers above schedule it.

## Signals to cut change detection

DO
- Model component state as `signal()`; derive with `computed()` (lazy + memoized). Stable since **v17**.
- Read signals in templates — a changed signal marks only that view dirty, the finest-grained CD Angular offers.
- Use `input()` / `input.required()` (signal inputs), `output()`, `model()` (two-way), and signal `viewChild`/`contentChild` queries — all **stable in v19** (dev preview v17.1–17.3).
- `effect()` for syncing signals to imperative/non-signal APIs only — last resort per docs. Ties to injection context; auto-cleans.
- `linkedSignal()` (writable derived state) and `resource()`/`httpResource()` (async→signal): **v19+, still stabilizing** — confirm status before shipping.

DON'T
- Don't put derivations in `effect()` — use `computed()`; use `linkedSignal()` when it must also be settable.
- Don't write to a signal inside `computed()` or during template read.
- Don't forget signals are getters: read with `count()`, never `count` (that's the function).

## Standalone & smart/dumb components

DO
- Use standalone components (`standalone: true` is the **default since v19**; explicit flag needed v15–18). Import deps in the component's `imports: []`.
- Split **container (smart)** — injects services, holds state, orchestrates — from **presentational (dumb)** — `input()` in, `output()` out, OnPush, no service injection.
- Inject with the `inject()` function (v14+) over constructor params in standalone/functional code.

DON'T
- Don't inject data services into leaf/presentational components — pass data via inputs.
- Don't reach for an NgModule for a new feature; use standalone + `Routes`.

## Typed reactive forms

DO
- Reactive forms are strictly typed **by default since v14**. Let inference type controls (`new FormControl('')` → `FormControl<string|null>`).
- Use `{ nonNullable: true }` (or `NonNullableFormBuilder` / `fb.nonNullable.group(...)`) so `.reset()` restores the initial value, not `null`, and drops `|null` from the type.
- Type `FormGroup` via an interface of controls for editor safety.

DON'T
- Don't use `UntypedFormControl`/`UntypedFormGroup` in new code — only as a temporary migration bridge.
- Don't assume `.value` is fully populated — disabled controls are omitted; use `.getRawValue()` for the complete shape.
- Prefer reactive forms over template-driven for anything non-trivial (validation, typing, testability).

## Lazy routes & deferrable views

DO
- Lazy-load routes with `loadComponent: () => import('./x').then(m => m.X)` (standalone) or `loadChildren` for route arrays. Split at feature boundaries.
- Guard/resolve with functional guards (`CanActivateFn`, `ResolveFn`) — tree-shakable, `inject()`-based.
- Defer in-template heavy/below-the-fold UI with `@defer` blocks + triggers (`on viewport`, `on idle`, `on interaction`) and `@placeholder`/`@loading`/`@error`. Dev preview **v17**, **stable v18**.

DON'T
- Don't eagerly import a whole feature into the root/App component — it defeats code-splitting.
- Don't lazy-load tiny always-visible components; the request overhead outweighs the win.

## Templates: control flow & track

DO
- Use built-in `@if` / `@for` / `@switch` (dev preview **v17**, **stable v18**). Faster and no import needed vs structural directives.
- `@for` **requires** `track`: `@for (u of users(); track u.id) { ... }`. Pick a stable unique id so Angular reuses DOM nodes; use `track $index` only for static/primitive lists.
- Use `@empty {}` for the empty state; use `@if (...; as v)` to alias.

DON'T
- Don't `track` by the item object for data that gets re-fetched/re-created — identity changes force full re-render (the old `*ngFor` default; `@for` bans this footgun by requiring track).
- Don't reach for `*ngIf`/`*ngFor`/`ngSwitch` in new templates. (`ng generate @angular/core:control-flow` migrates existing.)

## RxJS: avoid nested subscribes & leaks

DO
- Flatten dependent streams with `switchMap`/`concatMap`/`mergeMap`/`exhaustMap` — never subscribe inside a subscribe.
- Prefer the `async` pipe in templates (auto-subscribe/unsubscribe, marks for check) over manual `.subscribe()`.
- For manual subscriptions, auto-tear-down with `takeUntilDestroyed()` (v16+) — call in an injection context or pass a `DestroyRef`.
- Interop: `toSignal(obs$)` to consume a stream as a signal; `toObservable(sig)` for the reverse (v16+).

DON'T
- Don't nest `subscribe()` — leaks + races. `switchMap` cancels the stale inner stream.
- Don't hand-roll `ngOnDestroy` + `Subject` teardown when `takeUntilDestroyed()`/`async` pipe do it.
- Don't call `.subscribe()` just to assign a value you only read in the template — use `async` or `toSignal`.

## Sources
- https://angular.dev/overview
- https://angular.dev/guide/zoneless
- https://angular.dev/api/core/provideZonelessChangeDetection
- https://v18.angular.dev/api/core/provideExperimentalZonelessChangeDetection
- https://angular.dev/guide/signals
- https://angular.dev/guide/signals/linked-signal
- https://angular.dev/guide/signals/effect
- https://angular.dev/guide/components/inputs
- https://angular.dev/guide/templates/control-flow
- https://angular.dev/guide/forms/typed-forms
- https://angular.dev/roadmap
- https://angular.dev/reference/releases

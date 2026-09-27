# angular — deep dive

> On-demand companion to `lore/angular.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Components, DI & signals](#components-di-and-signals) · [RxJS & async](#rxjs-and-async) · [Patterns & pitfalls](#patterns-and-pitfalls)

## Components, DI & signals <a id="components-di-and-signals"></a>

Current stable: **v22** (2026-06). Modern Angular = standalone + `inject()` + signals + built-in control flow. Detect the repo's version (`package.json` → `@angular/core`) and adapt. Never claim a feature earlier than the versions below.

### Verified version map (do not invent)

- `inject()` function — **v14**.
- Standalone components — dev preview **v14**, recommended authoring format **v17**, the **default v19+** (best-practices doc: default in v20+). Don't write `standalone: true`.
- `signal()` / `computed()` — dev preview v16, stable **v17**.
- Built-in control flow `@if`/`@for`/`@switch` — dev preview v17, **stable v18**.
- Deferrable views `@defer` — dev preview v17, stable v18.
- Signal inputs `input()` / `input.required()` — dev preview **v17.1**, stable v19.
- `output()` function — **v17.3**, stable v19.
- `model()` two-way — **v17.2**, stable v19.
- Signal queries `viewChild`/`contentChild`(`ren`) — dev preview v17.2/17.3, stable v19.
- `linkedSignal` — v19, stable **v20**. `resource()` — introduced v19, **stable since v22**.
- Full reactivity set (`signal`,`effect`,`linkedSignal`,queries,inputs) **graduated stable v20**.

### Components (standalone-first)

DO
- Author standalone. Import deps directly in the component's `imports: []`.
- Use `changeDetection: ChangeDetectionStrategy.OnPush` for every new component (mandatory with signals; enables zoneless).
- Keep template/styles in separate files for non-trivial components.

DON'T
- Don't add `standalone: true` on v19+ — it's the default and linted against.
- Don't create `NgModule`s for new features. NgModules are legacy; only touch them in pre-v15 code or when interop demands it. To interop a standalone component into an old NgModule, add it to that module's `imports`.

```ts
import { Component, ChangeDetectionStrategy, input } from '@angular/core';
@Component({
  selector: 'app-user-card',
  imports: [DatePipe],           // direct deps, no NgModule
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `{{ name() }} — {{ joined() | date }}`,
})
export class UserCard {
  name = input.required<string>();
  joined = input<Date>();
}
```

Bootstrap (v14+): `bootstrapApplication(App, { providers: [...] })` in `main.ts` — no `AppModule`.

### Dependency injection

DO
- Prefer `inject()` over constructor params (works in field initializers, cleaner for mixins/inheritance).
- Register app-wide singletons with `@Injectable({ providedIn: 'root' })` — tree-shakeable, no manual provider wiring.
- Register app config via `provide*` functions in `bootstrapApplication` providers: `provideRouter`, `provideHttpClient`, `provideAnimationsAsync`.
- Call `inject()` only in an **injection context** (field initializer, constructor, `runInInjectionContext`, route guards/resolvers, factory).

DON'T
- Don't call `inject()` in lifecycle hooks, callbacks, or after an `await` — throws "outside injection context". Capture it in a field first.
- Don't register a `root` service again in a component's `providers` unless you deliberately want a scoped instance.

```ts
@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);        // field-initializer injection
}
```

Component-scoped instance: put the token in the component's `providers: []`. Use `InjectionToken<T>` for non-class deps; multi-providers with `{ provide, useValue, multi: true }`.

### Signals (modern reactivity — default for state)

DO
- Model component state as `signal()`; derive with `computed()` (lazy + memoized). Read by calling: `count()`.
- Write with `.set(v)` or `.update(prev => …)`.
- Use `effect()` only for side effects to non-reactive APIs (logging, DOM, `localStorage`). Runs in an injection context; reads are tracked synchronously.
- Expose read-only state via `.asReadonly()`; escape tracking with `untracked()`.
- `linkedSignal({source, computation})` (v19+/stable v20) for writable state that resets from a source. `resource()` (introduced v19, **stable v22**) for async→signal.

DON'T
- No `.mutate()` — removed. Produce a new value (`update(a => [...a, x])`).
- Don't put async/`await` logic inside `effect()` and expect post-await reads to be tracked.
- Don't overuse `effect()` to sync state between signals — use `computed`/`linkedSignal`.
- Don't forget `OnPush`; without it signals still work but you lose the perf/zoneless win.
- RxJS interop: `toSignal()` / `toObservable()` from `@angular/core/rxjs-interop`. Prefer signals for view state, RxJS for streams/events.

```ts
count = signal(0);
double = computed(() => this.count() * 2);
inc() { this.count.update(c => c + 1); }
```

### Inputs / outputs

DO
- Signal inputs (v17.1+): `value = input(0)`, required `id = input.required<string>()`. Read as `this.value()`. Reactive, `computed`-friendly, no `ngOnChanges` needed.
- Two-way: `model()` (v17.2+): `checked = model(false)` → parent binds `[(checked)]`. Writable via `.set()`/`.update()`; auto-emits `checkedChange`.
- Outputs: `output()` function (v17.3+): `changed = output<T>()`; emit `this.changed.emit(v)`.
- Transform/alias: `input(0, { transform: booleanAttribute, alias: 'disabled' })`.

DON'T
- Don't mix decorator and signal styles arbitrarily. `@Input()`/`@Output()` remain supported (fine in older code) but prefer `input()`/`output()` for new work. Migrate with `ng generate @angular/core:signal-input-migration` / `output-migration`.
- `model()` does **not** support transforms.
- Required signal inputs error at **build time** if unbound — don't guard for `undefined`.

### Control flow (templates)

DO
- Use built-in `@if`/`@for`/`@switch` (stable v18+). `track` is **mandatory** in `@for` — use a stable id (`track item.id`); `$index` for static lists.
- Use `@empty` for empty collections; `@else`/`@else if`; `@switch`/`@case`/`@default`.
- Migrate legacy templates: `ng generate @angular/core:control-flow`.

DON'T
- Don't reach for `*ngIf`/`*ngFor`/`[ngSwitch]` in new v17+ code (still valid, needs `CommonModule`/`NgIf`/`NgFor` imports). Built-in flow needs **no imports**.
- Don't omit `track` (won't compile) or track by index on dynamic reorderable lists (breaks reuse).

```html
@for (u of users(); track u.id) {
  <app-user-card [name]="u.name" />
} @empty {
  <p>No users</p>
}
@if (loading()) { <spinner/> } @else { <content/> }
```

### Pre-v17 fallbacks
NgModules + `declarations`; constructor DI; `*ngIf`/`*ngFor` with `CommonModule`; RxJS/`@Input` `set` for reactivity (no signals < v16). Don't back-port `@if`, `input()`, `signal()` into those codebases.

### Sources
- https://angular.dev/overview
- https://angular.dev/guide/signals
- https://angular.dev/guide/components/inputs
- https://angular.dev/guide/templates/control-flow
- https://angular.dev/guide/di
- https://angular.dev/roadmap
- https://angular.dev/reference/releases
- https://angular.dev/reference/migrations/outputs
- https://angular.dev/assets/context/best-practices.md

## RxJS & async <a id="rxjs-and-async"></a>

Framework-specific async patterns. Assumes JS/TS + generic RxJS lore exists elsewhere.
Version anchors: signals stable **v17**; `takeUntilDestroyed` stable **v19** (available since 16);
`httpResource` added **v19.2** (still stabilizing); `HttpClient` injectable by default **v21+**;
`fetch` is the default HTTP backend. Current docs reflect **v22**.

### Observables — mental model

DO
- Treat `HttpClient` results as **cold** Observables — "blueprints" that fire a new request per `subscribe`. No subscription = no request.
- Type responses with a generic: `http.get<Config>(url)`. It is a **type assertion only** — Angular does not validate the payload.
- Encapsulate data access in injectable services; expose Observables, render in templates.

DON'T
- Don't subscribe the same HTTP Observable twice expecting one request — each `subscribe` re-fires. `share`/`shareReplay` if you must fan out.
- Don't assume mutations run — POST/PUT/DELETE need a `subscribe` (or async pipe / `toSignal`) or they never execute.

### Operator choice — pick by concurrency

Higher-order mapping flattens an inner Observable per source emission. Choose by what happens to **overlapping** inner streams:

- `switchMap` — **cancel** prior inner on new emission. Default for typeahead, route params, "latest wins" reads.
- `concatMap` — **queue**, run inners in order, one at a time. Ordered writes / sequential requests.
- `mergeMap` (`flatMap`) — **run all in parallel**, no ordering. Independent fire-and-forget; risks unbounded concurrency.
- `exhaustMap` — **ignore** new emissions while an inner is active. Submit-button double-click guard, login.
- `map` — synchronous value transform, no flattening.

DO
- Default to `switchMap` for reads driven by rapidly-changing inputs (search, filters) to auto-abort stale requests.
- Use `concatMap` when write order matters; `exhaustMap` to drop duplicate submits.

DON'T
- Don't `mergeMap` user-triggered searches — stale responses can arrive after fresh ones and clobber the UI.
- Don't nest `subscribe` inside `subscribe` — flatten with a higher-order operator.

### async pipe — prefer it

DO
- Bind Observables/Promises with `| async`; it subscribes on init and **unsubscribes automatically** on destroy.
- Guard + alias in modern control flow: `@if (data$ | async; as data) { … }` (avoids multiple subscriptions from repeated `| async`).

DON'T
- Don't manually `subscribe` in a component when the value only feeds the template — that reintroduces leak risk. Let the pipe own the lifecycle.
- Don't put `| async` on the same source twice in a template without `as` — each is a separate subscription.

### Manual subscribe — only when you must (side effects)

Manual `subscribe` is correct for imperative side effects (navigation, toasts, non-template writes). It leaks unless you tie it to a lifecycle.

DO — `takeUntilDestroyed` (stable v19, import `@angular/core/rxjs-interop`)
```ts
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
// In injection context (field initializer / constructor): DestroyRef auto-injected
private data = inject(DataService);
ngValue$ = this.data.stream$.pipe(takeUntilDestroyed()).subscribe(/* … */);
```
```ts
// Outside an injection context (e.g. ngOnInit): pass DestroyRef explicitly
private destroyRef = inject(DestroyRef);
ngOnInit() {
  interval(5000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(/* … */);
}
```

DON'T
- Don't call `takeUntilDestroyed()` **without** a `DestroyRef` argument outside an injection context — it throws (no context to inject from). Capture `inject(DestroyRef)` in a field, pass it in.
- Don't hand-roll a `Subject` + `ngOnDestroy` teardown when `takeUntilDestroyed` / async pipe / `toSignal` already handle it.
- Don't forget: `takeUntilDestroyed` **completes** the stream on destroy — put it last (or after operators that must see completion).

### Signals interop (`@angular/core/rxjs-interop`)

`toSignal(obs$, opts?)` — subscribes immediately, tracks latest value as a signal, **auto-unsubscribes on destroy**. Read it as `sig()`; reuse the returned signal, don't re-call `toSignal`.

Options:
- `initialValue` — value before first emission (else `undefined`).
- `requireSync: true` — for synchronous sources (`BehaviorSubject`); guarantees a value, drops `undefined` from the type.
- `manualCleanup: true` — opt out of auto-unsubscribe (self-completing streams).
- `equal` — custom equality; equal values don't update the signal.

`toObservable(sig, opts?)` — signal → Observable via an internal `effect` + `ReplaySubject(1)`. First value may be sync; later ones async and only the **settled** value after a batch of rapid updates emits.

DO
- Prefer `toSignal` over manual subscribe when you want a signal in TS or template.
- Pass an `Injector` via options when calling outside an injection context.

DON'T
- Don't call `toSignal` / `toObservable` inside `computed`/`effect` — throws **NG0602** (side-effecting). Create the signal at field level, read it inside `computed`.
- Don't ignore errors: a source error is **re-thrown when you read** the `toSignal` signal. Handle upstream (`catchError`) if the read must stay safe.

### HttpClient

Setup (standalone `app.config.ts` or NgModule `providers`):
```ts
provideHttpClient(withInterceptors([authInterceptor]))
```
- `fetch` is the **default** backend — no `withFetch()` needed on current versions.
- `withInterceptors([...])` — functional interceptors (**recommended**, predictable order).
- `withInterceptorsFromDi()` — legacy class-based interceptors.
- `withXhr()` — force `XMLHttpRequest` (e.g. upload-progress events, unsupported by fetch).
- Legacy `HttpClientModule` ≡ `provideHttpClient(withInterceptorsFromDi(), withXhr())` — migrate to `provideHttpClient`.
- Test: `provideHttpClientTesting()` from `@angular/common/http/testing`.

DO
- Inject with `private http = inject(HttpClient)`.
- Set `observe: 'response'` for full response, `observe: 'events'` for progress; use `as const` when extracting options objects (literal types for `observe`/`responseType`).
- Treat `HttpParams` / `HttpHeaders` as **immutable** — `set`/`append` return new instances.

DON'T
- Don't use `withXhr()` for SSR — server XHR support is **deprecated, slated for removal in v23** (unsafe redirect handling). Use fetch on the server.
- Don't rely on the fetch backend for upload progress — it doesn't report it; use `withXhr()`.

### httpResource — reactive fetch (v19.2+, stabilizing)

Signal-based wrapper over `HttpClient`. Fires **eagerly** (no subscribe) and re-requests when a tracked signal changes, cancelling the pending request first. Read-only — **not for mutations**.
```ts
userId = input.required<string>();
user = httpResource(() => `/api/user/${userId()}`);  // re-fetches when userId() changes
```
Exposes `value()`, `error()`, `isLoading()`, `hasValue()`.

DO — guard reads: `@if (user.hasValue()) { … user.value() … }`. Reading `value()` in an error state throws.
DON'T — don't use for POST/PUT/DELETE; call `HttpClient` directly. `rxResource({ stream })` is the Observable-fed sibling.

### Sources
- https://angular.dev/ecosystem/rxjs-interop
- https://angular.dev/api/core/rxjs-interop/takeUntilDestroyed
- https://angular.dev/guide/http/making-requests
- https://angular.dev/guide/http/setup
- https://angular.dev/guide/http/http-resource
- https://github.com/angular/angular (rxjs-interop source; NG0602 / NG0205 error refs)

## Patterns & pitfalls <a id="patterns-and-pitfalls"></a>

Scope: Angular-specific guidance. Assume JS/TS lore lives elsewhere. Latest stable: **v22** (2026-06-03); v20/v21 are LTS. Default to **standalone components + signals + built-in control flow**. NgModules still supported but legacy for new code. Version-tag every feature; verify against angular.dev before relying on anything below v-tagged "dev preview".

### Change detection: zone.js → zoneless / OnPush

DO
- New apps: enable zoneless. `bootstrapApplication(App, { providers: [provideZonelessChangeDetection()] })`. Stable API since **v20**; **default in v21+** (no provider needed — just don't add `provideZoneChangeDetection`).
- On v18/v19 (dev preview): use `provideExperimentalZonelessChangeDetection()` and drop `zone.js` from `polyfills`.
- Until zoneless: set `changeDetection: ChangeDetectionStrategy.OnPush` on every component. It bounds CD to input identity changes, signal reads, events, and `async` pipe emissions. (v21 renamed `.Default` → `.Eager` and makes OnPush the default.)
- Zoneless/OnPush notify triggers: signal update read in template, `async` pipe, `ComponentRef.setInput`, template/host listeners, `markForCheck()`. Ensure every state mutation hits one.

DON'T
- Don't mutate arrays/objects in place under OnPush and expect a re-render — replace the reference (`this.items = [...this.items, x]`) or use a signal.
- Don't call `detectChanges()`/`ApplicationRef.tick()` to paper over missed notifications — find the missing trigger.
- Don't rely on `setTimeout`/`Promise`/rxjs to auto-trigger CD once zoneless — only the notify triggers above schedule it.

### Signals to cut change detection

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

### Standalone & smart/dumb components

DO
- Use standalone components (`standalone: true` is the **default since v19**; explicit flag needed v15–18). Import deps in the component's `imports: []`.
- Split **container (smart)** — injects services, holds state, orchestrates — from **presentational (dumb)** — `input()` in, `output()` out, OnPush, no service injection.
- Inject with the `inject()` function (v14+) over constructor params in standalone/functional code.

DON'T
- Don't inject data services into leaf/presentational components — pass data via inputs.
- Don't reach for an NgModule for a new feature; use standalone + `Routes`.

### Typed reactive forms

DO
- Reactive forms are strictly typed **by default since v14**. Let inference type controls (`new FormControl('')` → `FormControl<string|null>`).
- Use `{ nonNullable: true }` (or `NonNullableFormBuilder` / `fb.nonNullable.group(...)`) so `.reset()` restores the initial value, not `null`, and drops `|null` from the type.
- Type `FormGroup` via an interface of controls for editor safety.

DON'T
- Don't use `UntypedFormControl`/`UntypedFormGroup` in new code — only as a temporary migration bridge.
- Don't assume `.value` is fully populated — disabled controls are omitted; use `.getRawValue()` for the complete shape.
- Prefer reactive forms over template-driven for anything non-trivial (validation, typing, testability).

### Lazy routes & deferrable views

DO
- Lazy-load routes with `loadComponent: () => import('./x').then(m => m.X)` (standalone) or `loadChildren` for route arrays. Split at feature boundaries.
- Guard/resolve with functional guards (`CanActivateFn`, `ResolveFn`) — tree-shakable, `inject()`-based.
- Defer in-template heavy/below-the-fold UI with `@defer` blocks + triggers (`on viewport`, `on idle`, `on interaction`) and `@placeholder`/`@loading`/`@error`. Dev preview **v17**, **stable v18**.

DON'T
- Don't eagerly import a whole feature into the root/App component — it defeats code-splitting.
- Don't lazy-load tiny always-visible components; the request overhead outweighs the win.

### Templates: control flow & track

DO
- Use built-in `@if` / `@for` / `@switch` (dev preview **v17**, **stable v18**). Faster and no import needed vs structural directives.
- `@for` **requires** `track`: `@for (u of users(); track u.id) { ... }`. Pick a stable unique id so Angular reuses DOM nodes; use `track $index` only for static/primitive lists.
- Use `@empty {}` for the empty state; use `@if (...; as v)` to alias.

DON'T
- Don't `track` by the item object for data that gets re-fetched/re-created — identity changes force full re-render (the old `*ngFor` default; `@for` bans this footgun by requiring track).
- Don't reach for `*ngIf`/`*ngFor`/`ngSwitch` in new templates. (`ng generate @angular/core:control-flow` migrates existing.)

### RxJS: avoid nested subscribes & leaks

DO
- Flatten dependent streams with `switchMap`/`concatMap`/`mergeMap`/`exhaustMap` — never subscribe inside a subscribe.
- Prefer the `async` pipe in templates (auto-subscribe/unsubscribe, marks for check) over manual `.subscribe()`.
- For manual subscriptions, auto-tear-down with `takeUntilDestroyed()` (v16+) — call in an injection context or pass a `DestroyRef`.
- Interop: `toSignal(obs$)` to consume a stream as a signal; `toObservable(sig)` for the reverse (v16+).

DON'T
- Don't nest `subscribe()` — leaks + races. `switchMap` cancels the stale inner stream.
- Don't hand-roll `ngOnDestroy` + `Subject` teardown when `takeUntilDestroyed()`/`async` pipe do it.
- Don't call `.subscribe()` just to assign a value you only read in the template — use `async` or `toSignal`.

### Sources
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

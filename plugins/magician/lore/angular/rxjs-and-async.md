# angular — RxJS & async

Framework-specific async patterns. Assumes JS/TS + generic RxJS lore exists elsewhere.
Version anchors: signals stable **v17**; `takeUntilDestroyed` stable **v19** (available since 16);
`httpResource` added **v19.2** (still stabilizing); `HttpClient` injectable by default **v21+**;
`fetch` is the default HTTP backend. Current docs reflect **v22**.

## Observables — mental model

DO
- Treat `HttpClient` results as **cold** Observables — "blueprints" that fire a new request per `subscribe`. No subscription = no request.
- Type responses with a generic: `http.get<Config>(url)`. It is a **type assertion only** — Angular does not validate the payload.
- Encapsulate data access in injectable services; expose Observables, render in templates.

DON'T
- Don't subscribe the same HTTP Observable twice expecting one request — each `subscribe` re-fires. `share`/`shareReplay` if you must fan out.
- Don't assume mutations run — POST/PUT/DELETE need a `subscribe` (or async pipe / `toSignal`) or they never execute.

## Operator choice — pick by concurrency

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

## async pipe — prefer it

DO
- Bind Observables/Promises with `| async`; it subscribes on init and **unsubscribes automatically** on destroy.
- Guard + alias in modern control flow: `@if (data$ | async; as data) { … }` (avoids multiple subscriptions from repeated `| async`).

DON'T
- Don't manually `subscribe` in a component when the value only feeds the template — that reintroduces leak risk. Let the pipe own the lifecycle.
- Don't put `| async` on the same source twice in a template without `as` — each is a separate subscription.

## Manual subscribe — only when you must (side effects)

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

## Signals interop (`@angular/core/rxjs-interop`)

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

## HttpClient

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

## httpResource — reactive fetch (v19.2+, stabilizing)

Signal-based wrapper over `HttpClient`. Fires **eagerly** (no subscribe) and re-requests when a tracked signal changes, cancelling the pending request first. Read-only — **not for mutations**.
```ts
userId = input.required<string>();
user = httpResource(() => `/api/user/${userId()}`);  // re-fetches when userId() changes
```
Exposes `value()`, `error()`, `isLoading()`, `hasValue()`.

DO — guard reads: `@if (user.hasValue()) { … user.value() … }`. Reading `value()` in an error state throws.
DON'T — don't use for POST/PUT/DELETE; call `HttpClient` directly. `rxResource({ stream })` is the Observable-fed sibling.

## Sources
- https://angular.dev/ecosystem/rxjs-interop
- https://angular.dev/api/core/rxjs-interop/takeUntilDestroyed
- https://angular.dev/guide/http/making-requests
- https://angular.dev/guide/http/setup
- https://angular.dev/guide/http/http-resource
- https://github.com/angular/angular (rxjs-interop source; NG0602 / NG0205 error refs)

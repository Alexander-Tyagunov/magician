# Go — Concurrency

Lore for an AI agent writing concurrent Go. Terse, version-adaptive. Current stable is the Go 1.26 line (Feb 2026); Go 1.25 still supported. Give the modern form AND the fallback; never claim a feature earlier than the release that shipped it. Golden rules: don't share memory without sync (channels OR a lock per datum, never race); every goroutine needs a guaranteed exit path; never copy a value holding a `Mutex`/`WaitGroup`/`atomic.*`.

## Goroutines & the loop-var trap

DO
- Launch with `go f(args)`; prefer passing args over closing over outer vars. Goroutines are NOT garbage-collected — each must return on its own.
- Under `go 1.22`+ in `go.mod`, loop vars are per-iteration: `for _, v := range xs { go func(){ use(v) }() }` is correct.
- Cap concurrency (worker pool, `SetLimit`, semaphore channel) — never spawn unbounded goroutines from a request or loop.

DON'T
- DON'T rely on per-iteration loop vars if the module targets `go 1.21` or earlier — there the classic bug prints the last value N times. Fallback: shadow `v := v` before the `go`. (Fixed in Go 1.22; the `x := x` copy is no longer needed under 1.22+.)
- DON'T assume `main` waits for goroutines — when `main` returns the program exits. Join via channel, `WaitGroup`, or `errgroup`.

## Channels — buffered vs unbuffered

DO
- Unbuffered `make(chan T)`: send blocks until a receiver is ready — a sync handshake. Default choice.
- Buffered `make(chan T, n)`: send blocks only when full. Use for known burst capacity or to decouple rates. A size-1 error channel lets a producer send its final error without blocking.
- Use directional types in signatures: `<-chan T` (receive-only), `chan<- T` (send-only).
- `v, ok := <-ch` detects closure (`ok==false`); a closed channel yields the zero value immediately.

DON'T
- DON'T pick a buffer size to "fix" a deadlock or leak — it hides the real ordering bug.
- DON'T send/receive on a nil channel (blocks forever) unless deliberately disabling a `select` arm.

## Closing channels — the sender closes

DO
- The SENDING side closes, only when all sends are done. `close(ch)` broadcasts: every current and future receiver unblocks with the zero value.
- `for v := range ch { ... }` drains until closed — idiomatic consumer.
- Multiple senders on one channel: none may close it. Use `WaitGroup` + a dedicated closer: `go func(){ wg.Wait(); close(ch) }()`.

DON'T
- DON'T close from the receiver, double-close, or send on a closed channel — all panic. Ensure all sends finish before `close`.
- DON'T close to mean "stop" if others may still send — cancel via a separate `done`/`ctx` channel receivers select on.

## select

DO
- Blocks until one ready case fires; ties chosen pseudo-randomly.
- Add `case <-ctx.Done():` (or `<-done:`) to every blocking send/receive in a long-lived goroutine so it can bail and return.
- `default:` = non-blocking try. `case <-time.After(d):` adds a timeout (leaks the timer until it fires — in hot loops use `time.NewTimer`+`Stop`, or prefer a `ctx` deadline).

```go
select {
case out <- v:          // send, or...
case <-ctx.Done():      // ...bail on cancellation
    return ctx.Err()
}
```

DON'T
- DON'T write a blocking send/receive with no cancellation arm inside a goroutine whose peer may vanish — the canonical leak.

## context.Context — cancellation, deadlines, request values

DO
- Pass `ctx context.Context` as the FIRST param of any function that blocks, does I/O, or spawns goroutines. Name it `ctx`. Roots: `Background()` (top-level), `TODO()` (unsure).
- Derive `WithCancel`/`WithTimeout`/`WithDeadline`/`WithValue`, then `defer cancel()` ALWAYS — skipping it leaks the child until the parent dies (`go vet` flags it).
- Select on `ctx.Done()`; after close, `ctx.Err()` is `Canceled` or `DeadlineExceeded`.
- 1.20+: `WithCancelCause` → `cancel(err)`, then `context.Cause(ctx)` returns it. 1.21+: `AfterFunc(ctx,f)`, `WithoutCancel(parent)`, `WithTimeoutCause`/`WithDeadlineCause`.

DON'T
- DON'T store a `Context` in a struct — thread it through calls. DON'T pass `nil` — use `context.TODO()`.
- DON'T use `context.Value` for optional params/deps — request-scoped data only, keyed by an unexported custom type (never a bare `string`/builtin).

## sync — Mutex, RWMutex, WaitGroup, Once

DO
- `sync.Mutex` zero value is ready. `mu.Lock(); defer mu.Unlock()`; keep critical sections small; embed the mutex beside the data it guards. Use `RWMutex` when reads vastly outnumber writes.
- `WaitGroup`: `Add(n)` BEFORE launching, `defer wg.Done()` inside, `wg.Wait()` to join. 1.25+: `wg.Go(f)` does Add/Done for you (prefer it; `f` must not panic).
- `sync.Once` for exactly-once init: `once.Do(func(){...})`. 1.21+: `OnceValue[T]`/`OnceValues`/`OnceFunc` for lazy memoized values.

DON'T
- DON'T copy any sync type after first use (`Mutex`, `RWMutex`, `WaitGroup`, `Once`, `Map`, `Pool`, `Cond`) — pass by pointer; a struct with a `Mutex` field is non-copyable (`go vet -copylocks`).
- DON'T let the `WaitGroup` counter go negative or `Add` after `Wait` began — panics. DON'T recursively `RLock` (a pending writer deadlocks readers) or upgrade `RLock`→`Lock`.
- DON'T default to `sync.Map` — use a plain map + `Mutex`. `sync.Map` fits only write-once/read-many or disjoint-key access.

## sync/atomic

DO
- Prefer the typed wrappers (1.19): `atomic.Int64`, `Int32`, `Uint64`, `Bool`, `Pointer[T]`, `Value`. Methods: `Load`, `Store`, `Swap`, `CompareAndSwap`; `Add` on ints; `And`/`Or` (1.23) on ints.
- Simple lock-free counters/flags: `var n atomic.Int64; n.Add(1); n.Load()`.
- Typed `Int64`/`Uint64` are auto 64-bit-aligned (safe on 32-bit; the raw `atomic.AddInt64(&x,…)` funcs are not).

DON'T
- DON'T mix atomic and non-atomic access to the same var, or copy an atomic after use.
- DON'T build multi-word invariants from atomics — use a `Mutex`. Atomics guard ONE word.

## Worker pools & bounded parallelism

DO
- Fixed pool: N goroutines `range` a shared `jobs` channel; a separate closer does `wg.Wait(); close(results)`. Workers do NOT close the shared results channel.
- Or a semaphore channel `sem := make(chan struct{}, N)`: `sem<-struct{}{}` before, `<-sem` after.

```go
jobs := make(chan Job); results := make(chan Result)
var wg sync.WaitGroup
for i := 0; i < numWorkers; i++ {
    wg.Go(func(){ for j := range jobs { results <- process(j) } }) // 1.25+; else Add/go/Done
}
go func(){ wg.Wait(); close(results) }()
```

DON'T
- DON'T let workers block forever on send when the consumer stops — select on `ctx.Done()`.

## errgroup (golang.org/x/sync/errgroup) — ergonomic default

DO
- `g, ctx := errgroup.WithContext(parent)`; `g.Go(func() error {...})`; `err := g.Wait()` returns the FIRST non-nil error. The derived `ctx` is canceled on first error — pass it to every task so siblings stop.
- `g.SetLimit(n)` caps concurrency (`Go` blocks until a slot frees); `g.TryGo` starts only if under limit. Under `go 1.22`+ drop the old `i, v := i, v` copy.

DON'T
- DON'T reuse a `Group` across tasks or call `SetLimit` while goroutines run. A zero `Group` (`new(errgroup.Group)`) has no limit and does NOT cancel on error — only `WithContext` gives cancellation.

## Race detector & goroutine leaks

DO
- Run `go test -race ./...` in CI (also `go run/build -race`). It reports real, observed data races at runtime — treat every report as a bug.
- Prove liveness: every goroutine exits via closed input, `ctx.Done()`, or a bounded loop. `defer close(out)` / `defer wg.Done()` guarantee cleanup on all return paths.
- Test time-dependent concurrency with `testing/synctest` (experimental `GOEXPERIMENT=synctest` in 1.24; stable in 1.25) — fake clock + deterministic scheduling, no real sleeps.

DON'T
- DON'T ship `-race` binaries to prod — it is a dev tool (heavy overhead) and catches only races it witnesses.
- DON'T leave a goroutine blocked on an un-cancelable send/receive, or forget `defer cancel()` — both leak.

## Sources
- https://go.dev/doc/effective_go
- https://go.dev/blog/pipelines
- https://pkg.go.dev/context
- https://pkg.go.dev/sync
- https://pkg.go.dev/sync/atomic
- https://pkg.go.dev/golang.org/x/sync/errgroup
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release
- https://go.dev/blog/context-and-structs

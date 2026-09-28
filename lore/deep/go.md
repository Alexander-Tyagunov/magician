# Go — deep dive

> On-demand companion to `lore/go.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Language & idioms](#language-and-idioms) · [Errors](#errors) · [Concurrency](#concurrency) · [net/http & servers](#http-and-servers) · [Testing](#testing) · [Modules & tooling](#modules-and-tooling) · [Performance](#performance)

## Language & idioms <a id="language-and-idioms"></a>

Senior-reviewer checklist for writing idiomatic Go. Verify the module's `go` directive in `go.mod` before assuming a feature exists — language behavior is gated per-module. Current stable is Go 1.26 (2026-02); supported: 1.26, 1.25, 1.24.

### Structs & methods

- DO put behavior on the type via methods; choose the receiver deliberately.
- DO use a pointer receiver `(t *T)` when the method mutates, when `T` is large, or for consistency once any method needs a pointer. Use a value receiver for small immutable types.
- DON'T mix value and pointer receivers on the same type. If one method needs `*T`, give them all `*T`.
- DO remember: a method set of `T` has value-receiver methods; the method set of `*T` has both. An interface value holding a `T` (not `*T`) can't call pointer methods.

### Interfaces

- DO keep interfaces small — one or two methods. Name single-method ones with `-er` (`Reader`, `Writer`, `Stringer`).
- DO **accept interfaces, return concrete types**. Let callers narrow; give them the full type back.
- DO define the interface in the *consumer* package, not the producer. Satisfaction is implicit — no `implements`.
- DON'T add methods to an interface speculatively. Widen only when a real second implementation appears.
- DO use `any` (Go 1.18 alias for `interface{}`) in new code.

```go
func Save(w io.Writer, data []byte) error   // accept interface
func New() *Client                            // return concrete
```

### Embedding (composition, not inheritance)

- DO embed a type (named without a field name) to promote its methods/fields. This is composition, not subclassing.
- DON'T expect dynamic dispatch to the outer type: a promoted method's receiver is the **inner** type. The outer type does not override the inner's calls.
- DO resolve name conflicts explicitly — a shallower name shadows a deeper one; two at the same depth are an error only if referenced.

```go
type Server struct {
    *log.Logger   // promotes Printf, etc.; refer to it as s.Logger
}
```

### Zero values are useful

- DO make the zero value usable so `var x T` works without a constructor. `sync.Mutex`, `bytes.Buffer`, `strings.Builder` all do this.
- DON'T write a `New()` that only sets fields to their zero values.
- DO note map zero value is `nil` (reads OK, **writes panic**) and slice zero value is `nil` (append works).

### Slices vs arrays

- Arrays `[N]T` are fixed-size **values** (copied on assignment/pass). Slices `[]T` are `{ptr, len, cap}` views over a backing array.
- DO understand `append` may reallocate; always assign the result: `s = append(s, x)`.
- DON'T alias-trap: appending to a slice that shares a backing array can overwrite another slice's data.

```go
a := []int{1, 2, 3, 4}
b := a[:2]                 // len 2, cap 4 — shares backing
b = append(b, 99)          // OVERWRITES a[2]! a is now [1 2 99 4]
```

- DO use full-slice expression `a[low:high:max]` to cap capacity and force a copy on next append.
- DO copy explicitly with `copy(dst, src)` when you need independence; `clear(s)` (Go 1.21) zeros elements.

### Maps

- DON'T assume order — map iteration order is randomized. Sort keys for determinism.
- DO use comma-ok to distinguish "absent" from "zero value": `v, ok := m[k]`.
- `delete(m, k)` is safe on a missing key; `clear(m)` (Go 1.21) removes all entries.
- DON'T take the address of a map element (`&m[k]` is illegal) or write to a nil map.

### defer

- DO use `defer` for cleanup next to acquisition (`f.Close()` after `Open`). Deferred calls run LIFO.
- DO note arguments are **evaluated when `defer` executes**, not when the call runs.

```go
defer fmt.Println(i)     // captures i's value NOW
defer func() { fmt.Println(i) }()  // reads i at return time
```

- DON'T `defer` inside a loop expecting per-iteration release — deferreds fire at function return. Wrap the body in a closure or call directly.
- DO use a deferred closure with named results to alter the return value or recover.

### iota

- DO use `iota` for enumerations; it resets to 0 per `const` block and increments per line. Expressions repeat implicitly.

```go
type Level int
const (
    Debug Level = iota   // 0
    Info                 // 1
    Warn                 // 2
)
```

### Generics (Go 1.18)

- DO use type parameters when logic is identical across types (containers, `Map`/`Filter`, `slices`/`maps` helpers).
- DON'T reach for generics when an interface suffices, or to over-abstract a single call site. Prefer concrete code.
- DO write constraints as interfaces with type sets; `|` is union, `~T` means "underlying type T" (matches `type MyInt int`).
- `comparable` (built-in) constrains to `==`/`!=` types; `cmp.Ordered` (Go 1.21) covers `<`-comparable types — prefer it over `golang.org/x/exp/constraints`.

```go
func Keys[K comparable, V any](m map[K]V) []K { ... }
type Number interface { ~int | ~float64 }
```

- Generic type aliases are fully supported as of Go 1.24 (permanent in 1.25).

### Iterators: range-over-func (Go 1.23)

- DO expose sequences via `iter.Seq[V]` / `iter.Seq2[K,V]`; convention is an `All()` method. `for/range` accepts these directly.

```go
func (s *Set[E]) All() iter.Seq[E] {
    return func(yield func(E) bool) {
        for v := range s.m {
            if !yield(v) { return }   // stop if consumer breaks
        }
    }
}
for v := range s.All() { ... }
```

- DO check `yield`'s bool and return on `false` (handles `break`/`return`/`panic`).
- DO use `iter.Pull(seq)` → `(next, stop)` for pull-style consumption; `defer stop()`.
- Pre-1.23 fallback: return a slice or take a callback `func(V) bool`.

### Loop variable (Go 1.22) — classic trap

- Since Go 1.22, each iteration gets a **fresh** loop variable (both 3-clause and range). Closures/goroutines capturing it now see the per-iteration value.
- DON'T assume this in modules declaring `go 1.21` or earlier — old shared-variable semantics still apply there. Under old rules, `i := i` shadow copy is required before capturing.

```go
for _, v := range items {
    go func() { use(v) }()   // Go 1.22+: correct; pre-1.22: all see last v
}
```

### Errors

- DON'T ignore returned errors (`v, _ := f()` for anything that can fail). Handle, wrap, or return.
- DO wrap with `%w` (Go 1.13): `fmt.Errorf("read config: %w", err)`; inspect with `errors.Is` (sentinel) / `errors.As` (typed) (Go 1.13).
- DO join multiple errors with `errors.Join(e1, e2)` (Go 1.20); `errors.Is`/`As` traverse joins.
- DON'T `panic` for ordinary failures — return `error`. Reserve panic for programmer bugs / unrecoverable init.

### Naked returns

- DON'T use naked `return` in long or non-trivial functions — it hides which values escape and invites bugs. Return values explicitly.
- DO limit named results + naked return to short functions where they document intent, or where a deferred closure must mutate the result.

### Other version anchors (verify against go.mod)

- `min`/`max`/`clear` builtins, `log/slog`, `slices`, `maps`, `cmp` packages: Go 1.21.
- `for i := range n` (range over int), `net/http.ServeMux` method+wildcard routing (`"POST /items/{id}"`, `r.PathValue("id")`), `math/rand/v2`: Go 1.22.
- `unique` package (canonicalization/interning): Go 1.23.
- `errors.Join`: Go 1.20. `GOMEMLIMIT` soft memory limit: Go 1.19. Workspaces (`go.work`) & native fuzzing: Go 1.18.

### Sources

- https://go.dev/doc/effective_go
- https://go.dev/ref/spec
- https://go.dev/blog/loopvar-preview
- https://go.dev/blog/range-functions
- https://go.dev/blog/intro-generics
- https://go.dev/doc/go1.21
- https://go.dev/doc/go1.22
- https://go.dev/doc/go1.23
- https://go.dev/doc/go1.24
- https://go.dev/doc/devel/release

## Errors <a id="errors"></a>

Errors are values. `error` is an interface (`Error() string`). Program with them; don't reflexively `if err != nil { return err }`. Current stable: Go 1.26 (1.26.0 2026-02-10). Supported line: 1.26 + 1.25. Feature versions are marked below — never claim one earlier than reality.

### DO — return & wrap

- DO return errors as the last return value. Check every one.
  ```go
  f, err := os.Open(name)
  if err != nil { return err }
  ```
- DO add context by wrapping with `%w` (Go 1.13). The result exposes an `Unwrap` method, keeping the wrapped error inspectable by `Is`/`As`:
  ```go
  return fmt.Errorf("decompress %s: %w", name, err)
  ```
- DO use `%v` (not `%w`) when the underlying error is an implementation detail you do NOT want callers to depend on. Wrapping an error makes it part of your API — commit only if you'll support returning it forever.
- DO wrap sentinels so callers are forced onto `errors.Is`:
  ```go
  var ErrNotFound = errors.New("not found")
  return fmt.Errorf("%q: %w", name, ErrNotFound) // not: return ErrNotFound
  ```

### DON'T — the traps

- DON'T discard with `_`. `_, _ = w.Write(b)` hides real failures. If you truly must ignore, comment why.
- DON'T compare error strings: `err.Error() == "not found"` is brittle and breaks on wrap. Use `errors.Is`/`errors.As`.
- DON'T compare a wrapped error with `==`. `err == ErrNotFound` fails once wrapped; use `errors.Is`.
- DON'T `%w` a value the caller must never couple to (e.g. leaking `*os.PathError` or `sql.ErrNoRows` from an internal DB). That's a permanent API promise.
- DON'T panic for ordinary/expected failures (see panic section).

### Inspecting the chain

An error wraps another if it implements `Unwrap() error` — or `Unwrap() []error` (multi, Go 1.20+). Successive unwrapping forms a tree; `Is`/`As` walk it pre-order, depth-first.

- `errors.Is(err, target) bool` (1.13) — chain-aware sentinel match. Target must be comparable; a type may override with an `Is(error) bool` method.
  ```go
  if errors.Is(err, fs.ErrNotExist) { ... }
  ```
- `errors.As(err, &target) bool` (1.13) — chain-aware type assertion; sets `target` to the first assignable error. Pass a **pointer to the target variable**. Panics if target isn't a non-nil pointer.
  ```go
  var perr *fs.PathError
  if errors.As(err, &perr) { log.Println(perr.Path) }
  ```
- `errors.Unwrap(err) error` (1.13) — single step. Only calls `Unwrap() error`; does NOT traverse `Join`'s `[]error`. Prefer `Is`/`As` over manual unwrap loops.
- `errors.AsType[E error](err error) (E, bool)` (Go 1.26) — generic, type-safe alternative to `As`; now the recommended form where available.
  ```go
  if perr, ok := errors.AsType[*fs.PathError](err); ok { ... }
  ```
  Fallback pre-1.26: use `errors.As`.

### Sentinel vs typed

- **Sentinel** — a package-level `var ErrX = errors.New("...")` for a condition with no payload. Match with `errors.Is`. `errors.New` returns a distinct value per call, so callers MUST reference your exported var, not their own `New` with the same text.
- **Typed** — a struct implementing `error` when callers need fields. Match and extract with `errors.As`.
  ```go
  type QueryError struct { Query string; Err error }
  func (e *QueryError) Error() string { return e.Query + ": " + e.Err.Error() }
  func (e *QueryError) Unwrap() error { return e.Err } // makes Err visible to Is/As
  ```
- Prefer sentinel when callers only branch; typed when they need data.

### errors.Join (Go 1.20) — multiple errors

`errors.Join(errs ...error) error` wraps several errors. Nil args are dropped; all-nil ⇒ nil. Message is newline-joined. The result implements `Unwrap() []error`; inspect with `Is`/`As` (NOT `errors.Unwrap`).
```go
var errs error
for _, x := range xs {
    if err := do(x); err != nil { errs = errors.Join(errs, err) }
}
return errs // nil if every do() succeeded
```
Pre-1.20 fallback: accumulate into a slice/`[]error` and build a custom error type, or use a third-party multierror.

### Errors-are-values patterns

Abstract repeated checks instead of stamping `if err != nil` everywhere.
- **Sticky writer** — record the first error, no-op after:
  ```go
  type errWriter struct { w io.Writer; err error }
  func (e *errWriter) write(b []byte) {
      if e.err != nil { return }
      _, e.err = e.w.Write(b)
  }
  // ...many e.write(...); check e.err once at the end.
  ```
  `bufio.Writer` (check via `Flush`), `archive/zip`, `net/http` use this.
- **Deferred check** — `bufio.Scanner`: loop on `Scan()`, then `if err := scanner.Err(); err != nil`.

Caveat: all-or-nothing end check loses "how far did we get" — use per-op checks when that matters. Always check errors somewhere.

### panic / recover

- DO use `panic` only for truly exceptional / programmer errors: impossible states, broken invariants, unrecoverable init. Library functions should almost never panic.
  ```go
  func init() { if user == "" { panic("no value for $USER") } }
  ```
- DON'T use panic for normal control flow or expected failures — return an `error`.
- `recover` works only inside a deferred function; returns `nil` otherwise. It stops stack unwinding and returns the panic value.
- DO recover at goroutine boundaries so one goroutine's panic doesn't kill the process:
  ```go
  func safelyDo(w *Work) {
      defer func() {
          if r := recover(); r != nil { log.Println("work failed:", r) }
      }()
      do(w)
  }
  ```
- DO recover at a **package boundary** to convert internal panics into returned errors (the `regexp` idiom): deep code panics with a package-local error type; the public entry defers a recover, converts that type to an `error`, and re-panics anything else (a genuine bug).
- DON'T let panics cross your public API. Recover, or don't panic.

### Version cheat-sheet (verified)

- 1.13 — `errors.Is`, `errors.As`, `errors.Unwrap`, `%w` in `fmt.Errorf`.
- 1.20 — `errors.Join`, `Unwrap() []error` multi-error tree.
- 1.26 — `errors.AsType[E]` generic accessor (current stable line).
- Unrelated traps to keep straight: per-iteration loop variables + `net/http.ServeMux` method/wildcard routing + `math/rand/v2` all landed in **1.22** (not earlier); range-over-func iterators + `unique` in 1.23; generic type aliases in 1.24.

### Sources

- https://go.dev/blog/go1.13-errors
- https://pkg.go.dev/errors
- https://go.dev/blog/errors-are-values
- https://go.dev/doc/effective_go
- https://go.dev/doc/go1.22
- https://go.dev/doc/devel/release

## Concurrency <a id="concurrency"></a>

Lore for an AI agent writing concurrent Go. Terse, version-adaptive. Current stable is the Go 1.26 line (Feb 2026); Go 1.25 still supported. Give the modern form AND the fallback; never claim a feature earlier than the release that shipped it. Golden rules: don't share memory without sync (channels OR a lock per datum, never race); every goroutine needs a guaranteed exit path; never copy a value holding a `Mutex`/`WaitGroup`/`atomic.*`.

### Goroutines & the loop-var trap

DO
- Launch with `go f(args)`; prefer passing args over closing over outer vars. Goroutines are NOT garbage-collected — each must return on its own.
- Under `go 1.22`+ in `go.mod`, loop vars are per-iteration: `for _, v := range xs { go func(){ use(v) }() }` is correct.
- Cap concurrency (worker pool, `SetLimit`, semaphore channel) — never spawn unbounded goroutines from a request or loop.

DON'T
- DON'T rely on per-iteration loop vars if the module targets `go 1.21` or earlier — there the classic bug prints the last value N times. Fallback: shadow `v := v` before the `go`. (Fixed in Go 1.22; the `x := x` copy is no longer needed under 1.22+.)
- DON'T assume `main` waits for goroutines — when `main` returns the program exits. Join via channel, `WaitGroup`, or `errgroup`.

### Channels — buffered vs unbuffered

DO
- Unbuffered `make(chan T)`: send blocks until a receiver is ready — a sync handshake. Default choice.
- Buffered `make(chan T, n)`: send blocks only when full. Use for known burst capacity or to decouple rates. A size-1 error channel lets a producer send its final error without blocking.
- Use directional types in signatures: `<-chan T` (receive-only), `chan<- T` (send-only).
- `v, ok := <-ch` detects closure (`ok==false`); a closed channel yields the zero value immediately.

DON'T
- DON'T pick a buffer size to "fix" a deadlock or leak — it hides the real ordering bug.
- DON'T send/receive on a nil channel (blocks forever) unless deliberately disabling a `select` arm.

### Closing channels — the sender closes

DO
- The SENDING side closes, only when all sends are done. `close(ch)` broadcasts: every current and future receiver unblocks with the zero value.
- `for v := range ch { ... }` drains until closed — idiomatic consumer.
- Multiple senders on one channel: none may close it. Use `WaitGroup` + a dedicated closer: `go func(){ wg.Wait(); close(ch) }()`.

DON'T
- DON'T close from the receiver, double-close, or send on a closed channel — all panic. Ensure all sends finish before `close`.
- DON'T close to mean "stop" if others may still send — cancel via a separate `done`/`ctx` channel receivers select on.

### select

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

### context.Context — cancellation, deadlines, request values

DO
- Pass `ctx context.Context` as the FIRST param of any function that blocks, does I/O, or spawns goroutines. Name it `ctx`. Roots: `Background()` (top-level), `TODO()` (unsure).
- Derive `WithCancel`/`WithTimeout`/`WithDeadline`/`WithValue`, then `defer cancel()` ALWAYS — skipping it leaks the child until the parent dies (`go vet` flags it).
- Select on `ctx.Done()`; after close, `ctx.Err()` is `Canceled` or `DeadlineExceeded`.
- 1.20+: `WithCancelCause` → `cancel(err)`, then `context.Cause(ctx)` returns it. 1.21+: `AfterFunc(ctx,f)`, `WithoutCancel(parent)`, `WithTimeoutCause`/`WithDeadlineCause`.

DON'T
- DON'T store a `Context` in a struct — thread it through calls. DON'T pass `nil` — use `context.TODO()`.
- DON'T use `context.Value` for optional params/deps — request-scoped data only, keyed by an unexported custom type (never a bare `string`/builtin).

### sync — Mutex, RWMutex, WaitGroup, Once

DO
- `sync.Mutex` zero value is ready. `mu.Lock(); defer mu.Unlock()`; keep critical sections small; embed the mutex beside the data it guards. Use `RWMutex` when reads vastly outnumber writes.
- `WaitGroup`: `Add(n)` BEFORE launching, `defer wg.Done()` inside, `wg.Wait()` to join. 1.25+: `wg.Go(f)` does Add/Done for you (prefer it; `f` must not panic).
- `sync.Once` for exactly-once init: `once.Do(func(){...})`. 1.21+: `OnceValue[T]`/`OnceValues`/`OnceFunc` for lazy memoized values.

DON'T
- DON'T copy any sync type after first use (`Mutex`, `RWMutex`, `WaitGroup`, `Once`, `Map`, `Pool`, `Cond`) — pass by pointer; a struct with a `Mutex` field is non-copyable (`go vet -copylocks`).
- DON'T let the `WaitGroup` counter go negative or `Add` after `Wait` began — panics. DON'T recursively `RLock` (a pending writer deadlocks readers) or upgrade `RLock`→`Lock`.
- DON'T default to `sync.Map` — use a plain map + `Mutex`. `sync.Map` fits only write-once/read-many or disjoint-key access.

### sync/atomic

DO
- Prefer the typed wrappers (1.19): `atomic.Int64`, `Int32`, `Uint64`, `Bool`, `Pointer[T]`, `Value`. Methods: `Load`, `Store`, `Swap`, `CompareAndSwap`; `Add` on ints; `And`/`Or` (1.23) on ints.
- Simple lock-free counters/flags: `var n atomic.Int64; n.Add(1); n.Load()`.
- Typed `Int64`/`Uint64` are auto 64-bit-aligned (safe on 32-bit; the raw `atomic.AddInt64(&x,…)` funcs are not).

DON'T
- DON'T mix atomic and non-atomic access to the same var, or copy an atomic after use.
- DON'T build multi-word invariants from atomics — use a `Mutex`. Atomics guard ONE word.

### Worker pools & bounded parallelism

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

### errgroup (golang.org/x/sync/errgroup) — ergonomic default

DO
- `g, ctx := errgroup.WithContext(parent)`; `g.Go(func() error {...})`; `err := g.Wait()` returns the FIRST non-nil error. The derived `ctx` is canceled on first error — pass it to every task so siblings stop.
- `g.SetLimit(n)` caps concurrency (`Go` blocks until a slot frees); `g.TryGo` starts only if under limit. Under `go 1.22`+ drop the old `i, v := i, v` copy.

DON'T
- DON'T reuse a `Group` across tasks or call `SetLimit` while goroutines run. A zero `Group` (`new(errgroup.Group)`) has no limit and does NOT cancel on error — only `WithContext` gives cancellation.

### Race detector & goroutine leaks

DO
- Run `go test -race ./...` in CI (also `go run/build -race`). It reports real, observed data races at runtime — treat every report as a bug.
- Prove liveness: every goroutine exits via closed input, `ctx.Done()`, or a bounded loop. `defer close(out)` / `defer wg.Done()` guarantee cleanup on all return paths.
- Test time-dependent concurrency with `testing/synctest` (experimental `GOEXPERIMENT=synctest` in 1.24; stable in 1.25) — fake clock + deterministic scheduling, no real sleeps.

DON'T
- DON'T ship `-race` binaries to prod — it is a dev tool (heavy overhead) and catches only races it witnesses.
- DON'T leave a goroutine blocked on an un-cancelable send/receive, or forget `defer cancel()` — both leak.

### Sources
- https://go.dev/doc/effective_go
- https://go.dev/blog/pipelines
- https://pkg.go.dev/context
- https://pkg.go.dev/sync
- https://pkg.go.dev/sync/atomic
- https://pkg.go.dev/golang.org/x/sync/errgroup
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release
- https://go.dev/blog/context-and-structs

## net/http & servers <a id="http-and-servers"></a>

Lore for writing correct HTTP code with the standard library. Version-adaptive: the
**Go 1.22** `net/http` routing overhaul is the pivotal fact — pre-1.22 you needed a 3rd-party
router for method + wildcard matching. Current stable: **Go 1.26 line** (1.25 also supported).
Verify a feature's version before relying on it.

### Routing — ServeMux (the 1.22 pivot)

Since **Go 1.22**, `ServeMux` patterns accept an HTTP method and `{wildcard}` segments.
Two new methods on `*http.Request`: `PathValue` and `SetPathValue`. Nothing else changed API-wise.

DO (1.22+):
```go
mux := http.NewServeMux()
mux.HandleFunc("GET /items/{id}", func(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")           // single-segment wildcard
	_ = id
})
mux.HandleFunc("POST /items", createItem)
mux.HandleFunc("GET /files/{path...}", serveFiles) // {name...} = all remaining segments; must be last
mux.HandleFunc("GET /items/{$}", listRoot)         // {$} = exact match, not a prefix
```

- `GET` also matches `HEAD`; every other method matches exactly.
- No method registered → the path matches any method (old behavior).
- Trailing-slash pattern `"/items/"` still matches the whole subtree as a prefix. Use `{$}` to pin the exact path.
- Precedence is **most-specific-wins** and **order-independent**: `/items/latest` beats `/items/{id}`; `GET /items/{id}` beats `/items/{id}`.
- Two overlapping patterns where neither is more specific **conflict** → `panic` at registration (startup), in either order. Fail fast — good.
- Unmatched method on a matched path → automatic `405 Method Not Allowed` with an `Allow` header.

DON'T:
- Don't hand-parse `strings.Split(r.URL.Path, "/")` or `switch r.Method` when 1.22 routing covers it.
- Don't put `{path...}` anywhere but the final segment (compile-time-ish panic at registration).
- Don't assume old code with literal `{}` in patterns still means literal — 1.22 treats braces as wildcards. Emergency escape hatch: `GODEBUG=httpmuxgo121=1` restores pre-1.22 semantics.

PRE-1.22 fallback (Go ≤ 1.21): stdlib `ServeMux` had **no** method or wildcard matching. Use
`github.com/go-chi/chi/v5` or `github.com/gorilla/mux`, or manually branch on `r.Method` and slice the path.
`r.PathValue` does not exist before 1.22.

### Handlers & middleware

```go
type Handler interface{ ServeHTTP(http.ResponseWriter, *http.Request) }
type HandlerFunc func(http.ResponseWriter, *http.Request) // adapts a func to Handler
```

DO — middleware is `func(http.Handler) http.Handler`:
```go
func withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.Path, time.Since(start))
	})
}
srv.Handler = withLogging(withAuth(mux)) // chain: outermost runs first
```

DON'T:
- Don't write a header/status after calling `w.Write` — the first `Write` (or `WriteHeader`) flushes the status; later `w.WriteHeader` is a no-op that logs an error.
- Don't ignore the write order: set headers, then `WriteHeader(code)`, then body.

### Context on the request

DO:
- Read the per-request deadline/cancellation via `r.Context()`; it's canceled when the client disconnects or the server times out. Thread it into DB/RPC calls.
- Build outbound requests with `http.NewRequestWithContext(ctx, method, url, body)` (Go 1.13+) so cancellation propagates.
- Attach request-scoped values by wrapping: `r = r.WithContext(context.WithValue(r.Context(), key, val))` in middleware.

DON'T:
- Don't use `http.NewRequest` without a context in production paths — you lose cancellation.
- Don't stash a request-scoped `context.Context` in a struct field; pass it as the first arg.

### Server timeouts — ALWAYS set them

The zero-value `http.Server` has **no timeouts** → a slow-loris client ties up a goroutine forever.

DO:
```go
srv := &http.Server{
	Addr:              ":8080",
	Handler:           mux,
	ReadHeaderTimeout: 5 * time.Second,   // cheapest slow-loris guard; set even if nothing else
	ReadTimeout:       10 * time.Second,  // whole request incl. body
	WriteTimeout:      15 * time.Second,  // response write
	IdleTimeout:       60 * time.Second,  // keep-alive idle
	MaxHeaderBytes:    1 << 20,           // default 1 MiB
}
```
- `ReadHeaderTimeout` falls back to `ReadTimeout` if zero; `IdleTimeout` falls back to `ReadTimeout` if zero.
- Zero/negative = no timeout.
- Cap request bodies with `r.Body = http.MaxBytesReader(w, r.Body, n)` to bound memory.

DON'T:
- Don't call `http.ListenAndServe(addr, handler)` in prod — that uses an internal `Server` with **all timeouts zero**. Construct your own `*http.Server`.

### Graceful shutdown

DO — `Server.Shutdown(ctx)` stops accepting, then waits for in-flight requests up to the ctx deadline:
```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM) // signal.NotifyContext: Go 1.16+
defer stop()

go func() {
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("listen: %v", err)
	}
}()

<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
if err := srv.Shutdown(shutdownCtx); err != nil {
	log.Printf("graceful shutdown failed: %v", err) // deadline hit → some conns still open
	_ = srv.Close()                                  // hard close as fallback
}
```
- `ListenAndServe`/`Serve` return `http.ErrServerClosed` after `Shutdown`/`Close` — treat it as success, not an error.

DON'T:
- Don't use `srv.Close()` as the primary path — it drops active connections abruptly.
- Register long-lived cleanup with `srv.RegisterOnShutdown` if needed. `Shutdown` never cancels in-flight per-request contexts in any version — if you need in-flight work to abort on shutdown, thread your own cancellation (e.g. a base context you cancel).

### HTTP client — never the zero-value default in prod

`http.DefaultClient` (and `http.Get/Post`) have **`Timeout: 0` = no timeout**. A hung server hangs you forever.

DO:
```go
client := &http.Client{Timeout: 10 * time.Second} // covers dial + redirects + reading the body
req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
resp, err := client.Do(req)
if err != nil {
	return err
}
defer resp.Body.Close()          // ALWAYS — even on non-2xx; err==nil means Body is non-nil
_, err = io.Copy(io.Discard, resp.Body) // drain to EOF so the TCP conn can be reused (keep-alive)
```
- Reuse one `*http.Client` (and its `Transport`) across requests — it pools connections and is goroutine-safe.
- For fine control, set a custom `http.Transport` (e.g. `MaxIdleConnsPerHost`, `TLSHandshakeTimeout`) once and share it.

DON'T:
- Don't `http.Get(url)` in production code — no timeout.
- Don't forget `resp.Body.Close()` — leaks connections/goroutines. `err == nil` guarantees a non-nil Body you must close.
- Don't create a fresh `http.Client`/`Transport` per request — defeats connection pooling and can exhaust FDs.
- Don't rely on `Timeout` alone for streaming; it interrupts body reads too. Use a `context` deadline for finer scope.

### File serving

`ServeFileFS`, `FileServerFS`, `NewFileTransportFS` (Go 1.22) serve from an `fs.FS` (e.g. `embed.FS`).
Pre-1.22: `http.FileServer(http.FS(fsys))` or `http.Dir`.

### Go version cheat-sheet (verify before use)

- 1.13 — `errors.Is/As`, `%w`, `http.NewRequestWithContext`. 1.16 — `signal.NotifyContext`, `embed`/`io/fs`, `http.FS`. 1.18 — generics, workspaces, fuzzing. 1.20 — `errors.Join`. 1.21 — `min`/`max`/`clear`, `log/slog` (no range-over-int yet).
- **1.22 — ServeMux method + `{wildcard}` routing, `r.PathValue`/`SetPathValue`, per-iteration loop variables, `for range int`, `math/rand/v2`, `ServeFileFS`.**
- 1.23 — range-over-func iterators, `unique`. 1.24 — generic type aliases.

Trap: the loop-variable per-iteration change and the net/http routing change **both landed in 1.22** — never attribute either to an earlier version.

### Sources

- https://go.dev/blog/routing-enhancements
- https://go.dev/doc/go1.22
- https://pkg.go.dev/net/http
- https://go.dev/doc/devel/release

## Testing <a id="testing"></a>

Stdlib-first testing lore. Current stable: **Go 1.26** (Feb 2026). Verify `go.mod`'s `go` directive — some behaviors (loop-var scope) key off the declared version, not the toolchain.

Files end in `_test.go`. `func TestXxx(t *testing.T)`, `func BenchmarkXxx(b *testing.B)`, `func FuzzXxx(f *testing.F)`, `func ExampleXxx()`. Run: `go test ./...`.

### Table-driven tests

DO structure cases as a slice of structs; it's the idiomatic default.

```go
func TestAbs(t *testing.T) {
    tests := []struct {
        name string
        in   int
        want int
    }{
        {"neg", -3, 3},
        {"zero", 0, 0},
        {"pos", 5, 5},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if got := Abs(tt.in); got != tt.want {
                t.Errorf("Abs(%d) = %d, want %d", tt.in, got, tt.want)
            }
        })
    }
}
```

- DO wrap each case in `t.Run(tt.name, ...)` (subtests, since **1.7**) — isolates failures, enables `-run 'TestAbs/neg'`.
- DON'T write a bare loop with no subtest; one failure obscures the case that broke.

### t.Run subtests

- Subtest names join with `/`: `TestAbs/neg`. Slashes/spaces in names get sanitized.
- Filter: `go test -run 'TestAbs/pos'`. Trailing `/` matters: `-run Foo/A=`.
- `t.Run` runs `f` in a new goroutine and blocks until it returns (or calls `t.Parallel`).

### Errorf vs Fatalf

- `Errorf` = `Logf` + `Fail`: marks failed, **keeps going**. Default for independent assertions.
- `Fatalf` = `Logf` + `FailNow`: marks failed, **stops this test/subtest now** (via `runtime.Goexit`). Use when continuing would panic (nil deref) or is meaningless.
- DON'T call `Fatal*`/`FailNow` from a spawned goroutine — only from the goroutine running the test. Use `Error*` + `return`, or a channel, in goroutines.
- DO mark helpers with `t.Helper()` (**1.9**) so failure line points at the caller.

### t.Cleanup (1.14)

- `t.Cleanup(fn)` runs when the test **and all its subtests** finish. LIFO order.
- DO prefer `t.Cleanup` over `defer` for setup helpers — cleanup registered inside a helper still runs at test end, and composes across subtests.
- DON'T leak: register teardown next to setup. `t.TempDir()` auto-cleans; `t.Setenv` (**1.17**) auto-restores.

### t.Parallel

```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        // ... uses tt ...
    })
}
```

- `t.Parallel()` pauses the subtest until its serial siblings finish, then runs paused ones together. Cap via `-parallel N` (default `GOMAXPROCS`).
- **1.22 trap:** loop variables became per-iteration in **1.22**. In modules declaring `go 1.22`+, capturing `tt` in a parallel closure is safe. In `go 1.21` or earlier `go.mod`, you MUST shadow: `tt := tt`. Check the `go.mod` directive, not the toolchain. `go vet`'s `loopclosure` flags the old bug.
- DON'T share mutable state across parallel tests (shared maps, global mutation, same temp file). Each parallel test gets its own `tt`, `t.TempDir()`, `t.Context()`.
- DON'T use `t.Setenv`/`t.Chdir` in a parallel test (or one with parallel ancestors) — they panic; env/cwd is process-global.

### testify (optional, not stdlib)

Only if already a dependency (`github.com/stretchr/testify`). DON'T add it just to test.

- `assert.Equal(t, want, got)` — logs + continues (like `Errorf`).
- `require.Equal(t, want, got)` — stops on failure (like `Fatalf`); use for preconditions.
- DON'T call `require` from a goroutine (it calls `FailNow`).

### Benchmarks (testing.B)

Modern (**1.24**): `for b.Loop()` — setup before the loop is excluded, keeps results alive (defeats dead-code elimination), reports iterations in `b.N` after.

```go
func BenchmarkEncode(b *testing.B) {
    data := makeInput() // excluded from timing
    for b.Loop() {
        _ = Encode(data)
    }
}
```

Older / pre-1.24: classic `b.N` loop with manual `b.ResetTimer()`.

```go
func BenchmarkEncode(b *testing.B) {
    data := makeInput()
    b.ResetTimer() // exclude setup
    for range b.N { // for-range-over-int since 1.22; else i := 0; i < b.N; i++
        _ = Encode(data)
    }
}
```

- DON'T mix `b.Loop()` and a `b.N` loop. Condition must be literally `for b.Loop()`.
- `b.ResetTimer` zeros elapsed time + alloc counters; `b.StopTimer`/`b.StartTimer` bracket per-iteration setup you can't hoist.
- Run: `go test -bench=. -benchmem`. Report allocs with `b.ReportAllocs()` or `-benchmem`.

### Fuzzing (1.18)

```go
func FuzzReverse(f *testing.F) {
    f.Add("Hello, world") // seed corpus; type must match Fuzz arg
    f.Fuzz(func(t *testing.T, s string) {
        rev := Reverse(s)
        if Reverse(rev) != s {
            t.Errorf("round-trip failed: %q", s)
        }
    })
}
```

- `f.Fuzz` target: first arg `*testing.T`, then fuzzed args. Supported types only: `[]byte, string, bool, byte/rune, int*, uint*, float32/64`. No structs/slices-of-struct.
- Inside the target use `*testing.T` methods; DON'T call `*F` methods there (except `Failed`/`Name`).
- DO assert **properties/invariants** (round-trip, no panic, valid UTF-8), not exact outputs.
- Seed + regression corpus lives in `testdata/fuzz/FuzzReverse/`; failing inputs are written there and re-run by plain `go test` (no `-fuzz`). Commit them.
- Actively fuzz: `go test -fuzz=FuzzReverse -fuzztime=30s`. Runs until failure/ctrl-C otherwise.

### httptest

Handler unit test — no socket:

```go
req := httptest.NewRequest("GET", "/foo", nil)
rr := httptest.NewRecorder()
Handler(rr, req)
res := rr.Result() // call after handler returns
if res.StatusCode != http.StatusOK {
    t.Fatalf("status = %d", res.StatusCode)
}
```

Integration test over a real loopback listener:

```go
ts := httptest.NewServer(http.HandlerFunc(Handler))
defer ts.Close()
res, err := ts.Client().Get(ts.URL + "/foo") // Client() trusts TLS test cert
```

- `NewRecorder()` → `ResponseRecorder{Code, Body *bytes.Buffer}`; read via `rr.Result()` (don't touch deprecated `HeaderMap`).
- `NewTLSServer` + `ts.Client()` for HTTPS. DON'T use `http.DefaultClient` against a TLS test server — cert won't verify.
- **1.22 routing trap:** `ServeMux` gained method + wildcard patterns (`"GET /items/{id}"`, `r.PathValue("id")`) in **1.22**, active only under `go 1.22`+. Don't assume it on older modules.

### Golden files

```go
var update = flag.Bool("update", false, "update golden files")

got := Render(input)
golden := filepath.Join("testdata", t.Name()+".golden")
if *update {
    os.WriteFile(golden, got, 0o644)
}
want, _ := os.ReadFile(golden)
if !bytes.Equal(got, want) {
    t.Errorf("mismatch; run go test -update")
}
```

- DO keep fixtures under `testdata/` (the `go` tool ignores it). Regenerate with `-update`.
- DO review golden diffs — a wrong golden silently locks in a bug.

### Flags & CI

- `go test -race` — race detector; run in CI. Catches shared-state bugs parallel tests expose.
- `go test -cover` / `-coverprofile=c.out` then `go tool cover -html=c.out`.
- `go test -count=1` defeats the test cache; `-v` verbose; `-run`/`-bench`/`-fuzz` select.
- `TestMain(m *testing.M)` (**1.4**) for process-wide setup; call `flag.Parse()` if needed, then `os.Exit(m.Run())`.

### DON'T

- DON'T over-test unexported internals — test behavior via the exported API; prefer an external `xxx_test` package.
- DON'T share state across parallel tests or rely on execution order.
- DON'T sync via `time.Sleep`/wall-clock; inject a clock or use channels/`t.Context()` (**1.24**).
- DON'T ignore `go vet` — it runs before `go test` and catches `Printf`-family and `loopclosure` mistakes.

### Sources

- https://pkg.go.dev/testing
- https://go.dev/doc/tutorial/fuzz
- https://go.dev/security/fuzz/
- https://pkg.go.dev/net/http/httptest
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release

## Modules & tooling <a id="modules-and-tooling"></a>

Current stable: Go 1.26 line (1.25 also supported). Verify features against release notes; never claim a feature earlier than reality. The **1.22 loop-var change** and **1.22 net/http routing** are the classic traps.

### go.mod / go.sum — DO

- DO run `go mod init <module-path>` once; commit **both** `go.mod` and `go.sum`.
- DO keep the `go` directive at the **minimum** version your code needs (it sets the language version the compiler enforces and the floor for consumers). Example: `go 1.24`.
- DO understand `go.sum` = content checksums (integrity, not a lockfile). Minimal Version Selection (MVS) picks the lowest version satisfying all requirements — reproducible without a lockfile.
- DO set `GOTOOLCHAIN=auto` (default since **1.21**): the `go` command downloads/uses a newer toolchain when `go`/`toolchain` lines require it. Pin with `toolchain go1.26.0` for reproducibility; force with `GOTOOLCHAIN=local`.

```
module example.com/svc
go 1.24
require (
    golang.org/x/text v0.14.0
    example.com/lib/v2 v2.3.4   // v2+ needs the /v2 path suffix
)
```

### go.mod / go.sum — DON'T

- DON'T commit without `go mod tidy` — the #1 reviewer catch. It adds missing and removes unused requires and prunes `go.sum`.
- DON'T hand-edit `go.sum`. DON'T bump the `go` line just to use a tool; it forces the floor on every consumer.
- DON'T set `GOSUMDB=off` casually — toolchain downloads are verified against the checksum DB and will fail without it.

### Dependencies — DO

- DO use the version query suffix: `go get pkg@v1.3.4`, `@latest`, `@master`, `@<commit>`, `@patch`, `@none` (remove).
- DO `go get -u ./...` to upgrade minor/patch of imports; `go get -u=patch ./...` for patch-only.
- DO `go list -m -u all` to discover available updates.
- DO `go mod download` only to pre-fill the cache (CI, proxy). Plain `go build`/`go test` fetch as needed.

### Semantic import versioning — DO / DON'T

- v0/v1: no suffix. **v2+**: the module path **must** carry the major suffix (`/v2`, `/v3`) — this is a distinct import path so multiple majors coexist (diamond deps). Introduced with modules.
- DO bump the path in `go.mod` (`module example.com/lib/v2`) and in every internal import when releasing v2.
- DON'T expect `go get pkg@v2.0.0` to work against a module that didn't add `/v2` — you'll get `+incompatible` fallback only for pre-modules tags.

### Workspaces (go.work) — 1.18 — DO

- DO use `go work` for **multi-module local dev** (edit several modules together without `replace` churn).

```
go work init ./svc ./lib
go work use ./newmod        # add; -r recurses
go work sync                # push workspace build list into member go.mods
```

- DON'T commit `go.work`/`go.work.sum` to a library repo — it's a local-dev convenience; CI should build modules standalone. Check mode with `go env GOWORK`.

### replace / exclude — DO / DON'T

- `replace` and `exclude` apply **only in the main module** — ignored when your module is a dependency.
- DO use `replace ... => ./local/path` (version omitted for local) for a temporary fork or local dep. A `replace` still needs a matching `require`.

```
replace example.com/lib => ../lib                 # local
replace example.com/lib v1.2.3 => example.com/fork/lib v1.2.4
```

- DON'T ship a library that relies on `replace` to build — consumers won't inherit it. Prefer `go.work` locally, real releases for consumers.

### Build tags (//go:build) — 1.17 — DO

- DO use the modern `//go:build linux && amd64` expression form. Put it at the top, followed by a blank line, before `package`.
- DON'T use the legacy `// +build` form in new code (`gofmt` still syncs it if present). Only **one** `//go:build` line is allowed per file.
- Filename constraints are implicit: `foo_linux.go`, `bar_windows_amd64.go`, `x_test.go`. `unix` is a valid tag; per-release tags exist (`go1.24`) but not for minor/beta.

### Formatting & vetting — DO

- DO run `gofmt` (or `go fmt ./...`) — non-negotiable, no config. `goimports` (`golang.org/x/tools/cmd/goimports`) additionally manages import grouping/removal.
- DO run `go vet ./...`. `go test` already runs a high-confidence vet subset (printf, atomic, etc.); disable with `-vet=off`.
- `go vet -vettool=$(which shadow)` adds extra analyzers built on `golang.org/x/tools/go/analysis`.

### Linters — DO

- DO adopt **golangci-lint** (v2) as the aggregator — runs 100+ linters in parallel with caching. Standard default set includes `govet`, `staticcheck`, `errcheck`, `ineffassign`, `unused`. **staticcheck is bundled** — don't also run it standalone under CI.
- v2 config requires an explicit version field:

```yaml
# .golangci.yml  (.yaml/.toml/.json also accepted)
version: "2"
linters:
  default: standard
  enable: [revive, gosec]
```

- Run: `golangci-lint run` (or `./...`). Install via the official script/binary, not `go install` from a floating tag.
- DON'T enable every linter — curate; noisy configs get ignored.

### go generate — DO

- DO put `//go:generate <cmd>` directives in source (no space after `//`); they run **only** on explicit `go generate ./...`, never during build/test.
- DO commit generated files and mark them `// Code generated ... DO NOT EDIT.`.

### Tool dependencies — version-adaptive

**Go 1.24+ (preferred):** track tools in `go.mod` via the `tool` directive.

```
go get -tool golang.org/x/tools/cmd/stringer   # adds tool + require
go tool stringer                                # run (pinned version)
go tool                                         # list
go install tool                                 # install all to GOBIN
```

`go mod tidy` maintains the `require`s; `go get tool` upgrades all tools.

**Before 1.24 (fallback):** the `tools.go` pattern — a build-constrained file with blank imports so tools are tracked deps, run via `go run`.

```go
//go:build tools
package tools
import _ "golang.org/x/tools/cmd/stringer"
```
```
go run golang.org/x/tools/cmd/stringer
```

- DON'T rely on developers' globally-installed tool versions — pin via `tool` directive or `tools.go` for reproducibility.

### Vendoring — DON'T (usually)

- DON'T `go mod vendor` unless you need airgapped/hermetic builds or a policy requires it — the module cache + proxy already give reproducibility.
- If a `vendor/` exists and `go >= 1.14`, builds auto-use it (`-mod=vendor`) with **no** network access. Then you **must** re-run `go mod vendor` after any dependency change, or builds fail. Override with `-mod=mod`.

### Language-feature version map (verify before use)

- 1.13: `errors.Is`/`As`, `%w` wrapping
- 1.16: modules on by default, `//go:embed`
- 1.18: generics, workspaces, native fuzzing
- 1.19: `GOMEMLIMIT` (soft memory limit)
- 1.20: `errors.Join`
- 1.21: `min`/`max`/`clear` builtins, `log/slog`, toolchain management. **No** for-range-over-int yet.
- 1.22: **per-iteration loop variables** (gated on `go 1.22` in go.mod), for-range-over-int (`for i := range n`), `net/http` ServeMux method+wildcard routing (`GET /items/{id}`), `math/rand/v2`
- 1.23: range-over-func iterators (`iter`), `unique`
- 1.24: generic type aliases, `tool` directive / `go get -tool`

### Sources

- https://go.dev/ref/mod
- https://go.dev/doc/modules/managing-dependencies
- https://go.dev/doc/toolchain
- https://pkg.go.dev/cmd/go
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release
- https://go.dev/dl/
- https://golangci-lint.run/
- https://golangci-lint.run/docs/configuration/file/
- https://staticcheck.dev/docs/getting-started/

## Performance <a id="performance"></a>

Senior-reviewer checklist. Measure first; the compiler and GC are good. Current stable: Go **1.26** (2026-02-10). Verify version-gated facts against `go.mod`'s declared version.

### DON'T optimize blind

- DON'T micro-optimize without a benchmark. Guesses about hot paths are usually wrong — profile.
- DON'T prematurely add goroutines. Concurrency adds scheduling + sync cost and rarely speeds CPU-bound serial work. Add it for I/O overlap or genuinely parallel CPU work, then measure.
- DON'T assume; confirm with `pprof` + `benchstat` (`golang.org/x/perf/cmd/benchstat`) on repeated runs.

### DO profile first

Profile types (`runtime/pprof`): `cpu` (via Start/StopCPUProfile — NOT a `Profile` object), `heap` (in-use, default `-inuse_space`), `allocs` (all past allocs), `goroutine`, `block` (off by default; enable `runtime.SetBlockProfileRate`), `mutex` (off; `runtime.SetMutexProfileFraction`), `threadcreate`.

DO profile via benchmarks — cleanest signal:
```sh
go test -bench=. -benchmem -cpuprofile=cpu.prof -memprofile=mem.prof
go tool pprof cpu.prof      # top, list <fn>, web, weblist
```

DO expose live profiles in long-running servers (blank import registers `/debug/pprof/` on the default mux):
```go
import _ "net/http/pprof"
// go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
```
DON'T register `net/http/pprof` on a public mux — it leaks internals. Use a private mux/port.

DO profile programmatically when needed:
```go
pprof.StartCPUProfile(f); defer pprof.StopCPUProfile()  // CPU
runtime.GC(); pprof.Lookup("allocs").WriteTo(f, 0)      // heap: force GC first
```
DON'T mix profilers — precise memory profiling skews CPU profiles; collect one at a time.

DO use the execution tracer for latency/scheduling/GC-timing questions (not hot spots): `go test -trace=t.out` or `runtime/trace`, then `go tool trace t.out`.

### DO benchmark correctly

DO prefer `b.Loop()` (Go **1.24+**) — auto-resets timer after setup, stops after, runs the body once per measurement, and keeps loop-body values alive against dead-code elimination:
```go
func BenchmarkX(b *testing.B) {
    big := setup()          // not timed
    b.ReportAllocs()
    for b.Loop() { use(big) } // only this measured
}
```
- The condition must be written exactly `b.Loop()`; don't also loop to `b.N`.
- Older fallback (pre-1.24): `for range b.N { ... }` with a manual `b.ResetTimer()` after setup, and assign results to a package-level sink to defeat the optimizer.
- DON'T trust a single run — compare with `benchstat`. Use `testing.AllocsPerRun(n, f)` for a quick alloc count.

### DO cut allocations (usually the biggest win)

DO read escape analysis to see what lands on the heap:
```sh
go build -gcflags=-m ./...        # -m -m for more detail
```
DON'T fight it blindly — heap allocation is only a problem when a benchmark says so.

- DO preallocate slices/maps with capacity: `make([]T, 0, n)` / `make(map[K]V, n)`. Growth reallocates and copies.
- DO reuse buffers across calls (`buf = buf[:0]`) instead of allocating per iteration.
- DON'T return pointers/interfaces that force a value to escape when a value return keeps it on the stack.
- DO pass large structs by pointer to avoid copies — but note taking `&x` can cause `x` to escape. Trade-off; measure.

### DO use sync.Pool for churny, short-lived objects

`sync.Pool` (Go 1.3) caches temporary objects to relieve GC pressure; safe for concurrent use.
```go
var bufPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}
b := bufPool.Get().(*bytes.Buffer)
b.Reset()                 // always reset — Get returns arbitrary prior state
defer bufPool.Put(b)
```
- DO have `New` return a **pointer** type (no boxing alloc on the interface return).
- DON'T assume anything you `Put` survives — items may be GC'd at any time without notice.
- DON'T use it as a general object cache or for long-lived objects; it's for high-churn temporaries (see `fmt`'s buffer pool). A must-not-copy-after-use type.

### DO mind interfaces and conversions

- DON'T box hot values into `interface{}`/`any` in tight loops — assigning a non-pointer to an interface can allocate. Generics (Go **1.18**) often avoid the boxing entirely.
- DON'T convert `string`↔`[]byte` in hot paths; each conversion copies. Work in one representation. Comparisons/map lookups keyed by a `string(b)` are optimized by the compiler in common cases, but don't rely on it — benchmark.
- DO prefer `strings.Builder` / `bytes.Buffer` over `+=` concatenation in loops.

### DO tune the GC (only with data)

Knobs (`runtime/debug` mirrors the env vars):
- `GOGC` / `debug.SetGCPercent` — heap growth before next GC; default `100`. Doubling GOGC ≈ halves GC CPU and doubles heap footprint. `GOGC=off` / `SetGCPercent(-1)` disables GC (memory limit still applies).
- `GOMEMLIMIT` / `debug.SetMemoryLimit` (Go **1.19**) — **soft** total-memory cap. Counts `Sys - HeapReleased`.

DO combine for containers: set `GOMEMLIMIT` to ~90–95% of the container limit (leave 5–10% headroom) and raise or disable `GOGC` — heap floats up to the limit and GC runs at minimum frequency.
DON'T set `GOMEMLIMIT` in environments you don't control or where usage scales with input (CLIs, desktop apps) — under pressure the soft limit thrashes (GC capped ~50% CPU) instead of OOMing cleanly.
DO inspect with `GODEBUG=gctrace=1` before turning knobs.

### Version traps — verify against go.mod

- **Go 1.22** loop variables are **per-iteration**, not per-loop. The old `x := x` capture workaround is unneeded when `go.mod` declares `go 1.22`+; pre-1.22 code keeps the shared-variable footgun (closures/goroutines see the final value).
- **Go 1.22**: `net/http.ServeMux` gained method + wildcard patterns (`"GET /items/{id}"`); `math/rand/v2` (faster, better API — don't seed the global for perf myths); `for range <int>`.
- Modern stdlib worth preferring: `min`/`max`/`clear` builtins + `log/slog` (1.21); `errors.Join` (1.20), `%w`/`errors.Is`/`As` (1.13); range-over-func iterators + `unique` (1.23); generic type aliases (1.24).
- GOGC accounts for the root set (stacks + globals) since Go **1.18** — matters for programs with many goroutines.

### Sources

- https://go.dev/doc/diagnostics
- https://pkg.go.dev/runtime/pprof
- https://go.dev/doc/gc-guide
- https://pkg.go.dev/sync#Pool
- https://pkg.go.dev/testing
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release

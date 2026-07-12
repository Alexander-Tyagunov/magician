# Go — Performance

Senior-reviewer checklist. Measure first; the compiler and GC are good. Current stable: Go **1.26** (2026-02-10). Verify version-gated facts against `go.mod`'s declared version.

## DON'T optimize blind

- DON'T micro-optimize without a benchmark. Guesses about hot paths are usually wrong — profile.
- DON'T prematurely add goroutines. Concurrency adds scheduling + sync cost and rarely speeds CPU-bound serial work. Add it for I/O overlap or genuinely parallel CPU work, then measure.
- DON'T assume; confirm with `pprof` + `benchstat` (`golang.org/x/perf/cmd/benchstat`) on repeated runs.

## DO profile first

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

## DO benchmark correctly

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

## DO cut allocations (usually the biggest win)

DO read escape analysis to see what lands on the heap:
```sh
go build -gcflags=-m ./...        # -m -m for more detail
```
DON'T fight it blindly — heap allocation is only a problem when a benchmark says so.

- DO preallocate slices/maps with capacity: `make([]T, 0, n)` / `make(map[K]V, n)`. Growth reallocates and copies.
- DO reuse buffers across calls (`buf = buf[:0]`) instead of allocating per iteration.
- DON'T return pointers/interfaces that force a value to escape when a value return keeps it on the stack.
- DO pass large structs by pointer to avoid copies — but note taking `&x` can cause `x` to escape. Trade-off; measure.

## DO use sync.Pool for churny, short-lived objects

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

## DO mind interfaces and conversions

- DON'T box hot values into `interface{}`/`any` in tight loops — assigning a non-pointer to an interface can allocate. Generics (Go **1.18**) often avoid the boxing entirely.
- DON'T convert `string`↔`[]byte` in hot paths; each conversion copies. Work in one representation. Comparisons/map lookups keyed by a `string(b)` are optimized by the compiler in common cases, but don't rely on it — benchmark.
- DO prefer `strings.Builder` / `bytes.Buffer` over `+=` concatenation in loops.

## DO tune the GC (only with data)

Knobs (`runtime/debug` mirrors the env vars):
- `GOGC` / `debug.SetGCPercent` — heap growth before next GC; default `100`. Doubling GOGC ≈ halves GC CPU and doubles heap footprint. `GOGC=off` / `SetGCPercent(-1)` disables GC (memory limit still applies).
- `GOMEMLIMIT` / `debug.SetMemoryLimit` (Go **1.19**) — **soft** total-memory cap. Counts `Sys - HeapReleased`.

DO combine for containers: set `GOMEMLIMIT` to ~90–95% of the container limit (leave 5–10% headroom) and raise or disable `GOGC` — heap floats up to the limit and GC runs at minimum frequency.
DON'T set `GOMEMLIMIT` in environments you don't control or where usage scales with input (CLIs, desktop apps) — under pressure the soft limit thrashes (GC capped ~50% CPU) instead of OOMing cleanly.
DO inspect with `GODEBUG=gctrace=1` before turning knobs.

## Version traps — verify against go.mod

- **Go 1.22** loop variables are **per-iteration**, not per-loop. The old `x := x` capture workaround is unneeded when `go.mod` declares `go 1.22`+; pre-1.22 code keeps the shared-variable footgun (closures/goroutines see the final value).
- **Go 1.22**: `net/http.ServeMux` gained method + wildcard patterns (`"GET /items/{id}"`); `math/rand/v2` (faster, better API — don't seed the global for perf myths); `for range <int>`.
- Modern stdlib worth preferring: `min`/`max`/`clear` builtins + `log/slog` (1.21); `errors.Join` (1.20), `%w`/`errors.Is`/`As` (1.13); range-over-func iterators + `unique` (1.23); generic type aliases (1.24).
- GOGC accounts for the root set (stacks + globals) since Go **1.18** — matters for programs with many goroutines.

## Sources

- https://go.dev/doc/diagnostics
- https://pkg.go.dev/runtime/pprof
- https://go.dev/doc/gc-guide
- https://pkg.go.dev/sync#Pool
- https://pkg.go.dev/testing
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release

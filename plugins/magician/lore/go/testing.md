# Go — Testing

Stdlib-first testing lore. Current stable: **Go 1.26** (Feb 2026). Verify `go.mod`'s `go` directive — some behaviors (loop-var scope) key off the declared version, not the toolchain.

Files end in `_test.go`. `func TestXxx(t *testing.T)`, `func BenchmarkXxx(b *testing.B)`, `func FuzzXxx(f *testing.F)`, `func ExampleXxx()`. Run: `go test ./...`.

## Table-driven tests

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

## t.Run subtests

- Subtest names join with `/`: `TestAbs/neg`. Slashes/spaces in names get sanitized.
- Filter: `go test -run 'TestAbs/pos'`. Trailing `/` matters: `-run Foo/A=`.
- `t.Run` runs `f` in a new goroutine and blocks until it returns (or calls `t.Parallel`).

## Errorf vs Fatalf

- `Errorf` = `Logf` + `Fail`: marks failed, **keeps going**. Default for independent assertions.
- `Fatalf` = `Logf` + `FailNow`: marks failed, **stops this test/subtest now** (via `runtime.Goexit`). Use when continuing would panic (nil deref) or is meaningless.
- DON'T call `Fatal*`/`FailNow` from a spawned goroutine — only from the goroutine running the test. Use `Error*` + `return`, or a channel, in goroutines.
- DO mark helpers with `t.Helper()` (**1.9**) so failure line points at the caller.

## t.Cleanup (1.14)

- `t.Cleanup(fn)` runs when the test **and all its subtests** finish. LIFO order.
- DO prefer `t.Cleanup` over `defer` for setup helpers — cleanup registered inside a helper still runs at test end, and composes across subtests.
- DON'T leak: register teardown next to setup. `t.TempDir()` auto-cleans; `t.Setenv` (**1.17**) auto-restores.

## t.Parallel

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

## testify (optional, not stdlib)

Only if already a dependency (`github.com/stretchr/testify`). DON'T add it just to test.

- `assert.Equal(t, want, got)` — logs + continues (like `Errorf`).
- `require.Equal(t, want, got)` — stops on failure (like `Fatalf`); use for preconditions.
- DON'T call `require` from a goroutine (it calls `FailNow`).

## Benchmarks (testing.B)

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

## Fuzzing (1.18)

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

## httptest

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

## Golden files

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

## Flags & CI

- `go test -race` — race detector; run in CI. Catches shared-state bugs parallel tests expose.
- `go test -cover` / `-coverprofile=c.out` then `go tool cover -html=c.out`.
- `go test -count=1` defeats the test cache; `-v` verbose; `-run`/`-bench`/`-fuzz` select.
- `TestMain(m *testing.M)` (**1.4**) for process-wide setup; call `flag.Parse()` if needed, then `os.Exit(m.Run())`.

## DON'T

- DON'T over-test unexported internals — test behavior via the exported API; prefer an external `xxx_test` package.
- DON'T share state across parallel tests or rely on execution order.
- DON'T sync via `time.Sleep`/wall-clock; inject a clock or use channels/`t.Context()` (**1.24**).
- DON'T ignore `go vet` — it runs before `go test` and catches `Printf`-family and `loopclosure` mistakes.

## Sources

- https://pkg.go.dev/testing
- https://go.dev/doc/tutorial/fuzz
- https://go.dev/security/fuzz/
- https://pkg.go.dev/net/http/httptest
- https://go.dev/blog/loopvar-preview
- https://go.dev/doc/devel/release

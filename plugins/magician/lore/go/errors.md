# Go — Errors

Errors are values. `error` is an interface (`Error() string`). Program with them; don't reflexively `if err != nil { return err }`. Current stable: Go 1.26 (1.26.0 2026-02-10). Supported line: 1.26 + 1.25. Feature versions are marked below — never claim one earlier than reality.

## DO — return & wrap

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

## DON'T — the traps

- DON'T discard with `_`. `_, _ = w.Write(b)` hides real failures. If you truly must ignore, comment why.
- DON'T compare error strings: `err.Error() == "not found"` is brittle and breaks on wrap. Use `errors.Is`/`errors.As`.
- DON'T compare a wrapped error with `==`. `err == ErrNotFound` fails once wrapped; use `errors.Is`.
- DON'T `%w` a value the caller must never couple to (e.g. leaking `*os.PathError` or `sql.ErrNoRows` from an internal DB). That's a permanent API promise.
- DON'T panic for ordinary/expected failures (see panic section).

## Inspecting the chain

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

## Sentinel vs typed

- **Sentinel** — a package-level `var ErrX = errors.New("...")` for a condition with no payload. Match with `errors.Is`. `errors.New` returns a distinct value per call, so callers MUST reference your exported var, not their own `New` with the same text.
- **Typed** — a struct implementing `error` when callers need fields. Match and extract with `errors.As`.
  ```go
  type QueryError struct { Query string; Err error }
  func (e *QueryError) Error() string { return e.Query + ": " + e.Err.Error() }
  func (e *QueryError) Unwrap() error { return e.Err } // makes Err visible to Is/As
  ```
- Prefer sentinel when callers only branch; typed when they need data.

## errors.Join (Go 1.20) — multiple errors

`errors.Join(errs ...error) error` wraps several errors. Nil args are dropped; all-nil ⇒ nil. Message is newline-joined. The result implements `Unwrap() []error`; inspect with `Is`/`As` (NOT `errors.Unwrap`).
```go
var errs error
for _, x := range xs {
    if err := do(x); err != nil { errs = errors.Join(errs, err) }
}
return errs // nil if every do() succeeded
```
Pre-1.20 fallback: accumulate into a slice/`[]error` and build a custom error type, or use a third-party multierror.

## Errors-are-values patterns

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

## panic / recover

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

## Version cheat-sheet (verified)

- 1.13 — `errors.Is`, `errors.As`, `errors.Unwrap`, `%w` in `fmt.Errorf`.
- 1.20 — `errors.Join`, `Unwrap() []error` multi-error tree.
- 1.26 — `errors.AsType[E]` generic accessor (current stable line).
- Unrelated traps to keep straight: per-iteration loop variables + `net/http.ServeMux` method/wildcard routing + `math/rand/v2` all landed in **1.22** (not earlier); range-over-func iterators + `unique` in 1.23; generic type aliases in 1.24.

## Sources

- https://go.dev/blog/go1.13-errors
- https://pkg.go.dev/errors
- https://go.dev/blog/errors-are-values
- https://go.dev/doc/effective_go
- https://go.dev/doc/go1.22
- https://go.dev/doc/devel/release

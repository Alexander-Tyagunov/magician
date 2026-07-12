# Go — Language & idioms

Senior-reviewer checklist for writing idiomatic Go. Verify the module's `go` directive in `go.mod` before assuming a feature exists — language behavior is gated per-module. Current stable is Go 1.26 (2026-02); supported: 1.26, 1.25, 1.24.

## Structs & methods

- DO put behavior on the type via methods; choose the receiver deliberately.
- DO use a pointer receiver `(t *T)` when the method mutates, when `T` is large, or for consistency once any method needs a pointer. Use a value receiver for small immutable types.
- DON'T mix value and pointer receivers on the same type. If one method needs `*T`, give them all `*T`.
- DO remember: a method set of `T` has value-receiver methods; the method set of `*T` has both. An interface value holding a `T` (not `*T`) can't call pointer methods.

## Interfaces

- DO keep interfaces small — one or two methods. Name single-method ones with `-er` (`Reader`, `Writer`, `Stringer`).
- DO **accept interfaces, return concrete types**. Let callers narrow; give them the full type back.
- DO define the interface in the *consumer* package, not the producer. Satisfaction is implicit — no `implements`.
- DON'T add methods to an interface speculatively. Widen only when a real second implementation appears.
- DO use `any` (Go 1.18 alias for `interface{}`) in new code.

```go
func Save(w io.Writer, data []byte) error   // accept interface
func New() *Client                            // return concrete
```

## Embedding (composition, not inheritance)

- DO embed a type (named without a field name) to promote its methods/fields. This is composition, not subclassing.
- DON'T expect dynamic dispatch to the outer type: a promoted method's receiver is the **inner** type. The outer type does not override the inner's calls.
- DO resolve name conflicts explicitly — a shallower name shadows a deeper one; two at the same depth are an error only if referenced.

```go
type Server struct {
    *log.Logger   // promotes Printf, etc.; refer to it as s.Logger
}
```

## Zero values are useful

- DO make the zero value usable so `var x T` works without a constructor. `sync.Mutex`, `bytes.Buffer`, `strings.Builder` all do this.
- DON'T write a `New()` that only sets fields to their zero values.
- DO note map zero value is `nil` (reads OK, **writes panic**) and slice zero value is `nil` (append works).

## Slices vs arrays

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

## Maps

- DON'T assume order — map iteration order is randomized. Sort keys for determinism.
- DO use comma-ok to distinguish "absent" from "zero value": `v, ok := m[k]`.
- `delete(m, k)` is safe on a missing key; `clear(m)` (Go 1.21) removes all entries.
- DON'T take the address of a map element (`&m[k]` is illegal) or write to a nil map.

## defer

- DO use `defer` for cleanup next to acquisition (`f.Close()` after `Open`). Deferred calls run LIFO.
- DO note arguments are **evaluated when `defer` executes**, not when the call runs.

```go
defer fmt.Println(i)     // captures i's value NOW
defer func() { fmt.Println(i) }()  // reads i at return time
```

- DON'T `defer` inside a loop expecting per-iteration release — deferreds fire at function return. Wrap the body in a closure or call directly.
- DO use a deferred closure with named results to alter the return value or recover.

## iota

- DO use `iota` for enumerations; it resets to 0 per `const` block and increments per line. Expressions repeat implicitly.

```go
type Level int
const (
    Debug Level = iota   // 0
    Info                 // 1
    Warn                 // 2
)
```

## Generics (Go 1.18)

- DO use type parameters when logic is identical across types (containers, `Map`/`Filter`, `slices`/`maps` helpers).
- DON'T reach for generics when an interface suffices, or to over-abstract a single call site. Prefer concrete code.
- DO write constraints as interfaces with type sets; `|` is union, `~T` means "underlying type T" (matches `type MyInt int`).
- `comparable` (built-in) constrains to `==`/`!=` types; `cmp.Ordered` (Go 1.21) covers `<`-comparable types — prefer it over `golang.org/x/exp/constraints`.

```go
func Keys[K comparable, V any](m map[K]V) []K { ... }
type Number interface { ~int | ~float64 }
```

- Generic type aliases are fully supported as of Go 1.24 (permanent in 1.25).

## Iterators: range-over-func (Go 1.23)

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

## Loop variable (Go 1.22) — classic trap

- Since Go 1.22, each iteration gets a **fresh** loop variable (both 3-clause and range). Closures/goroutines capturing it now see the per-iteration value.
- DON'T assume this in modules declaring `go 1.21` or earlier — old shared-variable semantics still apply there. Under old rules, `i := i` shadow copy is required before capturing.

```go
for _, v := range items {
    go func() { use(v) }()   // Go 1.22+: correct; pre-1.22: all see last v
}
```

## Errors

- DON'T ignore returned errors (`v, _ := f()` for anything that can fail). Handle, wrap, or return.
- DO wrap with `%w` (Go 1.13): `fmt.Errorf("read config: %w", err)`; inspect with `errors.Is` (sentinel) / `errors.As` (typed) (Go 1.13).
- DO join multiple errors with `errors.Join(e1, e2)` (Go 1.20); `errors.Is`/`As` traverse joins.
- DON'T `panic` for ordinary failures — return `error`. Reserve panic for programmer bugs / unrecoverable init.

## Naked returns

- DON'T use naked `return` in long or non-trivial functions — it hides which values escape and invites bugs. Return values explicitly.
- DO limit named results + naked return to short functions where they document intent, or where a deferred closure must mutate the result.

## Other version anchors (verify against go.mod)

- `min`/`max`/`clear` builtins, `log/slog`, `slices`, `maps`, `cmp` packages: Go 1.21.
- `for i := range n` (range over int), `net/http.ServeMux` method+wildcard routing (`"POST /items/{id}"`, `r.PathValue("id")`), `math/rand/v2`: Go 1.22.
- `unique` package (canonicalization/interning): Go 1.23.
- `errors.Join`: Go 1.20. `GOMEMLIMIT` soft memory limit: Go 1.19. Workspaces (`go.work`) & native fuzzing: Go 1.18.

## Sources

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

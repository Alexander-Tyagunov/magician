# Go — net/http & servers

Lore for writing correct HTTP code with the standard library. Version-adaptive: the
**Go 1.22** `net/http` routing overhaul is the pivotal fact — pre-1.22 you needed a 3rd-party
router for method + wildcard matching. Current stable: **Go 1.26 line** (1.25 also supported).
Verify a feature's version before relying on it.

## Routing — ServeMux (the 1.22 pivot)

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

## Handlers & middleware

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

## Context on the request

DO:
- Read the per-request deadline/cancellation via `r.Context()`; it's canceled when the client disconnects or the server times out. Thread it into DB/RPC calls.
- Build outbound requests with `http.NewRequestWithContext(ctx, method, url, body)` (Go 1.13+) so cancellation propagates.
- Attach request-scoped values by wrapping: `r = r.WithContext(context.WithValue(r.Context(), key, val))` in middleware.

DON'T:
- Don't use `http.NewRequest` without a context in production paths — you lose cancellation.
- Don't stash a request-scoped `context.Context` in a struct field; pass it as the first arg.

## Server timeouts — ALWAYS set them

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

## Graceful shutdown

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

## HTTP client — never the zero-value default in prod

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

## File serving

`ServeFileFS`, `FileServerFS`, `NewFileTransportFS` (Go 1.22) serve from an `fs.FS` (e.g. `embed.FS`).
Pre-1.22: `http.FileServer(http.FS(fsys))` or `http.Dir`.

## Go version cheat-sheet (verify before use)

- 1.13 — `errors.Is/As`, `%w`, `http.NewRequestWithContext`. 1.16 — `signal.NotifyContext`, `embed`/`io/fs`, `http.FS`. 1.18 — generics, workspaces, fuzzing. 1.20 — `errors.Join`. 1.21 — `min`/`max`/`clear`, `log/slog` (no range-over-int yet).
- **1.22 — ServeMux method + `{wildcard}` routing, `r.PathValue`/`SetPathValue`, per-iteration loop variables, `for range int`, `math/rand/v2`, `ServeFileFS`.**
- 1.23 — range-over-func iterators, `unique`. 1.24 — generic type aliases.

Trap: the loop-variable per-iteration change and the net/http routing change **both landed in 1.22** — never attribute either to an earlier version.

## Sources

- https://go.dev/blog/routing-enhancements
- https://go.dev/doc/go1.22
- https://pkg.go.dev/net/http
- https://go.dev/doc/devel/release

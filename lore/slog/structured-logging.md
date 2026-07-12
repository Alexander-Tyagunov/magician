# slog — Structured logging (slog + zap/zerolog)

Baseline: **`log/slog`** (stdlib since **Go 1.21**). Reach for **zap** (`go.uber.org/zap` v1.28.0) or **zerolog** (`github.com/rs/zerolog` v1.35.1) only in hot paths. Both ship a `slog.Handler` bridge, so keep app code on the `slog` API and swap the backend.

## Setup — DO / DON'T

DO — build a logger from a handler and make it the default early in `main`:
```go
h := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level:     slog.LevelInfo,
    AddSource: true, // file:line
})
slog.SetDefault(slog.New(h)) // also bridges the old log package
```
- `NewJSONHandler` for prod (machine-parseable); `NewTextHandler` (`key=value`) for local dev.
- `SetDefault` once; then package-level `slog.Info(...)` works everywhere.

DON'T:
- DON'T use `fmt.Println`/`log.Printf` for application logs — unstructured, no levels, no fields.
- DON'T create ad-hoc loggers per call; construct once, pass or use default.

## Attributes & levels — DO / DON'T

DO — prefer typed attrs; key-value pairs are fine but easy to desync:
```go
slog.Info("order placed", "id", id, "total", total)        // convenient
slog.Info("order placed", slog.String("id", id), slog.Int("total", total)) // typed, faster
```
- Levels: `LevelDebug(-4) LevelInfo(0) LevelWarn(4) LevelError(8)`. Gaps allow custom levels.
- Run `go vet` (the `slog` analyzer catches omitted/mismatched key-value args).

DON'T:
- DON'T log secrets/PII/tokens/passwords. Redact via `LogValuer` or `ReplaceAttr` (below).
- DON'T rely on context cancellation to suppress a log — it won't; the record still writes.

### Redaction
```go
type Password string
func (Password) LogValue() slog.Value { return slog.StringValue("REDACTED") }
```
Or strip/rename globally with `HandlerOptions.ReplaceAttr(groups []string, a slog.Attr) slog.Attr` (return `slog.Attr{}` to drop).

## Context & structure — DO / DON'T

DO — pass `context.Context` so handlers can pull trace IDs:
```go
slog.InfoContext(ctx, "handling request", "route", route)
```
DO — bind reusable fields once with `With` (formatted a single time by the handler):
```go
reqLog := slog.Default().With("request_id", rid, "user", uid)
reqLog.Info("start"); reqLog.Warn("slow")
```
DO — group related fields:
```go
slog.Info("req", slog.Group("http", "method", m, "status", 200))
// JSON: "http":{"method":"...","status":200}
```
- `WithGroup("db")` qualifies all later keys; `slog.GroupAttrs` (Go 1.25) is the typed, cheaper form.

DON'T:
- DON'T stash the logger in a `context.Value` — pass it explicitly (rejected as hidden coupling).
- DON'T recompute expensive fields on disabled levels; guard with `logger.Enabled(ctx, lvl)` or `LogValuer`.

## Dynamic level — DO

```go
lvl := new(slog.LevelVar)            // goroutine-safe, defaults Info
h := slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{Level: lvl})
slog.SetDefault(slog.New(h))
lvl.Set(slog.LevelDebug)             // flip at runtime (e.g. SIGHUP, env)
```

## Hot paths — DO

`slog` args are always evaluated even when dropped. For high-frequency logs use `LogAttrs` (no `any` boxing):
```go
logger.LogAttrs(ctx, slog.LevelInfo, "hit", slog.Int("count", n))
```
If that's still too slow, switch the backend to zap or zerolog while keeping the `slog` call sites.

### zap backend (fastest; typed, zero-alloc encoder)
```go
zl, _ := zap.NewProduction() // JSON, ISO8601, caller; NewDevelopment() for console
defer zl.Sync()              // ALWAYS flush before exit
slog.SetDefault(slog.New(zapslog.NewHandler(zl.Core()))) // go.uber.org/zap/exp/zapslog
```
- Direct zap: `zl.Info("msg", zap.String("k", v), zap.Int("n", n))` (typed `*Logger`) vs `zl.Sugar().Infow("msg","k",v)` (ergonomic `SugaredLogger`, ~slower). Prefer typed on hot paths.
- DON'T forget `defer zl.Sync()` — buffered output is lost otherwise.

### zerolog backend (zero-alloc, chained)
```go
zl := zerolog.New(os.Stderr).With().Timestamp().Logger()
slog.SetDefault(slog.New(zerolog.NewSlogHandler(zl)))
```
- Direct zerolog: `zl.Info().Str("k", v).Int("n", n).Msg("done")` — **the chain MUST end in `.Msg`/`.Msgf` or nothing logs** (no compile error).
- Dev pretty output: `zerolog.ConsoleWriter{Out: os.Stderr}` (human-readable, but slow — dev only).
- DON'T retain an `*Event` after `Msg`; events are pooled.

## Choosing — DO

- DO default to `log/slog` — no deps, good enough for ~all services.
- DO use zap/zerolog only for measured hot paths; benchmark first (`656 ns/op` zap vs slog — verify for your load, don't assume).
- DO keep call sites on the `slog` API via the bridge handlers so the backend stays swappable.
- DON'T mix direct zap/zerolog calls with `slog` calls app-wide — pick one call surface per layer.

## Ops notes
- Config (level, format, sampling) from **env**, not committed constants.
- JSON to stdout/stderr; let the platform (k8s, systemd) handle rotation/shipping — don't write app-managed log files unless required.
- Recent stdlib adds: `SetLogLoggerLevel` (1.22), `GroupAttrs` (1.25), `NewMultiHandler` (1.26), `DiscardHandler`.

## Sources
- https://pkg.go.dev/log/slog
- https://go.dev/blog/slog
- https://github.com/uber-go/zap
- https://pkg.go.dev/go.uber.org/zap/exp/zapslog
- https://github.com/rs/zerolog
- https://pkg.go.dev/github.com/rs/zerolog

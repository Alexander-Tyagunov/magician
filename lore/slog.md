# slog — core digest

Version cue: `log/slog` — stdlib since Go 1.21 (baseline; recommended default). Frontend `Logger` / backend `Handler` split — zap/zerolog can back slog for higher throughput. `DiscardHandler` (1.24), `GroupAttrs`+`Record.Source` (1.25), `MultiHandler` (1.26).

DO configure once at startup: `slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stderr, opts)))` — JSON for prod (parseable); also reroutes stdlib `log`.
DO pass context: `slog.InfoContext(ctx,…)` / `LogAttrs(ctx,lvl,msg,…)` so handlers can pull trace/span IDs.
DO use typed attrs + `LogAttrs` on hot paths (no alloc): `slog.String`,`slog.Int`; `logger.With(k,v)` factors common attrs (formatted once).
DO vary level at runtime via one `*slog.LevelVar` (concurrent-safe) in `HandlerOptions.Level` — never rebuild the logger.
DON'T log secrets — implement `LogValuer.LogValue` to redact, or `HandlerOptions.ReplaceAttr` to drop/mask keys.
DON'T trust alternating `k,v` pairs — run the slog `go vet` pass to catch missing keys; prefer typed constructors.
DON'T do expensive work in args (always evaluated even if dropped) — pass `&v`/`LogValuer`, gate with `Handler.Enabled`.
DON'T bake level/format into committed config — read them from env.

Commands: `go vet ./...` (slog analyzer) · `go doc log/slog`

Deep dive when writing non-trivial slog — read lore/slog/{structured-logging}.md

## Sources
pkg.go.dev/log/slog · go.dev/blog/slog · github.com/uber-go/zap

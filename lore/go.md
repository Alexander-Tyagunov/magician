Go core digest. Verify versions vs go.dev/doc; never claim a feature earlier than reality.

DO handle every error: `if err != nil { return fmt.Errorf("ctx: %w", err) }` (%w = 1.13). Wrap to add context; test with `errors.Is`/`errors.As` (1.13), combine via `errors.Join` (1.20). DO pass `ctx context.Context` as first param on blocking/public funcs; never store in structs. DO `defer` cleanup (LIFO, at func return). DO accept interfaces, return concrete types; keep interfaces small, define at the consumer. DO run `-race` and bound goroutine lifetimes (leaks = unclosed channels / lost cancel).

DON'T ignore or `_ =` errors. DON'T shadow `err` with `:=` in nested scopes. DON'T share memory across goroutines without sync (`sync.Mutex`/channels); maps aren't concurrent-safe. DON'T `panic` for ordinary errors. DON'T return a nil concrete pointer as a non-nil interface. DON'T assume map iteration order.

Version cue: 1.26 stable (1.25 supported). **1.22**: per-iteration loop vars + net/http ServeMux method+wildcard routing (`GET /items/{id}`). 1.21: `slog`/`min`/`max`/`clear`/`slices`/`maps`. 1.20: `errors.Join`. 1.18: generics/workspaces/fuzzing. 1.23: range-over-func; 1.24: generic aliases + `tool` dir.

Commands: `go build ./...` · `go test -race ./...` · `go vet ./...` · `golangci-lint run`. Format with `gofmt`/`goimports`.

Deep dive when writing non-trivial Go — read lore/go/{language-and-idioms,errors,concurrency,http-and-servers,testing,modules-and-tooling,performance}.md

Sources: go.dev/doc/effective_go, go.dev/ref/spec, go.dev/doc/go1.{22,26}, pkg.go.dev.

Common AI mistakes: ignoring errors (always check `err != nil`); shadowing variables with `:=` in nested scopes; goroutine leaks from unclosed channels; nil pointer dereference on interface values.
Commands: test: `go test ./...`, lint: `golangci-lint run`, build: `go build ./...`, vet: `go vet ./...`.
Gotchas: `defer` runs LIFO at function return, not block; use `context.Context` as first arg in all public functions; `sync.WaitGroup` for goroutine coordination; table-driven tests are idiomatic.

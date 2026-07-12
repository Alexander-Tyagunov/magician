# Go — Modules & tooling

Current stable: Go 1.26 line (1.25 also supported). Verify features against release notes; never claim a feature earlier than reality. The **1.22 loop-var change** and **1.22 net/http routing** are the classic traps.

## go.mod / go.sum — DO

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

## go.mod / go.sum — DON'T

- DON'T commit without `go mod tidy` — the #1 reviewer catch. It adds missing and removes unused requires and prunes `go.sum`.
- DON'T hand-edit `go.sum`. DON'T bump the `go` line just to use a tool; it forces the floor on every consumer.
- DON'T set `GOSUMDB=off` casually — toolchain downloads are verified against the checksum DB and will fail without it.

## Dependencies — DO

- DO use the version query suffix: `go get pkg@v1.3.4`, `@latest`, `@master`, `@<commit>`, `@patch`, `@none` (remove).
- DO `go get -u ./...` to upgrade minor/patch of imports; `go get -u=patch ./...` for patch-only.
- DO `go list -m -u all` to discover available updates.
- DO `go mod download` only to pre-fill the cache (CI, proxy). Plain `go build`/`go test` fetch as needed.

## Semantic import versioning — DO / DON'T

- v0/v1: no suffix. **v2+**: the module path **must** carry the major suffix (`/v2`, `/v3`) — this is a distinct import path so multiple majors coexist (diamond deps). Introduced with modules.
- DO bump the path in `go.mod` (`module example.com/lib/v2`) and in every internal import when releasing v2.
- DON'T expect `go get pkg@v2.0.0` to work against a module that didn't add `/v2` — you'll get `+incompatible` fallback only for pre-modules tags.

## Workspaces (go.work) — 1.18 — DO

- DO use `go work` for **multi-module local dev** (edit several modules together without `replace` churn).

```
go work init ./svc ./lib
go work use ./newmod        # add; -r recurses
go work sync                # push workspace build list into member go.mods
```

- DON'T commit `go.work`/`go.work.sum` to a library repo — it's a local-dev convenience; CI should build modules standalone. Check mode with `go env GOWORK`.

## replace / exclude — DO / DON'T

- `replace` and `exclude` apply **only in the main module** — ignored when your module is a dependency.
- DO use `replace ... => ./local/path` (version omitted for local) for a temporary fork or local dep. A `replace` still needs a matching `require`.

```
replace example.com/lib => ../lib                 # local
replace example.com/lib v1.2.3 => example.com/fork/lib v1.2.4
```

- DON'T ship a library that relies on `replace` to build — consumers won't inherit it. Prefer `go.work` locally, real releases for consumers.

## Build tags (//go:build) — 1.17 — DO

- DO use the modern `//go:build linux && amd64` expression form. Put it at the top, followed by a blank line, before `package`.
- DON'T use the legacy `// +build` form in new code (`gofmt` still syncs it if present). Only **one** `//go:build` line is allowed per file.
- Filename constraints are implicit: `foo_linux.go`, `bar_windows_amd64.go`, `x_test.go`. `unix` is a valid tag; per-release tags exist (`go1.24`) but not for minor/beta.

## Formatting & vetting — DO

- DO run `gofmt` (or `go fmt ./...`) — non-negotiable, no config. `goimports` (`golang.org/x/tools/cmd/goimports`) additionally manages import grouping/removal.
- DO run `go vet ./...`. `go test` already runs a high-confidence vet subset (printf, atomic, etc.); disable with `-vet=off`.
- `go vet -vettool=$(which shadow)` adds extra analyzers built on `golang.org/x/tools/go/analysis`.

## Linters — DO

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

## go generate — DO

- DO put `//go:generate <cmd>` directives in source (no space after `//`); they run **only** on explicit `go generate ./...`, never during build/test.
- DO commit generated files and mark them `// Code generated ... DO NOT EDIT.`.

## Tool dependencies — version-adaptive

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

## Vendoring — DON'T (usually)

- DON'T `go mod vendor` unless you need airgapped/hermetic builds or a policy requires it — the module cache + proxy already give reproducibility.
- If a `vendor/` exists and `go >= 1.14`, builds auto-use it (`-mod=vendor`) with **no** network access. Then you **must** re-run `go mod vendor` after any dependency change, or builds fail. Override with `-mod=mod`.

## Language-feature version map (verify before use)

- 1.13: `errors.Is`/`As`, `%w` wrapping
- 1.16: modules on by default, `//go:embed`
- 1.18: generics, workspaces, native fuzzing
- 1.19: `GOMEMLIMIT` (soft memory limit)
- 1.20: `errors.Join`
- 1.21: `min`/`max`/`clear` builtins, `log/slog`, toolchain management. **No** for-range-over-int yet.
- 1.22: **per-iteration loop variables** (gated on `go 1.22` in go.mod), for-range-over-int (`for i := range n`), `net/http` ServeMux method+wildcard routing (`GET /items/{id}`), `math/rand/v2`
- 1.23: range-over-func iterators (`iter`), `unique`
- 1.24: generic type aliases, `tool` directive / `go get -tool`

## Sources

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

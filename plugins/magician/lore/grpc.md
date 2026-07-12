# gRPC (Go) — core

DO use `grpc.NewClient(target, opts...)` (v1.63+); DON'T use deprecated `Dial`/`DialContext`. NewClient does no I/O — connects lazily; default resolver is `dns`.
DO secure: client `grpc.WithTransportCredentials(creds)`, server `grpc.Creds(...)`; DON'T ship `insecure.NewCredentials()` / deprecated `WithInsecure()` in prod.
DO set a per-RPC deadline: `ctx,cancel:=context.WithTimeout(ctx,5*time.Second); defer cancel()`; DON'T rely on deprecated `WithTimeout`/`WithBlock` (NewClient ignores them).
DO return/inspect errors via `status.Errorf(codes.X,…)` + `status.Code(err)`; DON'T use deprecated `grpc.Errorf`.
DO put cross-cutting logic in interceptors (`Unary/StreamServerInterceptor`), validate every input, add health service + `GracefulStop()`.
DON'T log tokens/metadata/creds; keep addrs+keys in env, uncommitted. Enable reflection only outside prod.

Version: gRPC-Go v1.82.x; needs current Go (two latest majors). Gen via protoc-gen-go (google.golang.org/protobuf) + protoc-gen-go-grpc, or buf.

Commands: `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest` · `protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative f.proto` · buf: `buf lint`·`buf breaking`·`buf generate`

Deep dive when writing non-trivial grpc — read lore/grpc/{services-streaming-interceptors}.md

## Sources
grpc.io/docs/languages/go · pkg.go.dev/google.golang.org/grpc · protobuf.dev · buf.build/docs

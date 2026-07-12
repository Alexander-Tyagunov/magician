# grpc — Services, streaming & interceptors

Verified against **google.golang.org/grpc v1.82.0** (2026-06-30), proto3 +
`protoc-gen-go` / `protoc-gen-go-grpc`, `connectrpc.com/connect`. Go foundation lore
lives elsewhere — this is gRPC-specifics only.

## DO — define the contract (proto3) & generate

```proto
syntax = "proto3";
package route.v1;
option go_package = "example.com/gen/route/v1;routev1";

service RouteGuide {
  rpc GetFeature(Point) returns (Feature);                       // unary
  rpc ListFeatures(Rectangle) returns (stream Feature);          // server stream
  rpc RecordRoute(stream Point) returns (RouteSummary);          // client stream
  rpc RouteChat(stream RouteNote) returns (stream RouteNote);    // bidi stream
}
```

- **DO** set `option go_package`; codegen fails or misplaces files without it.
- **DO** install plugins and generate:

```sh
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative route/v1/route.proto
```

- **DO** prefer **buf** (`buf.gen.yaml` + `buf generate`) for lint, breaking-change
  detection, reproducible CI builds. `protoc` is the low-level fallback.
- **DON'T** hand-edit `*.pb.go` / `*_grpc.pb.go` — regenerate. Commit generated code
  *or* generate in CI, consistently.
- **DON'T** renumber/reuse field tags (breaks wire compat) — add fields, `reserved`
  removed ones.

## DO — implement & run the server

```go
type server struct{ pb.UnimplementedRouteGuideServer } // MUST embed: forward-compat

func (s *server) GetFeature(ctx context.Context, p *pb.Point) (*pb.Feature, error) {
    return &pb.Feature{Location: p}, nil
}

lis, _ := net.Listen("tcp", ":50051")
creds, _ := credentials.NewServerTLSFromFile("server.crt", "server.key")
srv := grpc.NewServer(grpc.Creds(creds),
    grpc.ChainUnaryInterceptor(logging, auth),
    grpc.ChainStreamInterceptor(streamLogging))
pb.RegisterRouteGuideServer(srv, &server{})
srv.Serve(lis) // blocks; srv.GracefulStop() on SIGTERM to drain in-flight RPCs
```

- **DO** embed `pb.Unimplemented<Svc>Server` in every impl — lets you add RPCs to
  the proto without breaking the build.

## DO — streaming server methods

```go
// server stream: Send N, return nil to end
func (s *server) ListFeatures(r *pb.Rectangle, stream pb.RouteGuide_ListFeaturesServer) error {
    for _, f := range s.features { if err := stream.Send(f); err != nil { return err } }
    return nil
}
// client stream: loop stream.Recv() until io.EOF, then stream.SendAndClose(summary)
// bidi:          interleave Recv/Send in a loop; return nil on io.EOF
```

- **DO** honor `stream.Context()` for cancellation/deadlines inside loops.
- **DON'T** call `Send` concurrently on one stream, nor `Recv` concurrently — each
  direction is single-goroutine (one reader goroutine + one writer is fine).
- Client mirrors: server-stream `Recv()` to `io.EOF`; client-stream `Send()` +
  `CloseAndRecv()`; bidi `Send`/`Recv` (reader goroutine) + `CloseSend()`.

## DO — client (NewClient, not Dial)

```go
conn, err := grpc.NewClient("dns:///route.svc:50051",
    grpc.WithTransportCredentials(creds),
    grpc.WithChainUnaryInterceptor(clientAuth))
if err != nil { return err }
defer conn.Close()
c := pb.NewRouteGuideClient(conn)

ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
defer cancel() // ALWAYS set a deadline
f, err := c.GetFeature(ctx, &pb.Point{})
```

- **DO** use `grpc.NewClient` — `Dial`/`DialContext` are **deprecated** (work
  through 1.x). `NewClient` does no I/O; connects lazily on first RPC. It defaults
  the resolver to `dns` (use a `dns:///` target) and **ignores**
  `WithBlock`/`WithTimeout`/`WithReturnConnectionError`.
- **DON'T** create a `ClientConn` per call — it multiplexes; share one, `Close()`
  once. Read streams to `io.EOF` (or cancel ctx) to free them.

## DO — deadlines, cancellation, errors

- **DO** set a deadline on *every* client call (`context.WithTimeout`) — a missing
  deadline is an unbounded hang. Check ctx server-side; cancel/expiry surfaces as
  `codes.Canceled` / `codes.DeadlineExceeded`.
- **DO** return typed errors and inspect them:

```go
return nil, status.Errorf(codes.InvalidArgument, "name required")
// client: FromError → (*status.Status, ok); Convert → non-nil even for plain err
if st, ok := status.FromError(err); ok { _ = st.Code() /* codes.NotFound … */ }
```

- **DON'T** return bare `errors.New` from handlers — it maps to `codes.Unknown`.
  Use `status.Error`/`Errorf` with a specific `codes.X`.

## DO — metadata (headers)

```go
ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "bearer "+tok) // client
md, ok := metadata.FromIncomingContext(ctx)                                 // server
if ok { tok := md.Get("authorization") /* []string, keys lowercased */ }
```

- **DON'T** use `grpc-` keys (reserved). `metadata.Pairs` **panics** on odd args.
  `NewOutgoingContext` overwrites; `AppendToOutgoingContext` merges.

## DO — interceptors (cross-cutting: auth, logging, metrics)

```go
func auth(ctx context.Context, req any, info *grpc.UnaryServerInfo,
          h grpc.UnaryHandler) (any, error) {              // UnaryServerInterceptor
    md, _ := metadata.FromIncomingContext(ctx)
    if !valid(md.Get("authorization")) {
        return nil, status.Error(codes.Unauthenticated, "bad token")
    }
    return h(ctx, req) // MUST call handler to proceed
}
```

Stream form: `func(srv any, ServerStream, *StreamServerInfo, StreamHandler) error`;
client forms are `Unary`/`StreamClientInterceptor`.

- **DO** register with `grpc.ChainUnaryInterceptor(a,b)` / `ChainStreamInterceptor`
  (server), `grpc.WithChainUnaryInterceptor` (client). First listed = outermost.
- **DO** wrap/embed `ServerStream` to intercept per-message `Send`/`Recv`.
- **DON'T** forget to invoke `handler` — skipping it silently drops the RPC.
- **DON'T** reimplement logging/auth/recovery — prefer
  `github.com/grpc-ecosystem/go-grpc-middleware`.

## DON'T — security / ops

- **DON'T** ship `insecure.NewCredentials()` (`credentials/insecure`) — test only.
  Use TLS: server `credentials.NewServerTLSFromFile` / `NewTLS(*tls.Config)` +
  `grpc.Creds`; client `credentials.NewClientTLSFromFile` / `NewTLS` +
  `grpc.WithTransportCredentials`. Use mTLS for service-to-service.
- **DON'T** log tokens/metadata or trust client input — validate every field.
- **DON'T** hardcode certs/secrets/addresses — load from env/secret store, not git.
- **DO** set `grpc.MaxRecvMsgSize` / keepalive deliberately; default recv cap ~4 MB.

## connect-go — the browser-friendly alternative

`connectrpc.com/connect`. Same `.proto`, plugin `protoc-gen-connect-go` (buf or
protoc). One server speaks **three protocols** at once: Connect (HTTP/1.1 *or* /2,
JSON or binary), **gRPC**, **gRPC-Web** — no Envoy proxy; interops with grpc-go
clients both ways.

- **DO** pick connect-go when browsers/HTTP/1.1 or plain `net/http` middleware
  matter; stay on grpc-go for pure backend meshes needing the full gRPC feature set.
  Same schema — the switch is codegen-level.

## Sources

- https://grpc.io/docs/languages/go/quickstart/
- https://grpc.io/docs/languages/go/basics/
- https://grpc.io/docs/guides/error/
- https://grpc.io/docs/guides/auth/
- https://grpc.io/docs/guides/interceptors/
- https://pkg.go.dev/google.golang.org/grpc
- https://pkg.go.dev/google.golang.org/grpc/metadata
- https://protobuf.dev/programming-guides/proto3/
- https://connectrpc.com/docs/go/getting-started/

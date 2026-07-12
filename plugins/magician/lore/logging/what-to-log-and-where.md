# Logging (principles) — What to log & where

Align to the OpenTelemetry log data model (Timestamp, SeverityText/Number, Body, TraceId/SpanId, Attributes, Resource) and 12-factor XI (logs are event streams). Language/platform-agnostic; pairs with per-framework lore (e.g. lore/slog).

## Where — the app emits, the environment routes
DO write the event stream **unbuffered to stdout** (stderr acceptable for crashes). One event per line.
DO let the platform/collector capture, aggregate, and route it — the destination is not the app's concern.
DON'T open, rotate, or manage log files in app code; DON'T hardcode paths, endpoints, or sinks (12-factor).
DON'T `print`/write to stdout AND a file — pick the stream; duplication corrupts aggregation.

## What — log at meaningful execution points, not everywhere
Emit ONE structured event per logical action, at decision boundaries:
- **Request/job entry & exit**: method, route, status/outcome, duration_ms. Log exit once, with the result — not entry+exit noise for trivial calls.
- **External calls** (HTTP/DB/queue/RPC): target, operation, outcome, latency, retry/attempt count. Both success (INFO/DEBUG) and failure (WARN/ERROR).
- **State changes / side effects**: created/updated/deleted an entity, payment captured, feature flag flipped — with the id, not the whole object.
- **Branch decisions that matter**: cache hit/miss, fallback taken, validation rejected, rate-limit hit, auth allow/deny.
- **Errors**: what failed, the inputs (redacted), and recovery/next step. See lore/logging/errors-and-exceptions.md.

DON'T log inside hot loops or per-row/per-iteration; aggregate to one summary event (n processed, m failed).
DON'T narrate line-by-line ("entering function", "got here"); that's a debugger's job, not production logs.
DON'T log success of trivial pure functions or getters.

## The event shape (OTel-aligned attributes)
Put the stable event class in the message/body; put variables in typed attributes; propagate a correlation id across the flow (see lore/logging/structured-and-correlation.md):

```json
{"timestamp":"2026-07-12T10:15:04.812Z","severity":"INFO","body":"http.request.served",
 "trace_id":"4bf92f...","span_id":"00f067...","http.request.method":"POST",
 "http.route":"/orders/{id}","http.response.status_code":201,"duration_ms":37,"order.id":"o_1a2b"}
```
```json
{"timestamp":"2026-07-12T10:15:09.220Z","severity":"ERROR","body":"payment.charge.failed",
 "trace_id":"4bf92f...","server.address":"payments.internal","attempt":3,
 "error.type":"UpstreamTimeout","exception.type":"TimeoutError","order.id":"o_1a2b"}
```
Use OTel HTTP names (`http.request.method`, `http.response.status_code`, `url.path`, `server.address`) and exception names (`exception.type`, `exception.message`, `exception.stacktrace`) so backends parse without regex. Set severity by intent (lore/logging/levels-and-environments.md); NEVER log secrets/tokens/PII (lore/logging/security-and-pii.md); bound volume on high-traffic paths (lore/logging/sampling-and-performance.md).

## Sources
- 12factor.net/logs
- opentelemetry.io/docs/specs/otel/logs/data-model
- opentelemetry.io/docs/specs/semconv/http/http-spans
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs

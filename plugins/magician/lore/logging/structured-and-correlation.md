# Logging (principles) — Structured & Correlation

Emit ONE structured event per logical action, not prose. Align to the OpenTelemetry log data model + 12-factor: machine-parseable objects an aggregator can index, filter, and join back to traces.

## DO
- Emit each event as ONE JSON object, NDJSON (one record per line) to stdout. Flat, stable keys; TYPED values (numbers as numbers, booleans as booleans) — don't stringify then regex later.
- Split message from context per OTel: human text in `Body`; variable data in `Attributes` (`user.id`, `http.status_code`, `duration_ms`). Don't interpolate values into a message you must re-parse.
- Set severity with BOTH fields: `SeverityText` ("INFO"/"ERROR") + `SeverityNumber` — ranges TRACE 1-4, DEBUG 5-8, INFO 9-12, WARN 13-16, ERROR 17-20, FATAL 21-24 (>=17 = erroneous).
- Attach correlation on EVERY event: `TraceId` (32 hex) + `SpanId` (16 hex). Accept/propagate the W3C `traceparent` across service calls; mint a request id at the entry point if none arrives.
- Carry the id through the whole flow via context (async context / thread-local / MDC) so it survives await & thread boundaries — bind once at entry, don't thread it by hand.
- Set immutable identity once as resource attributes: `service.name`, `service.version`, `deployment.environment`, host/instance.
- Keep a stable schema: same key = same meaning + type everywhere; namespace with dots (`db.rows_affected`). Stable keys are what queries target.
- For errors add `exception.type`, `exception.message`, `exception.stacktrace` as fields, not buried in text — lore/logging/errors-and-exceptions.md.

## DON'T
- DON'T write logfiles or do rotation/routing inside the app (12-factor XI): stream unbuffered to stdout; the platform collates & ships. Files are the runtime's job.
- DON'T reuse one key with two shapes (`user` = id here, object there) — it breaks the index and typed queries.
- DON'T drop the id across queues/jobs/retries — propagate `traceparent` into messages and downstream requests.
- DON'T dump whole request/response bodies or huge arrays into a field; log sizes, ids, counts. Never put secrets/PII in fields — lore/logging/security-and-pii.md.

## Example — one event (NDJSON)
`{"timestamp":"2026-07-12T10:15:04.123Z","severity_text":"ERROR","severity_number":17,"body":"charge failed","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","span_id":"00f067aa0ba902b7","service.name":"checkout","deployment.environment":"prod","http.method":"POST","http.route":"/charge","http.status_code":502,"duration_ms":812,"order.id":"o-1934","exception.type":"UpstreamError","exception.message":"gateway 502"}`

Propagate across services with the W3C header:
`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`

These structured keys become the query fields downstream (filter on `http.status_code>=500`, `trace_id`, `exception.type`) — see lore/logging/what-to-log-and-where.md and the platform's query lore. Framework specifics (field binding, MDC/contextvars, JSON encoders) live in the per-language log lore (e.g. lore/slog).

## Sources
- opentelemetry.io/docs/specs/otel/logs/data-model
- w3.org/TR/trace-context
- 12factor.net/logs
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs

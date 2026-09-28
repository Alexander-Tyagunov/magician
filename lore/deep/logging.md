# Logging (principles) — deep dive

> On-demand companion to `lore/logging.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Levels & Environments](#levels-and-environments) · [What to log & where](#what-to-log-and-where) · [Structured & Correlation](#structured-and-correlation) · [Errors & Exceptions](#errors-and-exceptions) · [Security and PII](#security-and-pii) · [Sampling & performance](#sampling-and-performance)

## Levels & Environments <a id="levels-and-environments"></a>

Pick the level by INTENT, the threshold by ENVIRONMENT. Align names to OpenTelemetry SeverityNumber so
backends normalize and range-filter ("smaller numerical values correspond to less severe events";
SeverityNumber >= 17 signals an error).

### Choose level by intent (OTel SeverityNumber)
- TRACE (1) — ultra-fine step-by-step; off outside deep debugging.
- DEBUG (5) — developer diagnostics: values, branch chosen, cache hit/miss.
- INFO (9) — a normal thing worth recording: request handled, job done, state change.
- WARN (13) — recoverable/degraded: retry, fallback, deprecated path, near-limit; app keeps working.
- ERROR (17) — an operation failed, needs attention; include full context.
- FATAL (21) — process cannot continue; emit, then exit non-zero.
Map your framework to these so severity survives export: e.g. Log4j/logback ERROR->17, FATAL->21; .NET
Critical->21. Emit BOTH SeverityText and SeverityNumber; backends filter the number, humans read text.

### Set the threshold by ENVIRONMENT (never hardcode)
Level is the minimum severity emitted, not hardcoded. Per 12-factor, "a twelve-factor app never concerns
itself with routing or storage of its output stream" — read the threshold from config, write to stdout
unbuffered; the platform collects and routes.
- dev/local: DEBUG (or TRACE for a session) — fast feedback.
- test/CI: INFO (DEBUG only when diagnosing a flake).
- staging: INFO, WARN-clean before promotion.
- prod: INFO or WARN baseline; keep it dial-able: raise verbosity per incident, then revert.

DO make it one env var, e.g. `LOG_LEVEL=info` (case-insensitive names OR OTel numbers), parsed once at
startup, defaulting to INFO on an unknown value — never crash on a typo.
DO allow a scoped override (per-module) to turn up one subsystem without flooding others.
DO reload/restart cheaply to change level; a runtime toggle beats redeploy mid-incident.
DON'T hardcode `setLevel(DEBUG)` or ship a debug build to prod — it leaks internals, costs money on
ingest/storage, and buries the signal.
DON'T invent bespoke levels ("VERBOSE","AUDIT") with no OTel SeverityText — exporters drop or mislabel them.
Notice/Critical DO map canonically (INFO2(10)/ERROR2(18)); use those, don't reinvent.
DON'T route by hand (open files, hit a service) from app code — that's the environment's job.

### Gotchas
- Threshold is inclusive-upward: `LOG_LEVEL=warn` emits WARN+ERROR+FATAL, suppresses INFO/DEBUG. Verify the
  boundary; off-by-one silences alerts.
- Guard DEBUG payloads behind `isDebugEnabled()`/lazy args so string-building doesn't run above DEBUG.
- Don't over-use WARN: one nobody acts on trains responders to ignore them. If it needs action it's ERROR;
  if noteworthy-normal, INFO.
- One env, one meaning: don't make prod quieter by changing what INFO *means* — change the THRESHOLD, not
  individual events.

Match the deploy platform for shape + queries (see lore/{dynatrace,grafana,splunk,gcp-logging,cloudwatch,
azure-monitor}.md), keep events structured (lore/deep/logging.md#structured-and-correlation), and make failures
actionable (lore/deep/logging.md#errors-and-exceptions).

### Sources
opentelemetry.io/docs/specs/otel/logs/data-model · /logs/data-model-appendix · 12factor.net/logs

## What to log & where <a id="what-to-log-and-where"></a>

Align to the OpenTelemetry log data model (Timestamp, SeverityText/Number, Body, TraceId/SpanId, Attributes, Resource) and 12-factor XI (logs are event streams). Language/platform-agnostic; pairs with per-framework lore (e.g. lore/slog.md).

### Where — the app emits, the environment routes
DO write the event stream **unbuffered to stdout** (stderr acceptable for crashes). One event per line.
DO let the platform/collector capture, aggregate, and route it — the destination is not the app's concern.
DON'T open, rotate, or manage log files in app code; DON'T hardcode paths, endpoints, or sinks (12-factor).
DON'T `print`/write to stdout AND a file — pick the stream; duplication corrupts aggregation.

### What — log at meaningful execution points, not everywhere
Emit ONE structured event per logical action, at decision boundaries:
- **Request/job entry & exit**: method, route, status/outcome, duration_ms. Log exit once, with the result — not entry+exit noise for trivial calls.
- **External calls** (HTTP/DB/queue/RPC): target, operation, outcome, latency, retry/attempt count. Both success (INFO/DEBUG) and failure (WARN/ERROR).
- **State changes / side effects**: created/updated/deleted an entity, payment captured, feature flag flipped — with the id, not the whole object.
- **Branch decisions that matter**: cache hit/miss, fallback taken, validation rejected, rate-limit hit, auth allow/deny.
- **Errors**: what failed, the inputs (redacted), and recovery/next step. See lore/deep/logging.md#errors-and-exceptions.

DON'T log inside hot loops or per-row/per-iteration; aggregate to one summary event (n processed, m failed).
DON'T narrate line-by-line ("entering function", "got here"); that's a debugger's job, not production logs.
DON'T log success of trivial pure functions or getters.

### The event shape (OTel-aligned attributes)
Put the stable event class in the message/body; put variables in typed attributes; propagate a correlation id across the flow (see lore/deep/logging.md#structured-and-correlation):

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
Use OTel HTTP names (`http.request.method`, `http.response.status_code`, `url.path`, `server.address`) and exception names (`exception.type`, `exception.message`, `exception.stacktrace`) so backends parse without regex. Set severity by intent (lore/deep/logging.md#levels-and-environments); NEVER log secrets/tokens/PII (lore/deep/logging.md#security-and-pii); bound volume on high-traffic paths (lore/deep/logging.md#sampling-and-performance).

### Sources
- 12factor.net/logs
- opentelemetry.io/docs/specs/otel/logs/data-model
- opentelemetry.io/docs/specs/semconv/http/http-spans
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs

## Structured & Correlation <a id="structured-and-correlation"></a>

Emit ONE structured event per logical action, not prose. Align to the OpenTelemetry log data model + 12-factor: machine-parseable objects an aggregator can index, filter, and join back to traces.

### DO
- Emit each event as ONE JSON object, NDJSON (one record per line) to stdout. Flat, stable keys; TYPED values (numbers as numbers, booleans as booleans) — don't stringify then regex later.
- Split message from context per OTel: human text in `Body`; variable data in `Attributes` (`user.id`, `http.status_code`, `duration_ms`). Don't interpolate values into a message you must re-parse.
- Set severity with BOTH fields: `SeverityText` ("INFO"/"ERROR") + `SeverityNumber` — ranges TRACE 1-4, DEBUG 5-8, INFO 9-12, WARN 13-16, ERROR 17-20, FATAL 21-24 (>=17 = erroneous).
- Attach correlation on EVERY event: `TraceId` (32 hex) + `SpanId` (16 hex). Accept/propagate the W3C `traceparent` across service calls; mint a request id at the entry point if none arrives.
- Carry the id through the whole flow via context (async context / thread-local / MDC) so it survives await & thread boundaries — bind once at entry, don't thread it by hand.
- Set immutable identity once as resource attributes: `service.name`, `service.version`, `deployment.environment`, host/instance.
- Keep a stable schema: same key = same meaning + type everywhere; namespace with dots (`db.rows_affected`). Stable keys are what queries target.
- For errors add `exception.type`, `exception.message`, `exception.stacktrace` as fields, not buried in text — lore/deep/logging.md#errors-and-exceptions.

### DON'T
- DON'T write logfiles or do rotation/routing inside the app (12-factor XI): stream unbuffered to stdout; the platform collates & ships. Files are the runtime's job.
- DON'T reuse one key with two shapes (`user` = id here, object there) — it breaks the index and typed queries.
- DON'T drop the id across queues/jobs/retries — propagate `traceparent` into messages and downstream requests.
- DON'T dump whole request/response bodies or huge arrays into a field; log sizes, ids, counts. Never put secrets/PII in fields — lore/deep/logging.md#security-and-pii.

### Example — one event (NDJSON)
`{"timestamp":"2026-07-12T10:15:04.123Z","severity_text":"ERROR","severity_number":17,"body":"charge failed","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","span_id":"00f067aa0ba902b7","service.name":"checkout","deployment.environment":"prod","http.method":"POST","http.route":"/charge","http.status_code":502,"duration_ms":812,"order.id":"o-1934","exception.type":"UpstreamError","exception.message":"gateway 502"}`

Propagate across services with the W3C header:
`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`

These structured keys become the query fields downstream (filter on `http.status_code>=500`, `trace_id`, `exception.type`) — see lore/deep/logging.md#what-to-log-and-where and the platform's query lore. Framework specifics (field binding, MDC/contextvars, JSON encoders) live in the per-language log lore (e.g. lore/slog.md).

### Sources
- opentelemetry.io/docs/specs/otel/logs/data-model
- w3.org/TR/trace-context
- 12factor.net/logs
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs

## Errors & Exceptions <a id="errors-and-exceptions"></a>

Align to OpenTelemetry exception semantics (record exceptions as `LogRecord` attributes) and 12-factor (write an event stream to stdout; don't manage restarts or log files). Complements per-language framework lore (e.g. lore/slog.md). An error log's job: let someone find it, understand what failed, recover.

### DO
- Log an exception ONCE, at the boundary where it becomes a real outcome (request handler, job runner, top-level handler) — not at every `catch` as it unwinds. Either handle-and-log OR wrap-with-context-and-rethrow; never both.
- Emit a structured error event with OTel stable attributes: `exception.type` (fully-qualified class), `exception.message`, `exception.stacktrace`. At least one of type/message is required. Set SeverityNumber ERROR (17–20); reserve FATAL (21–24) for process-ending failures.
- Attach the trace id (`trace_id`/`span_id`), operation name, and sanitized inputs so the failure is reproducible and searchable — see lore/deep/logging.md#structured-and-correlation.
- Make it actionable: what failed, the effect (retried? user-facing?), a recovery hint.
- Pick level by intent: expected/handled degradation = WARN; unhandled fault or violated invariant = ERROR; unrecoverable = FATAL then exit — see lore/deep/logging.md#levels-and-environments.
- Install top-level handlers (uncaught exception / unhandled promise rejection / panic recover): log ONE FATAL event with the stack, then exit — let the platform restart the process (12-factor).
- Preserve the cause chain when wrapping — include the root cause's type and message, not just the wrapper.
- For retries, log the final give-up at ERROR with `attempt`/`max_attempts`; keep intermediate retries at WARN/DEBUG.

### DON'T
- Don't swallow exceptions (empty `catch`, bare `except: pass`) or log at DEBUG and continue as if fine.
- Don't log-and-rethrow — it duplicates stack traces and inflates error counts/alerts.
- Don't put secrets or PII into `exception.message`, stack frames, or arg dumps; scrub first — see lore/deep/logging.md#security-and-pii.
- Don't flatten an error into a concatenated string that loses type/fields; keep it structured.
- Don't log expected client errors (validation, 404, 4xx) at ERROR — noise drowns real faults.

### Gotchas
- OTel flags `exception.message` as potentially sensitive — assume it may leak and scrub before emit.
- Stack traces are multi-line: ensure the appender writes ONE record (multiline handling / escaped `\n` in JSON) so aggregation counts one event, not N.
- Stable grouping needs a stable template: keep the string constant, push varying values into attributes, so backends fingerprint errors correctly.

### Finding them later (each valid in its own query language)
- CloudWatch Logs Insights — errors/hour:
  `filter @message like /Exception/ | stats count(*) as n by bin(1h) | sort n desc`
- Grafana Loki (LogQL) — error rate by level:
  `sum by (level) (count_over_time({app="checkout"} | json | level="error" [5m]))`
- Google Cloud Logging — one exception type:
  `resource.type="k8s_container" AND severity>="ERROR" AND jsonPayload.exception.type="TimeoutError"`

### Sources
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs · specs/otel/logs/data-model
- 12factor.net/logs
- docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-examples.html
- grafana.com/docs/loki/latest/query/log_queries · docs.cloud.google.com/logging/docs/view/logging-query-language

## Security and PII <a id="security-and-pii"></a>

Aligns to OpenTelemetry logs + 12-factor. OTel has **no built-in PII/secret protection** — redact at emit, then defense-in-depth (emit→collector→store→access); can't un-leak stored data.

### Never log (OWASP)
- **Secrets:** passwords, access/refresh/session tokens, API keys, private keys, DB connection strings.
- **Regulated data:** full PAN/card & bank numbers (PCI); government IDs (SSN, passport); health (PHI); biometrics.
- **Mask/pseudonymize:** email, phone, name, IP/MAC, file paths, internal hostnames.
- **Reference, not value:** `user_id`/keyed hash not email; card `last4` not PAN; token *fingerprint* (HMAC) not the token.

### Emit safely
- **Allow-list beats deny-list** — log only known-safe fields; a blocklist misses the next new field. `redaction` fails closed: empty `allowed_keys` drops every attribute.
- **Structured (JSON)** redacts by *key*; regex over free text is fragile and leaks.
- **Pseudonymize (HMAC + secret):** plain `md5`/`sha1` of low-entropy PII is reversible by lookup; HMAC correlates a subject without exposing identity.
- **Never** put PII/secrets in the message, span names, URLs/query strings, or **metric labels**.

### Pipeline redaction (each platform's own language)
- **OTel `redactionprocessor`:** `allowed_keys` (retained); `blocked_values` (regex → asterisks, or hashed via `hash_function` e.g. `hmac-sha256` + `hmac_key`); `allowed_values` beats blocked. Unlisted keys dropped first.
- **AWS CloudWatch data protection policy:** managed data identifiers (Credentials/Financial/PII/PHI/Device) + custom; masked at **all egress** (Logs Insights, metric filters); only `logs:Unmask` IAM views. Masks only data ingested **after** it's set.
- **Azure Monitor DCR transformation (KQL):** drop `source | project-away ClientIP`; obfuscate `source | extend Email = replace(Email, substring(Email,0,indexof(Email,"@")), "*****")`; or route sensitive rows to an RBAC-restricted table.
- **GCP, Grafana/Loki, Splunk, Dynatrace:** redact at the agent/collector; see each platform's lore.

### Injection & integrity (CWE-117)
- **Sanitize untrusted values** — strip/encode CR/LF so an attacker can't forge log lines; JSON encoding neutralizes this. Validate cross-trust-zone input.
- **Protect logs:** TLS in transit, least-privilege + audited *read* access, tamper detection, write-only DB sink.

### Compliance & retention
- **Classify, minimize, expire:** never log data above the store's clearance; PII must be GDPR-deletable — set short retention TTLs; honor opt-out.

### DON'T
- Rely solely on downstream masking.
- Log full request/response bodies or `Authorization`/`Cookie`/`Set-Cookie` headers verbatim.
- Emit stack traces/exception attrs unscrubbed — they capture locals, args, SQL (lore/deep/logging.md#errors-and-exceptions).
- Leave DEBUG on in prod (lore/deep/logging.md#levels-and-environments); or disable TLS to the backend.

### Sources
- cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- opentelemetry.io/docs/specs/otel/logs/data-model · collector-contrib redactionprocessor
- docs.aws.amazon.com/AmazonCloudWatch/latest/logs/mask-sensitive-log-data.html
- learn.microsoft.com/azure/azure-monitor/data-collection/data-collection-transformations-kql

## Sampling & performance <a id="sampling-and-performance"></a>

Platform- & language-agnostic; aligned to OpenTelemetry logs + 12-factor "logs are event streams". Complements per-language framework lore (lore/slog.md). Goal: cheap, high-signal logging that still keeps the events you need to debug.

### Emit without blocking — DO / DON'T
DO write the stream **unbuffered to stdout/stderr**; let the platform (k8s, systemd, agent) collate/route/store — the app never manages files, rotation, or shipping (12-factor XI).
DO batch the *export* off the request path: OTel **BatchLogRecordProcessor** queues + flushes on a timer (defaults `maxQueueSize=2048`, `scheduledDelay=1000ms`, `maxExportBatchSize=512`, `exportTimeout=30000ms`). Use **SimpleLogRecordProcessor** (synchronous) only in tests.
DO bound the queue and **drop on overflow, never block** — OTel drops records once `maxQueueSize` is reached; a slow/broken sink must not stall business logic.
DON'T do blocking network/disk I/O inside a log call, or flush per-record in prod.

### Keep call sites cheap — DO / DON'T
DO check the level *before* building the payload — args to a dropped log are wasted work; guard costly fields (`isEnabled(DEBUG)`) or pass lazy values.
DO log **structured key/values**, not pre-formatted strings — no `sprintf`/JSON concat on hot paths.
DON'T log inside tight loops or per-row — emit one aggregate event (count, duration) after.
DON'T serialize large bodies/objects at INFO; summarize (id, size, status).

### Sample deliberately — DO / DON'T
DO prefer **head sampling** for volume — cheap, decided up front. Deterministic/consistent sampling keyed on the **trace id** keeps whole traces intact at a fixed rate (OTel `TraceIdRatioBased{RATIO}`, e.g. 0.1 = 10%).
DO **rate-limit repetitive lines** (log first N, then 1-in-M) so a retry storm can't flood the sink.
DO leave **tail sampling** (keep-if-error/slow, decided after the trace ends) to the collector — stateful, needs the whole trace.
DON'T sample away ERROR/WARN — keep 100%; sample only high-volume success/DEBUG.
DON'T sample logs and traces independently — a log kept for a dropped trace has no context.

### Follow the trace's decision — DO
DO stamp `trace_id`/`span_id` and honor the **TraceFlags SAMPLED bit**. OTel trace-based log filtering drops a record whose `SpanId` is valid but whose `TraceFlags` mark the trace unsampled. Use `ParentBased(root=TraceIdRatioBased(r))` so children inherit the root's flag instead of re-rolling per span.

### Measure before you cut — DO
DO set sampling rates from real volume; reconstruct real counts by scaling by 1/rate.
Volume by time bucket (CloudWatch Logs Insights):
```
fields @timestamp, level | filter level="ERROR" | stats count(*) by bin(5m)
```
Error rate over a low-cardinality stream (Grafana Loki / LogQL):
```
sum(rate({namespace="prod", app="checkout"} |= "error" [5m]))
```
DON'T index high-cardinality values (user/request id) as labels/dimensions — Loki advises "Prefer fewer labels, which have bounded values" (aim ≤10–15); filter on the line (`|= "..."`) instead — high cardinality explodes index/stream cost.

### Sources
- https://opentelemetry.io/docs/specs/otel/logs/sdk/
- https://opentelemetry.io/docs/concepts/sampling/
- https://12factor.net/logs
- https://opentelemetry.io/docs/specs/otel/trace/sdk/
- https://grafana.com/docs/loki/latest/get-started/labels/
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html

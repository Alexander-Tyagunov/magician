# Logging (principles) — Sampling & performance

Platform- & language-agnostic; aligned to OpenTelemetry logs + 12-factor "logs are event streams". Complements per-language framework lore (lore/slog). Goal: cheap, high-signal logging that still keeps the events you need to debug.

## Emit without blocking — DO / DON'T
DO write the stream **unbuffered to stdout/stderr**; let the platform (k8s, systemd, agent) collate/route/store — the app never manages files, rotation, or shipping (12-factor XI).
DO batch the *export* off the request path: OTel **BatchLogRecordProcessor** queues + flushes on a timer (defaults `maxQueueSize=2048`, `scheduledDelay=1000ms`, `maxExportBatchSize=512`, `exportTimeout=30000ms`). Use **SimpleLogRecordProcessor** (synchronous) only in tests.
DO bound the queue and **drop on overflow, never block** — OTel drops records once `maxQueueSize` is reached; a slow/broken sink must not stall business logic.
DON'T do blocking network/disk I/O inside a log call, or flush per-record in prod.

## Keep call sites cheap — DO / DON'T
DO check the level *before* building the payload — args to a dropped log are wasted work; guard costly fields (`isEnabled(DEBUG)`) or pass lazy values.
DO log **structured key/values**, not pre-formatted strings — no `sprintf`/JSON concat on hot paths.
DON'T log inside tight loops or per-row — emit one aggregate event (count, duration) after.
DON'T serialize large bodies/objects at INFO; summarize (id, size, status).

## Sample deliberately — DO / DON'T
DO prefer **head sampling** for volume — cheap, decided up front. Deterministic/consistent sampling keyed on the **trace id** keeps whole traces intact at a fixed rate (OTel `TraceIdRatioBased{RATIO}`, e.g. 0.1 = 10%).
DO **rate-limit repetitive lines** (log first N, then 1-in-M) so a retry storm can't flood the sink.
DO leave **tail sampling** (keep-if-error/slow, decided after the trace ends) to the collector — stateful, needs the whole trace.
DON'T sample away ERROR/WARN — keep 100%; sample only high-volume success/DEBUG.
DON'T sample logs and traces independently — a log kept for a dropped trace has no context.

## Follow the trace's decision — DO
DO stamp `trace_id`/`span_id` and honor the **TraceFlags SAMPLED bit**. OTel trace-based log filtering drops a record whose `SpanId` is valid but whose `TraceFlags` mark the trace unsampled. Use `ParentBased(root=TraceIdRatioBased(r))` so children inherit the root's flag instead of re-rolling per span.

## Measure before you cut — DO
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

## Sources
- https://opentelemetry.io/docs/specs/otel/logs/sdk/
- https://opentelemetry.io/docs/concepts/sampling/
- https://12factor.net/logs
- https://opentelemetry.io/docs/specs/otel/trace/sdk/
- https://grafana.com/docs/loki/latest/get-started/labels/
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html

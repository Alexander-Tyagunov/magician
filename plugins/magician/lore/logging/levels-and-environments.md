# Logging (principles) — Levels & Environments

Pick the level by INTENT, the threshold by ENVIRONMENT. Align names to OpenTelemetry SeverityNumber so
backends normalize and range-filter ("smaller numerical values correspond to less severe events";
SeverityNumber >= 17 signals an error).

## Choose level by intent (OTel SeverityNumber)
- TRACE (1) — ultra-fine step-by-step; off outside deep debugging.
- DEBUG (5) — developer diagnostics: values, branch chosen, cache hit/miss.
- INFO (9) — a normal thing worth recording: request handled, job done, state change.
- WARN (13) — recoverable/degraded: retry, fallback, deprecated path, near-limit; app keeps working.
- ERROR (17) — an operation failed, needs attention; include full context.
- FATAL (21) — process cannot continue; emit, then exit non-zero.
Map your framework to these so severity survives export: e.g. Log4j/logback ERROR->17, FATAL->21; .NET
Critical->21. Emit BOTH SeverityText and SeverityNumber; backends filter the number, humans read text.

## Set the threshold by ENVIRONMENT (never hardcode)
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

## Gotchas
- Threshold is inclusive-upward: `LOG_LEVEL=warn` emits WARN+ERROR+FATAL, suppresses INFO/DEBUG. Verify the
  boundary; off-by-one silences alerts.
- Guard DEBUG payloads behind `isDebugEnabled()`/lazy args so string-building doesn't run above DEBUG.
- Don't over-use WARN: one nobody acts on trains responders to ignore them. If it needs action it's ERROR;
  if noteworthy-normal, INFO.
- One env, one meaning: don't make prod quieter by changing what INFO *means* — change the THRESHOLD, not
  individual events.

Match the deploy platform for shape + queries (see lore/{dynatrace,grafana,splunk,gcp-logging,cloudwatch,
azure-monitor}.md), keep events structured (lore/logging/structured-and-correlation.md), and make failures
actionable (lore/logging/errors-and-exceptions.md).

## Sources
opentelemetry.io/docs/specs/otel/logs/data-model · /logs/data-model-appendix · 12factor.net/logs

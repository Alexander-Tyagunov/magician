# Logging (principles) — Errors & Exceptions

Align to OpenTelemetry exception semantics (record exceptions as `LogRecord` attributes) and 12-factor (write an event stream to stdout; don't manage restarts or log files). Complements per-language framework lore (e.g. lore/slog). An error log's job: let someone find it, understand what failed, recover.

## DO
- Log an exception ONCE, at the boundary where it becomes a real outcome (request handler, job runner, top-level handler) — not at every `catch` as it unwinds. Either handle-and-log OR wrap-with-context-and-rethrow; never both.
- Emit a structured error event with OTel stable attributes: `exception.type` (fully-qualified class), `exception.message`, `exception.stacktrace`. At least one of type/message is required. Set SeverityNumber ERROR (17–20); reserve FATAL (21–24) for process-ending failures.
- Attach the trace id (`trace_id`/`span_id`), operation name, and sanitized inputs so the failure is reproducible and searchable — see lore/logging/structured-and-correlation.md.
- Make it actionable: what failed, the effect (retried? user-facing?), a recovery hint.
- Pick level by intent: expected/handled degradation = WARN; unhandled fault or violated invariant = ERROR; unrecoverable = FATAL then exit — see lore/logging/levels-and-environments.md.
- Install top-level handlers (uncaught exception / unhandled promise rejection / panic recover): log ONE FATAL event with the stack, then exit — let the platform restart the process (12-factor).
- Preserve the cause chain when wrapping — include the root cause's type and message, not just the wrapper.
- For retries, log the final give-up at ERROR with `attempt`/`max_attempts`; keep intermediate retries at WARN/DEBUG.

## DON'T
- Don't swallow exceptions (empty `catch`, bare `except: pass`) or log at DEBUG and continue as if fine.
- Don't log-and-rethrow — it duplicates stack traces and inflates error counts/alerts.
- Don't put secrets or PII into `exception.message`, stack frames, or arg dumps; scrub first — see lore/logging/security-and-pii.md.
- Don't flatten an error into a concatenated string that loses type/fields; keep it structured.
- Don't log expected client errors (validation, 404, 4xx) at ERROR — noise drowns real faults.

## Gotchas
- OTel flags `exception.message` as potentially sensitive — assume it may leak and scrub before emit.
- Stack traces are multi-line: ensure the appender writes ONE record (multiline handling / escaped `\n` in JSON) so aggregation counts one event, not N.
- Stable grouping needs a stable template: keep the string constant, push varying values into attributes, so backends fingerprint errors correctly.

## Finding them later (each valid in its own query language)
- CloudWatch Logs Insights — errors/hour:
  `filter @message like /Exception/ | stats count(*) as n by bin(1h) | sort n desc`
- Grafana Loki (LogQL) — error rate by level:
  `sum by (level) (count_over_time({app="checkout"} | json | level="error" [5m]))`
- Google Cloud Logging — one exception type:
  `resource.type="k8s_container" AND severity>="ERROR" AND jsonPayload.exception.type="TimeoutError"`

## Sources
- opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs · specs/otel/logs/data-model
- 12factor.net/logs
- docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax-examples.html
- grafana.com/docs/loki/latest/query/log_queries · docs.cloud.google.com/logging/docs/view/logging-query-language

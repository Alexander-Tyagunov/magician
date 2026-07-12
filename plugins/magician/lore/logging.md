# Logging (principles) — core digest
OpenTelemetry + 12-factor: app emits events; platform routes/stores. Levels TRACE<DEBUG<INFO<WARN<ERROR<FATAL; carry trace_id/span_id.

DO set level by intent (DEBUG=diag, INFO=state, WARN=recoverable, ERROR=failure, FATAL=crash); threshold by ENVIRONMENT (dev DEBUG, prod INFO/WARN), configurable not hardcoded.
DO log meaningful points: requests in/out (outcome+duration), external calls+results, state changes, key branches.
DO emit ONE structured event (JSON, stable fields) per logical action, tagged with a correlation/request id across the flow.
DO write to stdout/stderr unbuffered; the platform aggregates — no in-app files/rotation.
DO make errors actionable: what failed, inputs (secrets stripped), cause/stack, recovery.

DON'T log secrets, tokens, credentials, or PII — redact/hash first.
DON'T log in hot loops or line-by-line; one event per action, sample noise.
DON'T use print/console, hide context in a message string, or let logging throw/block/swallow.

Match the platform — shape logs for it, query in ITS language; the Observability note names it (ask+record if unknown): lore/{dynatrace,grafana,splunk,gcp-logging,cloudwatch,azure-monitor}.md.

Deep-dive: lore/logging/{levels-and-environments,what-to-log-and-where,structured-and-correlation,errors-and-exceptions,security-and-pii,sampling-and-performance}.md

## Sources
opentelemetry.io logs/data-model + signals/logs; 12factor.net/logs

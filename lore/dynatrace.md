# Dynatrace — core digest
SaaS; query logs in DQL (Dynatrace Query Language) over Grail — both GA. Ingest via OneAgent, OTLP, or Log API; parse/mask/route at ingest with OpenPipeline.

DO emit structured JSON (OneAgent auto-ingests stdout/file) or push OTLP; parse/enrich/mask at ingest via OpenPipeline.
DO map severity to `loglevel` (ERROR/WARN/INFO/DEBUG); set the threshold by env (DEBUG dev, INFO/WARN prod), env-configurable.
DO propagate trace context so logs carry `dt.trace_id`/`dt.span_id` — links logs to spans/traces.
DO query with the pipeline: `fetch logs | filter loglevel == "ERROR" | sort timestamp desc | limit 100`.
DO full-text via token-indexed `matchesPhrase(content,"timeout")`; `parse content,"…"` (DPL) lifts fields.
DO aggregate/trend: `summarize count(), by:{status}` and `makeTimeseries count(), by:{loglevel}, interval:5m`.

DON'T write SQL/SPL/KQL/LogQL — DQL has no SELECT/WHERE; it's `fetch | filter | summarize | makeTimeseries`.
DON'T run bare `fetch logs` — bound with timeframe + filter; Grail bills by bytes scanned.
DON'T log secrets/PII/tokens; mask at ingest if unavoidable.
DON'T hardcode threshold or over-log hot loops — one structured event per action.

Deep dive when writing non-trivial Dynatrace — read lore/dynatrace/{dql-log-queries,log-ingestion-and-attributes,problems-and-alerting}.md

## Sources
docs.dynatrace.com/docs — DQL commands & functions (summarize, makeTimeseries, matchesPhrase) · Grail ingestion, OpenPipeline

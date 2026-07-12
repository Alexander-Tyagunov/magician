# Dynatrace — Log ingestion and attributes

Context: Dynatrace SaaS; DQL (Dynatrace Query Language) over Grail is GA and the only current log query language (Classic log search / USQL are legacy). Ingest via OneAgent, OpenTelemetry (OTLP), or the Log Monitoring API v2.

## Grail model: buckets, tables, fields
Grail stores records in **buckets**, exposed via **tables** (fetch a table = read all its buckets). Logs use table `logs`; built-in bucket `default_logs` retains **35 days** and can't be modified. Create user buckets with custom retention to split noisy debug (short) from audit (long). List them: `fetch dt.system.buckets`.

Top-level log fields (Semantic Dictionary): `timestamp` (Unix epoch ns), `content` (raw message body), `status` (normalized severity `ERROR`/`WARN`/`INFO`/`NONE`), `loglevel` (source-reported level string), `log.source`, `dt.entity.host`, `dt.entity.process_group_instance`, `trace_id`, `span_id`, `dt.security_context`. Everything else you send (OTel attributes, parsed fields) becomes a **log attribute**. Prefer `status` for cross-source severity filters; `loglevel` varies per emitter.

## Ingestion paths
- **OneAgent** — auto-discovers log files; enriches records with topology (`dt.entity.*`) and, for instrumented processes, `trace_id`/`span_id` for log↔trace correlation.
- **OTLP** — POST to `https://{env-id}.live.dynatrace.com/api/v2/otlp/v1/logs`, header `Authorization: Api-Token dt0c01.…`, scope `logs.ingest`. Use `http/protobuf` only (gRPC/JSON unsupported); strip `.apps` from the env id or you get 404. Resource attrs → resource fields; record attrs → log attributes.
- **Log Monitoring API v2 / Fluent Bit / Fluentd** — hosts without OneAgent.

## DQL queries (valid on Grail)
Recent errors:
```
fetch logs | filter status == "ERROR" | sort timestamp desc | limit 100
```
Phrase search (token-based, index-friendly):
```
fetch logs | filter loglevel == "ERROR" and matchesPhrase(content, "connection refused")
```
Trace one request end-to-end:
```
fetch logs | filter trace_id == "a1b2c3..." | sort timestamp asc
```
Error rate over time:
```
fetch logs | filter status == "ERROR" | makeTimeseries count(), interval: 5m
```
Parse a field from `content`, normalize severity:
```
fetch logs
| parse content, "LD 'took=' INT:duration_ms 'ms'"
| fieldsAdd severity = if(status == "NONE", "INFO", else: status)
| fields timestamp, severity, duration_ms, content
```

## DO
- DO emit JSON logs; ship OTel `trace_id`/`span_id` (or let OneAgent inject) so logs join spans.
- DO set `status`/severity so `filter status == "ERROR"` works across every source.
- DO scope every query with a tight timeframe + `limit`; widen only as needed.

## DON'T
- DON'T ingest secrets/PII/tokens — Grail is queryable and retained; scrub at source or via processing rules.
- DON'T rely on legacy log search/USQL — write for DQL.
- DON'T send OTLP as gRPC/JSON to SaaS; use `http/protobuf`.

See also: lore/dynatrace/dql-log-queries.md, lore/dynatrace/problems-and-alerting.md.

## Sources
- docs.dynatrace.com — grail/data-model (buckets/tables, default_logs 35d)
- docs.dynatrace.com — dynatrace-query-language/commands (aggregation, filtering, fields, parse)
- docs.dynatrace.com — ingest-from/opentelemetry (OTLP `/api/v2/otlp/v1/logs`, `logs.ingest`)
- docs.dynatrace.com — references/semantic-dictionary (log fields)

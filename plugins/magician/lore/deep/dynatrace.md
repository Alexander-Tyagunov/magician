# Dynatrace — deep dive

> On-demand companion to `lore/dynatrace.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [DQL log queries](#dql-log-queries) · [Log ingestion and attributes](#log-ingestion-and-attributes) · [Problems & Alerting](#problems-and-alerting)

## DQL log queries <a id="dql-log-queries"></a>

DQL (Dynatrace Query Language) over Grail (Dynatrace's observability data lakehouse) — SaaS, GA. Logs arrive via OneAgent or OpenTelemetry (OTLP). Fields: `timestamp`, `content` (message), `loglevel`/`status` (ERROR/WARN/INFO/NONE), plus resource & log attributes (`dt.entity.service`, `k8s.namespace.name`, `service.name`, `trace_id`, `span_id`, any ingested JSON keys). Verify commands/functions at docs.dynatrace.com first.

### Pipeline model
DQL is a pipe: `fetch <source> | <command> | …`. Start with `fetch logs`, scope the timeframe on fetch, then filter, reduce fields, aggregate LAST.

DO scope every query: `fetch logs, from:-2h` (or `from: now()-24h, to: now()`), or use the UI timeframe — unbounded scans are slow and costly.
DO filter early on raw fields; case-insensitive substring via `~`, `matchesPhrase()`, or `matchesValue()` (wildcards `*`); literal substring via `contains()`.
DO reduce columns early with `fields`/`fieldsKeep`/`fieldsRemove`, then aggregate with `summarize` / `makeTimeseries`.
DO cap cost on wide ranges: `fetch logs, scanLimitGBytes:500, samplingRatio:100, bucket:{"default_logs"}`.
DO use `countIf()` for error-rate math and `by:{…}` to group.
DON'T `sort` right after fetch, or `limit` before `summarize` — both give wrong/slow results; sort/limit last.
DON'T negate when you can include (`filter loglevel=="ERROR"` beats `filter not …`).
DON'T use reserved words (`and or not null true false mod`) as bare field names — wrap in backticks.

### Find errors
```
fetch logs, from:-2h
| filter loglevel == "ERROR" or matchesPhrase(content, "exception")
| sort timestamp desc
| limit 100
```
Errors by service, worst first:
```
fetch logs, from:-24h
| filter loglevel == "ERROR"
| summarize errors = count(), by:{ dt.entity.service, k8s.namespace.name }
| sort errors desc
| limit 20
```
Error rate + total per service:
```
fetch logs, from:-1h
| summarize errors = countIf(loglevel == "ERROR"), total = count(), by:{ service.name }
| fieldsAdd error_pct = errors * 100.0 / total
| sort error_pct desc
```

### Trace one request
Correlate by trace id (OTel) or a propagated correlation attribute:
```
fetch logs, from:-6h
| filter trace_id == "0af7651916cd43dd8448eb211c80319c"
| sort timestamp asc
| fields timestamp, loglevel, dt.entity.service, content
```

### Error trend over time
```
fetch logs, from:-6h
| filter loglevel == "ERROR"
| makeTimeseries count(default: 0), interval: 5m, by:{ k8s.namespace.name }
```

### Extract fields from unstructured content
`parse` uses the Dynatrace Pattern Language (`LD` line-data, `INT`/`LONG`, `IPADDR`, `HTTPDATE`, `DQS`); assign with `MATCHER:field`:
```
fetch logs, from:-3h
| filter matchesPhrase(content, "status")
| parse content, "LD 'status=' INT:http_status LD 'dur=' INT:ms LD"
| filter http_status >= 500
| summarize slow = avg(ms), by:{ http_status }
```
`search` is the quick token search (case-insensitive): `fetch logs | search content ~ "*timeout*"`.

### Cross-references
Ingestion, attributes, buckets, retention → lore/deep/dynatrace.md#log-ingestion-and-attributes. Alerting on error queries → lore/deep/dynatrace.md#problems-and-alerting.

### Sources
- docs.dynatrace.com/docs/discover-dynatrace/platform/grail/dynatrace-query-language/commands/aggregation-commands (+ filtering-commands, extraction-and-parsing-commands)
- .../dynatrace-query-language/dql-best-practices · functions/string-functions

## Log ingestion and attributes <a id="log-ingestion-and-attributes"></a>

Context: Dynatrace SaaS; DQL (Dynatrace Query Language) over Grail is GA and the only current log query language (Classic log search / USQL are legacy). Ingest via OneAgent, OpenTelemetry (OTLP), or the Log Monitoring API v2.

### Grail model: buckets, tables, fields
Grail stores records in **buckets**, exposed via **tables** (fetch a table = read all its buckets). Logs use table `logs`; built-in bucket `default_logs` retains **35 days** and can't be modified. Create user buckets with custom retention to split noisy debug (short) from audit (long). List them: `fetch dt.system.buckets`.

Top-level log fields (Semantic Dictionary): `timestamp` (Unix epoch ns), `content` (raw message body), `status` (normalized severity `ERROR`/`WARN`/`INFO`/`NONE`), `loglevel` (source-reported level string), `log.source`, `dt.entity.host`, `dt.entity.process_group_instance`, `trace_id`, `span_id`, `dt.security_context`. Everything else you send (OTel attributes, parsed fields) becomes a **log attribute**. Prefer `status` for cross-source severity filters; `loglevel` varies per emitter.

### Ingestion paths
- **OneAgent** — auto-discovers log files; enriches records with topology (`dt.entity.*`) and, for instrumented processes, `trace_id`/`span_id` for log↔trace correlation.
- **OTLP** — POST to `https://{env-id}.live.dynatrace.com/api/v2/otlp/v1/logs`, header `Authorization: Api-Token dt0c01.…`, scope `logs.ingest`. Use `http/protobuf` only (gRPC/JSON unsupported); strip `.apps` from the env id or you get 404. Resource attrs → resource fields; record attrs → log attributes.
- **Log Monitoring API v2 / Fluent Bit / Fluentd** — hosts without OneAgent.

### DQL queries (valid on Grail)
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

### DO
- DO emit JSON logs; ship OTel `trace_id`/`span_id` (or let OneAgent inject) so logs join spans.
- DO set `status`/severity so `filter status == "ERROR"` works across every source.
- DO scope every query with a tight timeframe + `limit`; widen only as needed.

### DON'T
- DON'T ingest secrets/PII/tokens — Grail is queryable and retained; scrub at source or via processing rules.
- DON'T rely on legacy log search/USQL — write for DQL.
- DON'T send OTLP as gRPC/JSON to SaaS; use `http/protobuf`.

See also: lore/deep/dynatrace.md#dql-log-queries, lore/deep/dynatrace.md#problems-and-alerting.

### Sources
- docs.dynatrace.com — grail/data-model (buckets/tables, default_logs 35d)
- docs.dynatrace.com — dynatrace-query-language/commands (aggregation, filtering, fields, parse)
- docs.dynatrace.com — ingest-from/opentelemetry (OTLP `/api/v2/otlp/v1/logs`, `logs.ingest`)
- docs.dynatrace.com — references/semantic-dictionary (log fields)

## Problems & Alerting <a id="problems-and-alerting"></a>

Context: Dynatrace SaaS (Gen3), Grail + DQL GA. Davis AI correlates raw events into **problems** (root-cause + impact). Query them in DQL over Grail (`dt.davis.problems`, `dt.davis.events`); alert via **metric events** and the **Anomaly Detection** app (DQL-based). Log search is separate — see lore/deep/dynatrace.md#dql-log-queries and lore/deep/dynatrace.md#log-ingestion-and-attributes.

DO make error logs alert-worthy: distinct `loglevel` (ERROR/WARN), stable text, correlation ids, `dt.entity.*` — so a log-event rule matches and the problem carries context.
DO prefer Davis auto-adaptive/seasonal baselines for noisy signals; reserve static thresholds for hard SLOs.
DO scope every alert to an entity so Davis maps it to the right host/service and merges into one problem.
DO query problems by `event.status`, de-noising with Davis flags.
DON'T alert per log line or per hot-loop metric — duplicate problems; alert on a rate/threshold and let Davis correlate.
DON'T invent fields: problems use `event.id`, `display_id`, `event.status`, `event.kind`, `event.type`, `event.start`, `event.end`, `resolved_problem_duration`, `smartscape.affected_entities`.
DON'T mix SPL/KQL/LogQL/Insights syntax into DQL — pipe with `|`; use `filter`/`summarize`/`makeTimeseries`.

### Query problems (DQL over Grail)
```
// active problems, drop duplicates
fetch dt.davis.problems
| filter event.status == "ACTIVE" and not(dt.davis.is_duplicate)
| summarize activeProblems = countDistinct(event.id)

// one problem by its stable display id
fetch dt.davis.problems | filter display_id == "P-24051200"

// MTTR (h) for closed, real problems over 7d
fetch dt.davis.problems, from:now()-7d
| filter event.status == "CLOSED" and dt.davis.is_frequent_event == false and dt.davis.is_duplicate == false
| makeTimeseries `AVG hours` = avg(toLong(resolved_problem_duration)/3600000000000.0), time:event.end
```
Gotcha: Davis flags (`dt.davis.is_duplicate`, `dt.davis.is_frequent_event`) are **booleans** — use `not(flag)` or `== false`, never the string `"true"`.

### Query raw events feeding a problem
```
fetch dt.davis.events, from:now()-7d
| filter event.kind == "DAVIS_EVENT"
| filter event.type == "OSI_HIGH_CPU" or event.type == "OSI_HIGH_MEMORY"
| makeTimeseries count = count(default:0)
```
`event.kind` splits Davis-detected vs custom/info; `event.type` is the detector.

### Configure alerting
- **Metric events**: *static threshold* (fixed SLO), *auto-adaptive* (Davis learns), or *seasonal baseline* (daily/weekly band). Auto-adaptive/seasonal need a **metric-selector** event (metric-key events are static-only). Add entity dims (e.g. `dt.entity.host=HOST-123`) so it hits the right entity; Davis picks the most specific (process > host) into one problem.
- **Log alerting**: configure a **log event** with a rate/window-based DQL matcher (e.g. `filter loglevel == "ERROR"`); a match raises a custom event that opens/updates a Davis problem and notifies. Keep it specific to avoid duplicates.

### Sources
- docs.dynatrace.com — Davis for Grail (problems/events DQL); Semantic Dictionary (dt.davis.* types)
- docs.dynatrace.com — DQL commands (fetch/filter/summarize/makeTimeseries), operators (`not`)
- docs.dynatrace.com — Anomaly detection: metric events; log events

# Dynatrace — DQL log queries

DQL (Dynatrace Query Language) over Grail (Dynatrace's observability data lakehouse) — SaaS, GA. Logs arrive via OneAgent or OpenTelemetry (OTLP). Fields: `timestamp`, `content` (message), `loglevel`/`status` (ERROR/WARN/INFO/NONE), plus resource & log attributes (`dt.entity.service`, `k8s.namespace.name`, `service.name`, `trace_id`, `span_id`, any ingested JSON keys). Verify commands/functions at docs.dynatrace.com first.

## Pipeline model
DQL is a pipe: `fetch <source> | <command> | …`. Start with `fetch logs`, scope the timeframe on fetch, then filter, reduce fields, aggregate LAST.

DO scope every query: `fetch logs, from:-2h` (or `from: now()-24h, to: now()`), or use the UI timeframe — unbounded scans are slow and costly.
DO filter early on raw fields; case-insensitive substring via `~`, `matchesPhrase()`, or `matchesValue()` (wildcards `*`); literal substring via `contains()`.
DO reduce columns early with `fields`/`fieldsKeep`/`fieldsRemove`, then aggregate with `summarize` / `makeTimeseries`.
DO cap cost on wide ranges: `fetch logs, scanLimitGBytes:500, samplingRatio:100, bucket:{"default_logs"}`.
DO use `countIf()` for error-rate math and `by:{…}` to group.
DON'T `sort` right after fetch, or `limit` before `summarize` — both give wrong/slow results; sort/limit last.
DON'T negate when you can include (`filter loglevel=="ERROR"` beats `filter not …`).
DON'T use reserved words (`and or not null true false mod`) as bare field names — wrap in backticks.

## Find errors
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

## Trace one request
Correlate by trace id (OTel) or a propagated correlation attribute:
```
fetch logs, from:-6h
| filter trace_id == "0af7651916cd43dd8448eb211c80319c"
| sort timestamp asc
| fields timestamp, loglevel, dt.entity.service, content
```

## Error trend over time
```
fetch logs, from:-6h
| filter loglevel == "ERROR"
| makeTimeseries count(default: 0), interval: 5m, by:{ k8s.namespace.name }
```

## Extract fields from unstructured content
`parse` uses the Dynatrace Pattern Language (`LD` line-data, `INT`/`LONG`, `IPADDR`, `HTTPDATE`, `DQS`); assign with `MATCHER:field`:
```
fetch logs, from:-3h
| filter matchesPhrase(content, "status")
| parse content, "LD 'status=' INT:http_status LD 'dur=' INT:ms LD"
| filter http_status >= 500
| summarize slow = avg(ms), by:{ http_status }
```
`search` is the quick token search (case-insensitive): `fetch logs | search content ~ "*timeout*"`.

## Cross-references
Ingestion, attributes, buckets, retention → lore/dynatrace/log-ingestion-and-attributes.md. Alerting on error queries → lore/dynatrace/problems-and-alerting.md.

## Sources
- docs.dynatrace.com/docs/discover-dynatrace/platform/grail/dynatrace-query-language/commands/aggregation-commands (+ filtering-commands, extraction-and-parsing-commands)
- .../dynatrace-query-language/dql-best-practices · functions/string-functions

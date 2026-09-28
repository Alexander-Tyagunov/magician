# Azure Monitor — deep dive

> On-demand companion to `lore/azure-monitor.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [KQL Log Queries](#kql-log-queries) · [Application Insights & Ingestion](#app-insights-and-ingestion) · [Workspaces & Alerts](#workspaces-and-alerts)

## KQL Log Queries <a id="kql-log-queries"></a>

Azure Monitor Logs stores data in a Log Analytics workspace as typed tables; you query it with KQL (Kusto Query Language). Workspace-based Application Insights writes to Logs tables: AppRequests, AppDependencies, AppExceptions, AppTraces, AppPageViews, AppEvents, AppMetrics (verified 2026 at learn.microsoft.com). KQL is case-sensitive; keywords are lowercase; table/column names must match the schema pane exactly.

### Query shape
Start with a table name (scopes the query + is fast), pipe `|` into operators, put the time filter first.
```kusto
AppRequests
| where TimeGenerated > ago(1h)
| where Success == false
| project TimeGenerated, Name, ResultCode, DurationMs, OperationId
| top 50 by TimeGenerated desc
```
Time units: `ago(30m)`, `ago(2d)`, `ago(10s)`. Prefer a TimeGenerated filter over the portal picker; when both are set, the smaller range wins. TimeGenerated is UTC.

### DO
- DO filter early with `where`; `==` is case-sensitive, `=~` case-insensitive, `has` (token-indexed, faster) / `contains` for substrings.
- DO trace one request end-to-end by OperationId across tables via `union` or `join kind=inner ... on OperationId` (ParentId/OperationName link spans).
- DO aggregate: `summarize count() by bin(TimeGenerated, 5m), ResultCode`; latency with `percentiles(DurationMs, 50, 95, 99)`, distinct with `dcount()`.
- DO name thresholds with `let` (e.g. `let slow = 1000;`) and shape rows with `project`/`extend`.
- DO read dynamic fields directly: `Properties.userId`, `tostring(Properties["orderId"])`.
- DO map severity: AppTraces/AppExceptions `SeverityLevel` int 0=Verbose,1=Information,2=Warning,3=Error,4=Critical.

### DON'T
- DON'T lead with bare `search "text"` — it scans all tables and is slow; use `search in (AppTraces) "..."` or a `where` on a known column.
- DON'T `sort` a whole table to get recent rows — use `top N by TimeGenerated desc` (server-side).
- DON'T compare a string column numerically without a cast: `where toint(Level) >= 10`.

### Find errors / trace a request
Recent exceptions grouped by fingerprint:
```kusto
AppExceptions
| where TimeGenerated > ago(24h)
| summarize Count=count() by ProblemId, ExceptionType, OuterMessage
| top 20 by Count desc
```
Failure rate per operation:
```kusto
AppRequests
| where TimeGenerated > ago(6h)
| summarize Total=count(), Failed=countif(Success == false) by Name
| extend FailRate = round(100.0 * Failed / Total, 2)
| sort by FailRate desc
```
Full trace for one correlation id (traces + exceptions merged):
```kusto
let op = "<operation-id>";
union AppTraces, AppExceptions
| where OperationId == op
| project TimeGenerated, Type, Message, SeverityLevel, ExceptionType
| sort by TimeGenerated asc
```

Sibling deep-dives: lore/deep/azure-monitor.md#app-insights-and-ingestion, lore/deep/azure-monitor.md#workspaces-and-alerts.

### Sources
- learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
- learn.microsoft.com/en-us/kusto/query/summarize-operator (Applies to: Azure Monitor)
- learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appexceptions ; /apptraces

## Application Insights & Ingestion <a id="app-insights-and-ingestion"></a>

Workspace-based Application Insights is APM on Azure Monitor Logs: telemetry in a Log Analytics workspace, queried with KQL.

### Instrument (emit)
- DO instrument server code with the **Azure Monitor OpenTelemetry Distro** (.NET, Java, Node, Python); browsers use the **App Insights JavaScript SDK** (not OTel). Classic SDKs → OpenTelemetry.
- DO set a **connection string** (not the legacy instrumentation key): env `APPLICATIONINSIGHTS_CONNECTION_STRING`. Set `cloud_RoleName` per service to tell components apart.
- DO let auto-instrumentation capture request/dependency spans; add logs as `traces`, events as `customEvents`. Propagate W3C context so `operation_Id` links calls.
- DON'T log secrets/PII into custom dimensions; DON'T trust sampling-blind counts — see ItemCount.

### Tables (naming trap)
Same data, two schemas: query **Log Analytics** `App*` tables — short classic names work only in the App Insights blade. Spans → `AppRequests`/`AppDependencies`; app logs → `AppTraces`; also `AppExceptions`, `AppEvents`(customEvents), `AppMetrics`(customMetrics), `AppPageViews`, `AppAvailabilityResults`, `AppPerformanceCounters`. Key columns: `TimeGenerated`, `OperationId`, `Name`, `Success`, `ResultCode`, `DurationMs`, `Message`, `ExceptionType`, `ProblemId`, `AppRoleName`, `ItemCount`.

### Sampling — ItemCount
A row can equal several events; use `sum(ItemCount)`, not `count()`:
```kusto
AppRequests
| where TimeGenerated > ago(1h) and Success == false
| summarize failures = sum(ItemCount) by ResultCode, AppRoleName
| order by failures desc
```

### Trace a failed request
Exceptions live in `AppExceptions`. For end-to-end context, take a failed request's `OperationId` and union its dependencies, logs, exceptions:
```kusto
let op = toscalar(AppRequests | where Success == false | top 1 by TimeGenerated | project OperationId);
union AppRequests, AppDependencies, AppTraces, AppExceptions
| where OperationId == op
| project TimeGenerated, itemType = Type, Name, Message, ResultCode, Success, DurationMs
| order by TimeGenerated asc
```

### Custom ingestion
- DO send non-App-Insights logs via the **Logs Ingestion API** + a **data collection rule (DCR)** to a **custom table** (`_CL`); Entra OAuth, supersedes the deprecated HTTP Data Collector API.
- DO reshape at ingest with DCR **transformations** (drop noise, redact PII) to cut storage cost.
- DON'T assume every table supports transforms — check the tables-feature-support reference.

### Retention & cost
Per-table **table plan** (Analytics / Basic / Auxiliary) sets features + price. Interactive retention ≤2 years; total ≤12 years via **search job**. No workspace charge — pay for ingested GB + retention.

See lore/deep/azure-monitor.md#kql-log-queries and lore/deep/azure-monitor.md#workspaces-and-alerts.

### Sources
- https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/app/create-workspace-resource
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure

## Workspaces & Alerts <a id="workspaces-and-alerts"></a>

A Log Analytics workspace is the data store for Azure Monitor Logs; you query it with KQL. Workspace-based Application Insights writes telemetry to `App*` tables in its linked workspace: `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces`, `AppPageViews`, `AppPerformanceCounters`, `AppAvailabilityResults`. Verified at learn.microsoft.com 2026-07.

### Workspaces & tables — DO / DON'T
- DO send app telemetry to a workspace-based Application Insights resource (classic resources are retired) so `App*` tables are queryable next to platform/resource logs in one workspace.
- DO pick a table plan per table: **Analytics** (full KQL + alerts), **Basic** and **Auxiliary** (cheap, high-volume, limited query) — route verbose debug to Basic, keep alertable signals on Analytics.
- DO set retention per table: interactive retention for live querying, long-term retention (up to 12 years) for cheap archive; run a **search job** to pull archived data back into interactive when needed.
- DO track ingestion cost with the `Usage` table before it surprises you; DON'T over-retain chatty tables.
- DON'T hardcode a workspace or table name in app code — emit via the SDK/OpenTelemetry exporter and diagnostic settings; DON'T expect classic schema names like `requests`/`exceptions` in the workspace — the tables are `AppRequests`/`AppExceptions`.

Billable ingestion (GB/day) per table:
```kql
Usage
| where TimeGenerated > ago(24h) and IsBillable == true
| summarize GB = sum(Quantity) / 1000 by DataType
| sort by GB desc
```

### Log search alerts — DO / DON'T
A log search alert rule = a KQL query + a **measure** (Table rows, or a calculation on a numeric column) + an **aggregation type** (Total/Average/Minimum/Maximum) over an **aggregation granularity** (window) + a **frequency of evaluation** (1 minute–24 hours) + a **threshold** (static or dynamic).
- DO make the query emit one numeric value per window with `summarize ... by bin(TimeGenerated, <window>)`; **split by dimensions** (up to 6, e.g. `AppRoleName`) to alert per service.
- DO put the outcome in the filter (`Success == false`, `toint(ResultCode) >= 500`) so the count is actionable.
- DON'T use `bag_unpack()`, `pivot()`, `narrow()`, or the reserved word `AggregatedValue` — they're unsupported in alert queries.
- DON'T pair 1-minute frequency with `search`, `union`, `take`, `ingestion_time()`, or `adx()` — the query is optimized internally and fails; use `ago()` with timespan literals only.

Failed-request rate per service (measure = Total of `Failed`, split by `AppRoleName`, threshold > 10):
```kql
AppRequests
| where Success == false
| summarize Failed = count() by bin(TimeGenerated, 5m), AppRoleName
```

Exception spike (measure = Table rows, 15-minute window):
```kql
AppExceptions
| summarize Count = count() by bin(TimeGenerated, 15m), AppRoleName
```

See also lore/deep/azure-monitor.md#kql-log-queries and lore/deep/azure-monitor.md#app-insights-and-ingestion.

### Sources
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-workspace-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-create-log-alert-rule
- https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/apprequests

# Azure Monitor — KQL Log Queries

Azure Monitor Logs stores data in a Log Analytics workspace as typed tables; you query it with KQL (Kusto Query Language). Workspace-based Application Insights writes to Logs tables: AppRequests, AppDependencies, AppExceptions, AppTraces, AppPageViews, AppEvents, AppMetrics (verified 2026 at learn.microsoft.com). KQL is case-sensitive; keywords are lowercase; table/column names must match the schema pane exactly.

## Query shape
Start with a table name (scopes the query + is fast), pipe `|` into operators, put the time filter first.
```kusto
AppRequests
| where TimeGenerated > ago(1h)
| where Success == false
| project TimeGenerated, Name, ResultCode, DurationMs, OperationId
| top 50 by TimeGenerated desc
```
Time units: `ago(30m)`, `ago(2d)`, `ago(10s)`. Prefer a TimeGenerated filter over the portal picker; when both are set, the smaller range wins. TimeGenerated is UTC.

## DO
- DO filter early with `where`; `==` is case-sensitive, `=~` case-insensitive, `has` (token-indexed, faster) / `contains` for substrings.
- DO trace one request end-to-end by OperationId across tables via `union` or `join kind=inner ... on OperationId` (ParentId/OperationName link spans).
- DO aggregate: `summarize count() by bin(TimeGenerated, 5m), ResultCode`; latency with `percentiles(DurationMs, 50, 95, 99)`, distinct with `dcount()`.
- DO name thresholds with `let` (e.g. `let slow = 1000;`) and shape rows with `project`/`extend`.
- DO read dynamic fields directly: `Properties.userId`, `tostring(Properties["orderId"])`.
- DO map severity: AppTraces/AppExceptions `SeverityLevel` int 0=Verbose,1=Information,2=Warning,3=Error,4=Critical.

## DON'T
- DON'T lead with bare `search "text"` — it scans all tables and is slow; use `search in (AppTraces) "..."` or a `where` on a known column.
- DON'T `sort` a whole table to get recent rows — use `top N by TimeGenerated desc` (server-side).
- DON'T compare a string column numerically without a cast: `where toint(Level) >= 10`.

## Find errors / trace a request
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

Sibling deep-dives: lore/azure-monitor/app-insights-and-ingestion.md, lore/azure-monitor/workspaces-and-alerts.md.

## Sources
- learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries
- learn.microsoft.com/en-us/kusto/query/summarize-operator (Applies to: Azure Monitor)
- learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appexceptions ; /apptraces

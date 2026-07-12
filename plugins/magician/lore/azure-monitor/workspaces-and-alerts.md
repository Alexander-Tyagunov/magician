# Azure Monitor — Workspaces & Alerts

A Log Analytics workspace is the data store for Azure Monitor Logs; you query it with KQL. Workspace-based Application Insights writes telemetry to `App*` tables in its linked workspace: `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces`, `AppPageViews`, `AppPerformanceCounters`, `AppAvailabilityResults`. Verified at learn.microsoft.com 2026-07.

## Workspaces & tables — DO / DON'T
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

## Log search alerts — DO / DON'T
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

See also lore/azure-monitor/kql-log-queries.md and lore/azure-monitor/app-insights-and-ingestion.md.

## Sources
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-workspace-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-create-log-alert-rule
- https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/apprequests

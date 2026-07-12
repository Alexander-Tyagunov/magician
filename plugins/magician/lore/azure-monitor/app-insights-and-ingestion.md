# Azure Monitor — Application Insights & Ingestion

Workspace-based Application Insights is APM on Azure Monitor Logs: telemetry in a Log Analytics workspace, queried with KQL.

## Instrument (emit)
- DO instrument server code with the **Azure Monitor OpenTelemetry Distro** (.NET, Java, Node, Python); browsers use the **App Insights JavaScript SDK** (not OTel). Classic SDKs → OpenTelemetry.
- DO set a **connection string** (not the legacy instrumentation key): env `APPLICATIONINSIGHTS_CONNECTION_STRING`. Set `cloud_RoleName` per service to tell components apart.
- DO let auto-instrumentation capture request/dependency spans; add logs as `traces`, events as `customEvents`. Propagate W3C context so `operation_Id` links calls.
- DON'T log secrets/PII into custom dimensions; DON'T trust sampling-blind counts — see ItemCount.

## Tables (naming trap)
Same data, two schemas: query **Log Analytics** `App*` tables — short classic names work only in the App Insights blade. Spans → `AppRequests`/`AppDependencies`; app logs → `AppTraces`; also `AppExceptions`, `AppEvents`(customEvents), `AppMetrics`(customMetrics), `AppPageViews`, `AppAvailabilityResults`, `AppPerformanceCounters`. Key columns: `TimeGenerated`, `OperationId`, `Name`, `Success`, `ResultCode`, `DurationMs`, `Message`, `ExceptionType`, `ProblemId`, `AppRoleName`, `ItemCount`.

## Sampling — ItemCount
A row can equal several events; use `sum(ItemCount)`, not `count()`:
```kusto
AppRequests
| where TimeGenerated > ago(1h) and Success == false
| summarize failures = sum(ItemCount) by ResultCode, AppRoleName
| order by failures desc
```

## Trace a failed request
Exceptions live in `AppExceptions`. For end-to-end context, take a failed request's `OperationId` and union its dependencies, logs, exceptions:
```kusto
let op = toscalar(AppRequests | where Success == false | top 1 by TimeGenerated | project OperationId);
union AppRequests, AppDependencies, AppTraces, AppExceptions
| where OperationId == op
| project TimeGenerated, itemType = Type, Name, Message, ResultCode, Success, DurationMs
| order by TimeGenerated asc
```

## Custom ingestion
- DO send non-App-Insights logs via the **Logs Ingestion API** + a **data collection rule (DCR)** to a **custom table** (`_CL`); Entra OAuth, supersedes the deprecated HTTP Data Collector API.
- DO reshape at ingest with DCR **transformations** (drop noise, redact PII) to cut storage cost.
- DON'T assume every table supports transforms — check the tables-feature-support reference.

## Retention & cost
Per-table **table plan** (Analytics / Basic / Auxiliary) sets features + price. Interactive retention ≤2 years; total ≤12 years via **search job**. No workspace charge — pay for ingested GB + retention.

See lore/azure-monitor/kql-log-queries.md and workspaces-and-alerts.md.

## Sources
- https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/app/create-workspace-resource
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure

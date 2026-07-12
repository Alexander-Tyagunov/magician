# Azure Monitor — core digest
KQL (Kusto), case-sensitive. Logs live in a Log Analytics workspace (tables); Application Insights is workspace-based (Azure Monitor OpenTelemetry Distro + connection string). App tables: AppRequests, AppDependencies, AppExceptions, AppTraces (SeverityLevel 0=Verbose…4=Critical). Verified 2026-07.

DO emit structured events via OpenTelemetry; set the level threshold by ENV, not hardcoded.
DO filter TimeGenerated first: `AppTraces | where TimeGenerated > ago(1h)`.
DO find errors: `AppExceptions | where TimeGenerated > ago(1h) | summarize n=count() by ProblemId | top 10 by n`.
DO trace by OperationId: `AppRequests | where OperationId == "abc" | project TimeGenerated, Name, ResultCode, DurationMs`.
DO chart over time: `AppRequests | summarize errs=countif(Success==false) by bin(TimeGenerated,5m)`.

DON'T mix syntax — KQL only, no SPL/LogQL/SQL; `==` compares (not `=`).
DON'T `search "text"` over all tables (slow); start from a table name.
DON'T log secrets/PII into custom dimensions — they persist.
DON'T compare a String column numerically without a cast (`toint(Level)>=10`).

Deep dive when writing non-trivial Azure Monitor — read lore/azure-monitor/{kql-log-queries,app-insights-and-ingestion,workspaces-and-alerts}.md

## Sources
learn.microsoft.com/azure/azure-monitor/logs/{get-started-queries,data-platform-logs} · app/app-insights-overview

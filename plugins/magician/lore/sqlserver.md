# Microsoft SQL Server — core digest
Version: 2025 (17.x); supported 2017/2019/2022/2025 (2016 EOL 2026-07). Gates: 2019 UTF-8, ADR, UDF-inline; 2022 TDS 8.0, PSP, Query Store default-on (new DBs); 2025 JSON/VECTOR, regex, optimized locking.

DO pool client-side (no server pooler); MS ODBC/JDBC, Encrypt=strict.
DO default READ COMMITTED locks; RCSI OFF on-prem, ON Azure SQL DB/Fabric; set it ON; SNAPSHOT needs ALLOW_SNAPSHOT_ISOLATION.
DO give tables a narrow, rising clustered key; wide/GUID keys bloat every NC index.
DO read actual plans (SET STATISTICS IO, TIME ON); Query Store: catch/force.
DO type deliberately: NVARCHAR Unicode, VARCHAR under _UTF8 (2019+); datetime2 over datetime.
DO parameterize (sp_executesql): injection-safe; param sniffing (OPTIMIZE FOR/RECOMPILE; PSP 2022+).
DO wrap writes in tx + SET XACT_ABORT ON; batch big DML (escalation ~5000 locks); retry deadlocks 1205; Entra auth.

DON'T use NOLOCK/READ UNCOMMITTED: dirty/dup/skipped rows, not speed.
DON'T use MERGE under concurrency (deadlock/bug-prone); upsert with HOLDLOCK+UPDLOCK.
DON'T call scalar UDFs row-by-row pre-2019 (no inlining) or table vars for big sets → temp tables.
DON'T hold a tx across app/network round-trips: blocking + version growth.

Deep dive when writing non-trivial SQL Server — read lore/sqlserver/{connection-and-pooling,tsql-and-types,execution-plans-and-indexing,performance}.md

## Sources
learn.microsoft.com/sql · query-store, isolation, what's-new 2022/2025

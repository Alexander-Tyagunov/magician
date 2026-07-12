# Oracle Database — core digest
Version: 26ai current (23c renamed 23ai); 19c LTS. Gates: binary JSON 21c; BOOLEAN, VECTOR/AI Vector Search, JSON Relational Duality, IF NOT EXISTS DDL, SQL property graphs 23ai. Don't claim features pre-release.

DO connect by service name, not SID; Easy Connect Plus (19c+): TCPS+wallet, multi-host failover; small app pools + server-side DRCP for many clients.
DO bind `:name`/`:1` (injection-safe); literals hard-parse. Use `VARCHAR2` not `VARCHAR`; `(n CHAR)` not bytes; `NUMBER` money, `BINARY_DOUBLE` floats.
DO read plans via `DBMS_XPLAN.DISPLAY_CURSOR`, not `EXPLAIN PLAN`; keep `DBMS_STATS` fresh; index FK/filter/join cols.
DO default READ COMMITTED (readers never block writers); SERIALIZABLE + retry ORA-08177; guard lost updates with old `WHERE` values; require TLS/encryption, least-priv roles, no runtime DDL.

DON'T treat `''` as a value (it's NULL) — test `IS NULL`; expect lock escalation — row-locks only, never escalate, ORA-00060 auto-rollback one stmt, retry.
DON'T hold a tx open across app calls — readers hit `ORA-01555`; assume `FLOAT(p)` is decimal (it's binary) or `DATE`/`SYSDATE` lacks time.

Deep dive for non-trivial Oracle — read lore/oracle/{connection-and-pooling,plsql-and-types,optimizer-and-indexing,transactions-and-locking,performance}.md

## Sources
docs.oracle.com/en/database/oracle/oracle-database/26/ (cncpt, sqlrf, tgsql, jjdbc) · 26ai GA blog

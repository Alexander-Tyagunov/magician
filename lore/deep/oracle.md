# Oracle Database — deep dive

> On-demand companion to `lore/oracle.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Connection & pooling](#connection-and-pooling) · [PL/SQL & Types](#plsql-and-types) · [Optimizer & indexing](#optimizer-and-indexing) · [Transactions and Locking](#transactions-and-locking) · [Performance](#performance)

## Connection & pooling <a id="connection-and-pooling"></a>

Oracle Net, the listener, and the three server modes that set a connection's server-side cost. Current stable **Oracle AI Database 26ai (release 26)**; guidance spans **19c** (the long-lived production release) → **21c** (innovation) → **23ai** → **26ai**. Version gates that matter here: connect-string `POOL_CONNECTION_CLASS`/`POOL_PURITY` need **21c+**; multiple named DRCP pools need **23.4+**; **Implicit Connection Pooling** needs **26ai**. This is the *engine + Oracle Net* layer — client-pool (UCP/HikariCP) sizing lives in `lore/deep/jdbc.md#connections-and-pooling`, the two-tier model and pool-size knee in `lore/deep/databases.md#connection-pooling`.

### Three server modes — chosen per connect descriptor

A client picks its handler with `(SERVER=DEDICATED|SHARED|POOLED)` in `CONNECT_DATA` (Easy Connect `/service:dedicated|shared|pooled`).
- **DEDICATED** (default): the listener spawns **one server process per connection**, torn down when the session ends. Highest per-connection memory (a process + PGA). Fine behind a small bounded middle-tier pool.
- **SHARED**: dispatchers queue requests for a few shared servers; UGA moves into the SGA/large pool. Saves processes for many idle sessions but adds queueing — niche now.
- **POOLED (DRCP)**: connect to a **connection broker** that lends a pooled "server + session" only while a request runs, then reclaims it. Reach for this when **many client processes/hosts hold persistent but mostly-idle connections** — it shares sessions across processes and even hosts, which a per-process client pool cannot.

### DRCP — connection class and purity

DRCP pools full server+session pairs and multiplexes inbound connections onto few of them. Two knobs govern reuse:
- **Connection class** (`POOL_CONNECTION_CLASS`): a pooled session is reused only by connections with the **same DB user + same class**. Set one stable class per app tier. If unset, each driver process invents a unique class (`DPY…`/`OCI…`) so nothing is shared — the classic "DRCP does nothing" misconfig; catch it in `V$CPOOL_CONN_INFO` (maps machine→class).
- **Purity**: `SELF` reuses the server process **and its session memory** (max benefit); `NEW` forces fresh session memory. Pooled connections default to **SELF**, standalone to **NEW**. Session state (`ALTER SESSION`, package globals, temp objects) survives a `SELF` reuse within a class — scrub it with a session/fixup callback or you leak state to the next borrower.

### Configuring DRCP

`DBMS_CONNECTION_POOL.START_POOL`, then `CONFIGURE_POOL`/`ALTER_PARAM` on `SYS_DEFAULT_CONNECTION_POOL`. Defaults: `MINSIZE 4`, `MAXSIZE 40`, `INCRSIZE 2`, `SESSION_CACHED_CURSORS 20`, `INACTIVITY_TIMEOUT 300`s, `MAX_THINK_TIME 120`s (broker reclaims a server the client holds past this), `MAX_USE_SESSION 500000`, `MAX_LIFETIME_SESSION 86400`s. `MAXSIZE` caps concurrent *active* pooled servers, not clients. **23.4+**: `ADD_POOL`/`REMOVE_POOL` create named pools selected by `POOL_NAME` in the connect string. Multitenant: `ENABLE_PER_PDB_DRCP` (default `FALSE` = one CDB-wide pool managed from ROOT; `TRUE` = each PDB owns its config and broker sizing comes only from the `CONNECTION_BROKERS` init parameter).

### Implicit Connection Pooling & PRCP (26ai)

**26ai** adds **Implicit Connection Pooling**: set `POOL_BOUNDARY=TRANSACTION|STATEMENT` on a `SERVER=POOLED` descriptor and the broker maps/unmaps a session at request boundaries with **no client pool and no API calls**. `STATEMENT` releases when the session is stateless (all cursors fetched out, no open txn/temp LOB/temp table); `TRANSACTION` releases at commit/rollback. Gotcha: under `TRANSACTION`, a fetch after commit can raise `ORA-01001` and a temp LOB `ORA-22922` — the release already closed them. It engages only when `SERVER=POOLED` is also present. **PRCP** is DRCP fronted by CMAN in Traffic Director Mode (per-service or per-PDB pools) for proxy-side multiplexing across many app hosts.

### Oracle Net gotchas

- **Timeouts**: `TRANSPORT_CONNECT_TIMEOUT` bounds the TCP connect; `RETRY_COUNT`/`RETRY_DELAY` walk a multi-`ADDRESS` list — set them so a dead node fails fast, not hangs.
- **Dead sockets**: NAT/firewalls silently reap idle connections; the next borrow hands back a corpse. Use `EXPIRE_TIME` (client) / `SQLNET.EXPIRE_TIME` in minutes (server) for keepalive probes — **prefer it over `ENABLE=BROKEN`**, which thin drivers ignore. Keep client-pool max-lifetime under any middlebox idle timer.
- **Service, not SID**: connect by `SERVICE_NAME`; SID/`INSTANCE_NAME` are legacy and break RAC/PDB relocation. Multiple `ADDRESS`es with `LOAD_BALANCE`/`FAILOVER` plus FAN/Fast Connection Failover give HA and connection draining.
- **TLS**: TCPS with `WALLET_LOCATION` and `SSL_SERVER_DN_MATCH=TRUE` (verify the cert DN) — without DN match, TLS won't stop MITM. Native network encryption (`SQLNET.ENCRYPTION_*`) is a separate, wallet-free option.

### Limits, symptoms, monitoring

`PROCESSES` (range 80→OS-max, default derived from core count) caps OS processes that can connect at once; `SESSIONS`/`TRANSACTIONS` are **derived from it**. Exhaustion rejects logins with **ORA-00020** (max processes) / **ORA-00018** (max sessions); a listener with no matching handler (DRCP not started, wrong `SERVER=`, instance full) gives **ORA-12516/ORA-12520**. DRCP exists to keep server-process count flat under thousands of clients so you never reach these. Watch `V$CPOOL_STATS` (`NUM_MISSES` high = class churn; `NUM_WAITS` high = `MAXSIZE` too small), `V$CPOOL_CC_STATS` (per class), and `DBA_CPOOL_INFO` (config).

### Sources

- Oracle AI Database 26ai — Net Services Administrator's Guide, Understanding Service Handlers (dedicated/shared/pooled, connection broker): https://docs.oracle.com/en/database/oracle/oracle-database/26/netag/understanding-service-handlers.html
- Oracle AI Database 26ai — PL/SQL Packages and Types Reference, DBMS_CONNECTION_POOL (CONFIGURE_POOL/ADD_POOL defaults, ENABLE_PER_PDB_DRCP, CONNECTION_BROKERS): https://docs.oracle.com/en/database/oracle/oracle-database/26/arpls/DBMS_CONNECTION_POOL.html
- python-oracledb — Connection Handling & DRCP (connection class, purity SELF/NEW defaults, named pools 23.4, Implicit Connection Pooling requires 26ai, V$CPOOL views): https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html
- Oracle AI Database 26ai — Net Services Administrator's Guide, Oracle Connection Manager in Traffic Director Mode (Implicit Connection Pooling, POOL_BOUNDARY, PRCP, per-PDB pools): https://docs.oracle.com/en/database/oracle/oracle-database/26/netag/oracle-connection-manager-traffic-director-mode.html
- Oracle AI Database 26ai — Database Reference, PROCESSES (range 80→OS; SESSIONS/TRANSACTIONS derived): https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/PROCESSES.html

## PL/SQL & Types <a id="plsql-and-types"></a>

Current: **26ai** GA (successor to the **23ai** LTS); **19c** is still the widely-deployed long-term release, **21c** the innovation release. Feature gates noted inline — never claim a type/feature before its release.

### Type traps that bite through every driver
- **Empty string is NULL.** Oracle "treats a character value with a length of zero as null" — `'' = NULL`, and any driver that sends `''` for an empty field stores NULL. Comparisons with NULL yield UNKNOWN, so test only with `IS [NOT] NULL`. Arithmetic with NULL → NULL, but `||` **ignores** NULL operands. Oracle now recommends *not* relying on `''`≡NULL (may change).
- **NUMBER is exact decimal** (p 1–38, s −84–127) — use it for money. `BINARY_FLOAT`/`BINARY_DOUBLE` are IEEE-754 (inexact, but support Inf/NaN); `FLOAT(p)` is a NUMBER subtype (binary precision), not a C float.
- **Use `VARCHAR2`, never `VARCHAR`** (reserved; Oracle may redefine it). `size` is required. Max **4000 bytes** default, **32767** only if `MAX_STRING_SIZE=EXTENDED` (irreversible; extended cols stored out-of-line as LOBs). Length is `BYTE` vs `CHAR` per `NLS_LENGTH_SEMANTICS` (SYS defaults BYTE) — a multibyte value can overflow a byte-sized column. `CHAR(n)` is blank-padded (padded-comparison semantics) — avoid.
- **`DATE` carries a time-of-day** (to the second, no fractional, no zone) — it is *not* a date-only type; midnight-only assumptions and `=` matches silently fail. `TIMESTAMP` adds fractional seconds; `WITH TIME ZONE` stores the offset; `WITH LOCAL TIME ZONE` normalizes to the DB zone on store and renders in the session zone. Datetime `+ n` adds **days**.
- **Selecting a LOB returns a locator**, not bytes — stream via `DBMS_LOB`; free temporary LOBs or leak PGA. `LONG`/`LONG RAW` deprecated since 8.1.6 → use `CLOB`/`BLOB`.

### SQL-visible types added recently
- **JSON** native binary type since **21c** (`compatible>=20`); before that store as `VARCHAR2`/`CLOB`/`BLOB` + `IS JSON` check. **BOOLEAN** as a SQL/column type and **VECTOR** (similarity search) are **23ai**. Before 23ai, `BOOLEAN` was **PL/SQL-only** — not a column type and not bindable from clients; 23ai lets PL/SQL BOOLEAN cross into SQL.

### PL/SQL ↔ SQL engine: context switches
Procedural code runs in the PL/SQL engine; each SQL statement is handed to the SQL engine — a **context switch**. A row-by-row cursor loop pays one switch *per row*.
- `SELECT ... BULK COLLECT INTO coll [LIMIT n]` fetches a set in one switch — **always `LIMIT`** (e.g. 100–1000) from an unbounded source, or a large table OOMs the PGA.
- `FORALL i IN .. ` batches set DML in one switch; add `SAVE EXCEPTIONS` and read `SQL%BULK_EXCEPTIONS` to survive per-row errors.
- Loop counters: `PLS_INTEGER`/`BINARY_INTEGER` (hardware arithmetic, −2147483648..2147483647, overflow → ORA-01426) beat `NUMBER`. `SIMPLE_INTEGER` is `NOT NULL` and **wraps silently** on overflow — fastest, but only when overflow is impossible/intended.

### Compilation & function reuse
- `PLSQL_OPTIMIZE_LEVEL` default **2**; level **3** auto-inlines subprograms (`PRAGMA INLINE(f,'YES'|'NO')` to force/suppress). `PLSQL_CODE_TYPE` default **INTERPRETED**; `NATIVE` speeds compute-heavy code but not SQL (still switches).
- `NOCOPY` passes big `IN OUT` collections/records by reference — caveat: on an unhandled exception the actual argument may be left partially mutated.
- `DETERMINISTIC` marks pure functions (needed for function-based indexes/MVs). `RESULT_CACHE` caches results by argument, auto-invalidated when a dependency changes. `PRAGMA UDF` cuts SQL→PL/SQL call overhead for functions used inside SQL.

### Dynamic SQL, rights, transactions
- `EXECUTE IMMEDIATE stmt USING v1, v2` binds **values** — "the most effective way to make your PL/SQL code invulnerable to SQL injection attacks is to use bind variables"; the engine uses them as data, never parses them. Identifiers can't bind: validate against the data dictionary (`ALL_TAB_COLS`, `ALL_TABLES`) and wrap with `DBMS_ASSERT` (`ENQUOTE_NAME`/`ENQUOTE_LITERAL`/`SIMPLE_SQL_NAME`) — a *supplement*, not a replacement for validation. Convert datetime/number with explicit locale-independent format models (blocks NLS-based injection).
- `AUTHID DEFINER` is the **default** (runs as owner, only role PUBLIC); `AUTHID CURRENT_USER` (invoker's rights) is preferred for shared code but requires the owner hold `INHERIT PRIVILEGES` on the invoker or it raises ORA-06598. Triggers are DR units; anonymous blocks are IR.
- `PRAGMA AUTONOMOUS_TRANSACTION` runs an **independent** transaction that must `COMMIT`/`ROLLBACK` before returning (else ORA-06519) — ideal for audit rows that survive a caller rollback, but it can self-deadlock against the parent tx's locks.
- `WHEN OTHERS` without `RAISE` silently swallows errors — re-raise or log `SQLERRM` + `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE`. `RAISE_APPLICATION_ERROR` codes live in −20000..−20999 only.
- **Mutating table (ORA-04091):** a row-level trigger can't query/modify its own table — use a compound trigger to buffer rows.

### Sources
- https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/Data-Types.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/Nulls.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/plsql-optimization-and-tuning.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/sql-injection.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/invokers-rights-and-definers-rights-authid-property.html

## Optimizer & indexing <a id="optimizer-and-indexing"></a>

Version span 19c→26ai. Current stable is **26ai** (2026 GA); the cost-based optimizer is the only optimizer (RBO is long dead). **19c** is the still-ubiquitous Long Term Release, 23ai the prior LTR. Feature gate that bites: **automatic indexing, real-time statistics, and high-frequency stats collection all shipped in 19c but are licensed ONLY on Exadata / Exadata Cloud (and Autonomous)** — they silently do nothing on Standard EE, ODA, or Base DB. `OPTIMIZER_ADAPTIVE_STATISTICS` was split out and defaulted OFF from 12.2. Pin behavior across upgrades with `OPTIMIZER_FEATURES_ENABLE`, not by reverting the binary.

### Statistics are the fuel — nothing matters more
The optimizer costs plans purely from dictionary stats (`DBA_TAB/COL/IND_STATISTICS`), never live data. Gather with `DBMS_STATS` (the `ANALYZE` command is deprecated for stats); keep `ESTIMATE_PERCENT => AUTO_SAMPLE_SIZE` — a fast one-pass NDV scan. A fixed percent silently disables top-frequency/hybrid histograms and forces legacy height-balanced ones. `METHOD_OPT => 'SIZE AUTO'` (default) builds histograms only for columns that **prior queries actually filtered on** (tracked in `SYS.COL_USAGE$`): gathering on a never-queried table yields NO histograms, and shifting query patterns can change plans with zero data change. Histograms: frequency when NDV ≤ 254 buckets, else top-frequency or hybrid. The auto-stats task fires at ~10% modified rows — too lazy for large hot tables, so lower `STALE_PERCENT` or gather manually after bulk loads. Online stats auto-populate on direct-path INSERT/CTAS but skip histograms and skip conventional DML (unless `OPTIMIZER_REAL_TIME_STATISTICS`, Exadata-only). For correlated columns add **extended stats** (column groups) or expression stats so cardinality isn't underestimated by the independence assumption.

### Access paths & index types
An index scan wins for a small row fraction; a full table scan (multiblock reads sized by `DB_FILE_MULTIBLOCK_READ_COUNT`) wins once you touch a large share. Read the scans in a plan: **UNIQUE** (equality on all columns of a unique index, ≤1 row); **RANGE** (high selectivity, satisfies `ORDER BY`, incl. DESC); **FULL** (single-block, ordered, can skip a sort); **FAST FULL** (multiblock, unordered, index-only, no sort); **SKIP** (leading column absent from the predicate — only pays when that column is very low-NDV). A `TABLE ACCESS BY INDEX ROWID` step follows unless the index covers every selected column; `BATCHED` reorders rowids into block order to blunt a bad **clustering factor** (index-vs-heap ordering; a high factor pushes the optimizer toward a full scan). Gotchas: any function on an indexed column (incl. implicit `TO_NUMBER`/`TO_CHAR` from a type mismatch) disables the plain index — add a function-based index or fix the type; B-tree indexes omit all-NULL keys, so `COUNT(*)`/`IS NULL` can't use them; **bitmap** indexes suit low-NDV, read-mostly columns and DO store NULLs, but one DML locks a whole bitmap segment — never bitmap an OLTP-hot column (they shine in star schemas via bitmap-join indexes + star transformation). Build/rebuild with `ONLINE`; stage risky indexes `INVISIBLE`, then flip visible or trial via `OPTIMIZER_USE_INVISIBLE_INDEXES`.

### Adaptive optimization & plan stability
`OPTIMIZER_ADAPTIVE_PLANS` (default TRUE) defers the nested-loops-vs-hash join choice: a statistics collector buffers rows and switches at a runtime inflection point. Automatic reoptimization marks a cursor `IS_REOPTIMIZABLE` when actual rows diverge from the estimate, so the NEXT parse gets a better plan — the first run still executed the bad one. To stop plans regressing on upgrade or a stats change, use **SQL Plan Management**: capture via `OPTIMIZER_CAPTURE_SQL_PLAN_BASELINES` or load baselines from cursor cache/AWR/SQL tuning set with `DBMS_SPM`. The optimizer uses only an accepted baseline; new plans stay unaccepted until `EVOLVE_SQL_PLAN_BASELINE` proves they are faster. Prefer baselines over embedded hints and over pinning `OPTIMIZER_FEATURES_ENABLE`.

### Bind peeking & cursor sharing — the classic footgun
Always bind (`:x`); literals hard-parse per value and thrash library-cache latches. But the optimizer **peeks the bind only at the first hard parse**, so on a skewed column the whole app can inherit a plan chosen for one unlucky value. **Adaptive cursor sharing** counters this — it marks bind-sensitive cursors bind-aware and spawns per-selectivity child cursors — but only when a histogram advertises the skew, so stats still gate it. Don't reach for `CURSOR_SHARING=FORCE` as a permanent fix: it's a session-level band-aid that strips useful literals, breaks star transformation, and doesn't stop injection. Trivia that splits cursors: bind name/length, spacing, case, `OPTIMIZER_MODE` — diagnose with `V$SQL_SHARED_CURSOR`.

### Diagnosing
`EXPLAIN PLAN` shows only the compile-time guess and never peeks binds — don't trust it for bound SQL. Run the statement, then `SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(FORMAT=>'ALLSTATS LAST'))` (with the `GATHER_PLAN_STATISTICS` hint or `STATISTICS_LEVEL=ALL`) and compare **E-Rows vs A-Rows**: a large gap is a cardinality miss (stale/absent stats, a missing histogram or column-group stat, or a predicate the index can't serve). `DISPLAY_AWR` pulls a historical plan to prove a regression.

### Automatic indexing (Exadata/ADB only)
`DBMS_AUTO_INDEX` mines candidates from the workload, builds them invisible, verifies they beat the current plan, then promotes to visible or marks them unusable/drops them. `CONFIGURE('AUTO_INDEX_MODE', 'IMPLEMENT'|'REPORT ONLY'|'OFF')`; review with `REPORT_ACTIVITY`. It complements, never replaces, deliberate composite/covering design.

### Sources
docs.oracle.com/en/database/oracle/oracle-database/26/tgsql/query-optimizer-concepts.html · .../tgsql/optimizer-statistics-concepts.html · .../tgsql/histograms.html · .../tgsql/optimizer-access-paths.html · .../tgsql/improving-rwp-cursor-sharing.html · .../tgsql/influencing-the-optimizer.html · .../tgsql/generating-and-displaying-execution-plans.html · .../arpls/DBMS_AUTO_INDEX.html · .../dblic/Licensing-Information.html

## Transactions and Locking <a id="transactions-and-locking"></a>

Version: 26ai is the current long-term release (GA 2026), successor to 23ai (2024); 19c is still the most widely deployed LTS (21c was an Innovation release). Semantics below hold 19c→26ai. Version gates: `SKIP LOCKED` (since 11g), **Lock-Free Reservations** / `RESERVABLE` columns (**23ai**), transaction **priority** + auto-abort of low-priority blockers (23ai→26ai). Oracle exposes only **3** isolation modes — there is no READ UNCOMMITTED and no REPEATABLE READ level.

### Isolation: three modes, MVCC via undo + SCN
- **Read Committed** (default): every *query* sees data committed before that query (not the transaction) began — so two queries in one tx can differ; nonrepeatable reads and phantoms are possible. Dirty reads are **never** possible at any level.
- **Serializable**: the whole tx sees a snapshot as of when the *transaction* began, plus its own writes — no dirty/nonrepeatable/phantom reads. A write to a row another tx committed after yours began raises **ORA-08177 `can't serialize access`** — you must retry the whole tx.
- **Read Only**: like Serializable but DML is disallowed (except `SYS`); great for consistent multi-query reports, and immune to ORA-08177.

Set with `SET TRANSACTION ISOLATION LEVEL {READ COMMITTED|SERIALIZABLE}` or `ALTER SESSION SET ISOLATION_LEVEL=…` **before the first statement**. Multiversioning is powered by **undo segments** + **SCN**: readers get consistent-read (CR) block clones rebuilt from undo, so **readers never block writers and writers never block readers** (the only exception is a pending distributed transaction). A writer only blocks a *concurrent writer of the same row*.

### Read Committed lost-update trap
Under Read Committed a blocked `UPDATE … WHERE` re-reads the row after the other writer commits, so app-side read-then-write can silently lose updates. Fix: do arithmetic in SQL (`SET bal = bal - :n`), take `SELECT … FOR UPDATE` first, use `MERGE`, or (for hot counters) a `RESERVABLE` column.

### Row (TX) vs table (TM) locks — Oracle never escalates
- **Row locks (TX)** are always **exclusive**, taken per row by `INSERT/UPDATE/DELETE/MERGE/SELECT … FOR UPDATE`, and stored **in the data-block header** — there is no central lock manager, so locking millions of rows costs no extra memory and Oracle **never escalates** a row lock to block/table level (escalation would only breed deadlocks).
- **Table locks (TM)** guard against conflicting DDL. DML takes **Row Exclusive (RX/SX)**; `SELECT … FOR UPDATE` takes an exclusive row lock plus a **Row Share (RS)** table lock. `LOCK TABLE … IN {ROW SHARE|ROW EXCLUSIVE|SHARE|SHARE ROW EXCLUSIVE|EXCLUSIVE} MODE` requests stronger modes explicitly. Oracle does *convert* modes (RS→RX) but never escalates.
- **DDL** takes exclusive/share DDL locks (plus breakable parse locks) and does an **automatic COMMIT before and after** — DDL silently ends your transaction.

### FOR UPDATE: default waits forever
`SELECT … FOR UPDATE` **blocks indefinitely** on a contended row by default. Control it:
- `NOWAIT` — fail immediately with **ORA-00054 `resource busy…`** if any target row is locked.
- `WAIT n` — wait up to *n* seconds, then ORA-00054.
- `SKIP LOCKED` — return only currently-unlocked rows (the idiomatic work-queue dequeue; combine with `FETCH FIRST n ROWS ONLY`).
- `FOR UPDATE OF col` narrows which table's rows are locked in a join. `FOR UPDATE` can't be combined with `DISTINCT`, `GROUP BY`, aggregates, or set operators.

For DDL, set `ALTER SESSION SET DDL_LOCK_TIMEOUT=n` so `ALTER TABLE` waits for its TM lock instead of failing with ORA-00054.

### Deadlocks & retry
Oracle auto-detects deadlocks and raises **ORA-00060**, rolling back **only the one statement** that closed the cycle (not the whole tx) in the session that detected it — you must still decide whether to roll back further and retry. Deadlocks are rare here (row-level locking, no read locks, no escalation) and usually appear only when apps override default locking or take rows in inconsistent order. Defenses: lock rows/tables in a consistent app-wide order, keep txns short, prefer one set-based `UPDATE` over row-at-a-time loops. **Retry logic is mandatory** for ORA-08177 (Serializable) and appropriate for ORA-00060 — replay the whole transaction with backoff, idempotently.

### Lock-Free Reservations & priority (23ai+)
A **`RESERVABLE`** numeric column lets many txns concurrently add/subtract (e.g. reserve inventory or account balance) **without holding the row lock until commit**: each change is journaled as a reservation and *verified against the column's check constraint at commit*, failing only if the aggregate would violate it. This removes the hot-row bottleneck that `SELECT … FOR UPDATE` on a single counter creates. Newer releases also add transaction **priority**, letting a low-priority tx that blocks a high-priority one be auto-aborted.

### DON'T / driver gotchas
- DON'T leave a driver in **autocommit** mode for multi-statement work: each DML commits instantly, breaking atomicity and releasing `FOR UPDATE` locks at once. Oracle itself does **not** autocommit (only DDL does).
- DON'T run long queries against tables under heavy DML with tight undo — CR reconstruction can hit **ORA-01555 `snapshot too old`**; size `UNDO_RETENTION`/retention guarantee, and never fetch across commits in the same cursor.
- DON'T assume sequences roll back — `NEXTVAL` is non-transactional; `CACHE`/`NOORDER` gaps after rollback/RAC are normal, IDs aren't gapless.
- DON'T treat `PRAGMA AUTONOMOUS_TRANSACTION` casually — it commits independently and can **deadlock against its own parent** on the same row.
- DON'T hold a tx open across user think-time or network calls; watch for orphaned **in-doubt distributed transactions** (2PC) — they hold locks until resolved.

### Sources
- docs.oracle.com/en/database/oracle/oracle-database/23/cncpt/data-concurrency-and-consistency.html (isolation, undo/SCN read consistency, TX/TM locks, no escalation, ORA-00060/08177, DDL locks)
- docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/SELECT.html (for_update_clause, wait_clause: NOWAIT/WAIT/SKIP LOCKED)
- docs.oracle.com/en/database/oracle/oracle-database/26/nfcoa/intro_feature_highlights.html (Lock-Free Reservations, priority transactions; 26ai current release)

## Performance <a id="performance"></a>

The prioritized playbook. Ground truth: the cost-based optimizer costs plans from **dictionary stats, not live data** — so tune in this order. Current stable **26ai**; **19c** the ubiquitous LTR. Many levers are license-gated (Diagnostics/Tuning Pack, Partitioning) — verify entitlement first.

### Do these, in order
1. **Keep stats fresh & honest.** `DBMS_STATS` with `AUTO_SAMPLE_SIZE` + `METHOD_OPT 'SIZE AUTO'`; add extended (column-group) stats for correlated predicates; gather right after bulk loads. Stale/absent stats drive every downstream mis-plan. Histograms + adaptive plans: `lore/deep/oracle.md#optimizer-and-indexing`.
2. **Bind, don't literal.** `:x` avoids per-value hard parses and library-cache latch thrash; adaptive cursor sharing handles skew when a histogram exists. DON'T leave `CURSOR_SHARING=FORCE` on as a fix.
3. **Right access path / index.** B-tree for selective OLTP; **bitmap** only for low-NDV, read-mostly DW columns (never OLTP-hot — segment locking); **function-based** index (or fix the type) when a function/implicit conversion hides the column; cover the query to skip `TABLE ACCESS BY INDEX ROWID`. See lore/deep/oracle.md#optimizer-and-indexing.
4. **Partition big tables for pruning** (separately licensed EE option). RANGE/LIST/HASH/composite/interval. Confirm pruning in the plan's `PSTART/PSTOP`: `PARTITION RANGE SINGLE/ITERATOR` = pruned, `RANGE ALL` = not. DON'T wrap the partition key in a function or mismatch its type (defeats pruning as it does indexes) — use a **virtual-column partition** if queries must. Equipartition join keys for **partition-wise joins** (cut PX/RAC traffic).
5. **Result-cache expensive, stable aggregates.** `/*+ RESULT_CACHE */` — keep mode default `MANUAL` (`FORCE` latches and can cache non-deterministic PL/SQL). Size `RESULT_CACHE_MAX_SIZE`; auto-invalidated on base-table DML; watch `V$RESULT_CACHE_STATISTICS`. Read-mostly lookups from many client procs: the OCI **client result cache** (`CLIENT_RESULT_CACHE_SIZE`).
6. **Pool connections.** Reuse sessions (UCP/HikariCP client pool; DRCP for many idle clients) so you never pay dedicated-server spawn cost or hit ORA-00020. See `lore/deep/oracle.md#connection-and-pooling`.

Cross-DB fundamentals: `lore/deep/databases.md#{indexing-and-query-plans,connection-pooling,resilience-and-observability}`.

### How to measure (see it before you tune)
- **`SET AUTOTRACE ON`** (SQL*Plus/SQLcl) — fast plan + logical reads/sorts per statement.
- **Actual vs estimate**: run it, then `DBMS_XPLAN.DISPLAY_CURSOR(FORMAT=>'ALLSTATS LAST')` (with `GATHER_PLAN_STATISTICS`); a big **E-Rows vs A-Rows** gap = a cardinality/stats miss. `EXPLAIN PLAN` alone lies — compile-time only, never peeks binds.
- **Real-Time SQL Monitoring** (Tuning Pack): auto-tracks SQL run in parallel or ≥5s CPU/IO; `DBMS_SQL_MONITOR.REPORT_SQL_MONITOR`, `V$SQL_MONITOR` / `V$SQL_PLAN_MONITOR` — best for one slow/long statement, live per-step.
- **AWR + ASH** (Diagnostics Pack; gated by `CONTROL_MANAGEMENT_PACK_ACCESS`): `awrrpt.sql`/`DBMS_WORKLOAD_REPOSITORY` for system-wide load & top SQL; `V$ACTIVE_SESSION_HISTORY`/`ashrpt.sql` for what sessions waited on. Unlicensed? **Statspack** (free, no ASH/ADDM).

### Sources
docs.oracle.com/en/database/oracle/oracle-database/26/ — tgsql/generating-and-displaying-execution-plans.html · tgsql/monitoring-database-operations.html · tgsql/gathering-optimizer-statistics.html · tgdba/tuning-result-cache.html · partition pruning → …/23/vldbg/partition-pruning.html

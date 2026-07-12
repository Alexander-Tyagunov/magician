# Oracle Database — Connection & pooling

Oracle Net, the listener, and the three server modes that set a connection's server-side cost. Current stable **Oracle AI Database 26ai (release 26)**; guidance spans **19c** (the long-lived production release) → **21c** (innovation) → **23ai** → **26ai**. Version gates that matter here: connect-string `POOL_CONNECTION_CLASS`/`POOL_PURITY` need **21c+**; multiple named DRCP pools need **23.4+**; **Implicit Connection Pooling** needs **26ai**. This is the *engine + Oracle Net* layer — client-pool (UCP/HikariCP) sizing lives in `lore/jdbc/connections-and-pooling.md`, the two-tier model and pool-size knee in `lore/databases/connection-pooling.md`.

## Three server modes — chosen per connect descriptor

A client picks its handler with `(SERVER=DEDICATED|SHARED|POOLED)` in `CONNECT_DATA` (Easy Connect `/service:dedicated|shared|pooled`).
- **DEDICATED** (default): the listener spawns **one server process per connection**, torn down when the session ends. Highest per-connection memory (a process + PGA). Fine behind a small bounded middle-tier pool.
- **SHARED**: dispatchers queue requests for a few shared servers; UGA moves into the SGA/large pool. Saves processes for many idle sessions but adds queueing — niche now.
- **POOLED (DRCP)**: connect to a **connection broker** that lends a pooled "server + session" only while a request runs, then reclaims it. Reach for this when **many client processes/hosts hold persistent but mostly-idle connections** — it shares sessions across processes and even hosts, which a per-process client pool cannot.

## DRCP — connection class and purity

DRCP pools full server+session pairs and multiplexes inbound connections onto few of them. Two knobs govern reuse:
- **Connection class** (`POOL_CONNECTION_CLASS`): a pooled session is reused only by connections with the **same DB user + same class**. Set one stable class per app tier. If unset, each driver process invents a unique class (`DPY…`/`OCI…`) so nothing is shared — the classic "DRCP does nothing" misconfig; catch it in `V$CPOOL_CONN_INFO` (maps machine→class).
- **Purity**: `SELF` reuses the server process **and its session memory** (max benefit); `NEW` forces fresh session memory. Pooled connections default to **SELF**, standalone to **NEW**. Session state (`ALTER SESSION`, package globals, temp objects) survives a `SELF` reuse within a class — scrub it with a session/fixup callback or you leak state to the next borrower.

## Configuring DRCP

`DBMS_CONNECTION_POOL.START_POOL`, then `CONFIGURE_POOL`/`ALTER_PARAM` on `SYS_DEFAULT_CONNECTION_POOL`. Defaults: `MINSIZE 4`, `MAXSIZE 40`, `INCRSIZE 2`, `SESSION_CACHED_CURSORS 20`, `INACTIVITY_TIMEOUT 300`s, `MAX_THINK_TIME 120`s (broker reclaims a server the client holds past this), `MAX_USE_SESSION 500000`, `MAX_LIFETIME_SESSION 86400`s. `MAXSIZE` caps concurrent *active* pooled servers, not clients. **23.4+**: `ADD_POOL`/`REMOVE_POOL` create named pools selected by `POOL_NAME` in the connect string. Multitenant: `ENABLE_PER_PDB_DRCP` (default `FALSE` = one CDB-wide pool managed from ROOT; `TRUE` = each PDB owns its config and broker sizing comes only from the `CONNECTION_BROKERS` init parameter).

## Implicit Connection Pooling & PRCP (26ai)

**26ai** adds **Implicit Connection Pooling**: set `POOL_BOUNDARY=TRANSACTION|STATEMENT` on a `SERVER=POOLED` descriptor and the broker maps/unmaps a session at request boundaries with **no client pool and no API calls**. `STATEMENT` releases when the session is stateless (all cursors fetched out, no open txn/temp LOB/temp table); `TRANSACTION` releases at commit/rollback. Gotcha: under `TRANSACTION`, a fetch after commit can raise `ORA-01001` and a temp LOB `ORA-22922` — the release already closed them. It engages only when `SERVER=POOLED` is also present. **PRCP** is DRCP fronted by CMAN in Traffic Director Mode (per-service or per-PDB pools) for proxy-side multiplexing across many app hosts.

## Oracle Net gotchas

- **Timeouts**: `TRANSPORT_CONNECT_TIMEOUT` bounds the TCP connect; `RETRY_COUNT`/`RETRY_DELAY` walk a multi-`ADDRESS` list — set them so a dead node fails fast, not hangs.
- **Dead sockets**: NAT/firewalls silently reap idle connections; the next borrow hands back a corpse. Use `EXPIRE_TIME` (client) / `SQLNET.EXPIRE_TIME` in minutes (server) for keepalive probes — **prefer it over `ENABLE=BROKEN`**, which thin drivers ignore. Keep client-pool max-lifetime under any middlebox idle timer.
- **Service, not SID**: connect by `SERVICE_NAME`; SID/`INSTANCE_NAME` are legacy and break RAC/PDB relocation. Multiple `ADDRESS`es with `LOAD_BALANCE`/`FAILOVER` plus FAN/Fast Connection Failover give HA and connection draining.
- **TLS**: TCPS with `WALLET_LOCATION` and `SSL_SERVER_DN_MATCH=TRUE` (verify the cert DN) — without DN match, TLS won't stop MITM. Native network encryption (`SQLNET.ENCRYPTION_*`) is a separate, wallet-free option.

## Limits, symptoms, monitoring

`PROCESSES` (range 80→OS-max, default derived from core count) caps OS processes that can connect at once; `SESSIONS`/`TRANSACTIONS` are **derived from it**. Exhaustion rejects logins with **ORA-00020** (max processes) / **ORA-00018** (max sessions); a listener with no matching handler (DRCP not started, wrong `SERVER=`, instance full) gives **ORA-12516/ORA-12520**. DRCP exists to keep server-process count flat under thousands of clients so you never reach these. Watch `V$CPOOL_STATS` (`NUM_MISSES` high = class churn; `NUM_WAITS` high = `MAXSIZE` too small), `V$CPOOL_CC_STATS` (per class), and `DBA_CPOOL_INFO` (config).

## Sources

- Oracle AI Database 26ai — Net Services Administrator's Guide, Understanding Service Handlers (dedicated/shared/pooled, connection broker): https://docs.oracle.com/en/database/oracle/oracle-database/26/netag/understanding-service-handlers.html
- Oracle AI Database 26ai — PL/SQL Packages and Types Reference, DBMS_CONNECTION_POOL (CONFIGURE_POOL/ADD_POOL defaults, ENABLE_PER_PDB_DRCP, CONNECTION_BROKERS): https://docs.oracle.com/en/database/oracle/oracle-database/26/arpls/DBMS_CONNECTION_POOL.html
- python-oracledb — Connection Handling & DRCP (connection class, purity SELF/NEW defaults, named pools 23.4, Implicit Connection Pooling requires 26ai, V$CPOOL views): https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html
- Oracle AI Database 26ai — Net Services Administrator's Guide, Oracle Connection Manager in Traffic Director Mode (Implicit Connection Pooling, POOL_BOUNDARY, PRCP, per-PDB pools): https://docs.oracle.com/en/database/oracle/oracle-database/26/netag/oracle-connection-manager-traffic-director-mode.html
- Oracle AI Database 26ai — Database Reference, PROCESSES (range 80→OS; SESSIONS/TRANSACTIONS derived): https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/PROCESSES.html

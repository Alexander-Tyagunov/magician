# Microsoft SQL Server — Connection & pooling

TDS behavior is cross-driver, but **pool knobs here are Microsoft.Data.SqlClient-only** — `mssql-jdbc`/`go-mssqldb` use external / `database/sql` pools. Current **2025 (17.x)**; 2017–2022 supported.

## Thread model

Thread-per-request (SQLOS), **not** process-per-connection; concurrency is capped by `max worker threads` (`0`=auto), not connection count. `user connections` defaults **`0` = 32,767 max** (dynamic; needs restart) — don't raise it to mask leaks.

## Client-side pooling (Microsoft.Data.SqlClient)

`Pooling=true` default. Pools key **per process, AppDomain, exact connection-string text, and (integrated security) Windows identity** — keyword order/whitespace forks another pool. `Max Pool Size`=**100**, `Min Pool Size`=**0**, `Connect Timeout`=**15s** (**30s** Azure). Saturated → requests queue to `Connect Timeout` then throw. Login/timeout failure → **blocking period** (5s, doubling to a 1-min cap), **off by default for Azure SQL**; tune `PoolBlockingPeriod`. Idle reaped ~**4–8 min**; `Load Balance Timeout`/`Connection Lifetime` (default `0`) caps connection age.

- **Reset on reuse:** `sp_reset_connection` rolls back transactions, drops temp tables, resets `SET` options and DB context to the connection's **default catalog (Initial Catalog)** — no state leak. Doesn't re-run login triggers; **can't** reset an activated app role (`sp_setapprole`) — that connection errors on reuse, so avoid app roles with pooling.
- **Always close/dispose** (`using`), or it isn't returned. `ClearPool`/`ClearAllPools` drop a poisoned pool (cleared on fatal errors, e.g. failover).
- **Fragmentation:** per-user integrated security or per-tenant strings multiply pools + idle sockets — use one common DB, then `USE`/`EXECUTE AS`.

## Encryption — default flipped

`Encrypt` defaults **`true`/Mandatory** in SqlClient **4.0+**, ODBC **18**, JDBC **10.2+** — cleartext upgrades fail without a trusted cert. SqlClient 5+ adds **`strict` = TDS 8.0** (TLS first, `TrustServerCertificate` ignored). With `TrustServerCertificate=false`, cert CN/SAN **must match** the server — use `HostNameInCertificate` (or `ServerCertificate` to pin), not `TrustServerCertificate=true`. 2025 adds **TLS 1.3 over TDS 8.0**.

## Connection resiliency & transient retry

`ConnectRetryCount` (**1** on-prem, **2** Azure SQL, **5** Azure serverless) × `ConnectRetryInterval` (**10s**) drive resiliency for **both** the initial `Open` (within `Connect Timeout`) **and** broken idle connections (within `Command Timeout`). They do **not** retry an in-flight command — mid-query + login-time transients (e.g. `40197, 40613, 11001`) still need app retry with backoff + jitter; make retried writes idempotent.

## HA/DR & Azure routing

- `ApplicationIntent=ReadOnly` → **read-only routing** to a readable AG secondary; pair with the listener. `MultiSubnetFailover=True` (default `False`) parallelizes across listener IPs — always set for listeners.
- **Azure SQL** fronts on a **1433** gateway. **Redirect** (default *inside* Azure) → the node (allow outbound **11000–11999**); **Proxy** (default *outside*) tunnels via 1433. Prefer Redirect where allowed.

## Sources

- learn.microsoft.com/sql/connect/ado-net/sql-server-connection-pooling · dotnet/api/microsoft.data.sqlclient.sqlconnection.connectionstring
- learn.microsoft.com/azure/azure-sql/database/{troubleshoot-common-connectivity-issues, connectivity-architecture}

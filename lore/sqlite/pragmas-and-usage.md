# SQLite — PRAGMAs & Usage

Embedded single-writer engine. Stable 3.53.x; WAL since 3.7.0. PRAGMAs are **file-persistent** (header), **connection-scoped** (reset on close), or **session-only**.

## Connection preamble (every new conn)

Per-connection PRAGMAs revert on close; each pooled connection re-applies them:

```sql
PRAGMA journal_mode = WAL;    -- file-persistent
PRAGMA synchronous = NORMAL;  -- per-conn; pair w/ WAL
PRAGMA foreign_keys = ON;     -- per-conn, default OFF
PRAGMA busy_timeout = 5000;   -- per-conn; lock retry ms
PRAGMA cache_size = -20000;   -- session; neg=KiB pos=pages
```

- **`foreign_keys` is OFF by default**, per-conn: FKs do nothing unless every conn sets it; can't toggle inside a transaction.
- **`journal_mode=WAL` persists** in the header (survives reopen, all conns). Other modes (DELETE/TRUNCATE/MEMORY/OFF) are per-conn, revert to DELETE. `cache_size` neg-as-KiB since 3.7.10.

## WAL vs rollback journal

Default is `DELETE`. WAL lets **readers and the writer not block each other, but only ONE writer at a time**. Use WAL for concurrent reads; keep DELETE for single-process or read-only media.

- WAL creates `-wal`/`-shm` sidecars. **The `-wal` is part of the database**: copying only `.db` loses committed data — `wal_checkpoint(TRUNCATE)` first, or copy all files.
- **WAL needs shared memory → fails over NFS/SMB** (all conns same-host). Read-only WAL needs 3.22.0+ plus existing sidecars, a writable dir, or `immutable=1`.
- `page_size` changes only at DB creation or via `VACUUM` in a rollback-journal mode — **never in WAL**. `auto_vacuum` must be set before any tables exist, else needs a full `VACUUM`.

## Checkpointing & durability

Auto-checkpoint (past `wal_autocheckpoint`, default 1000 pages) slows the committing COMMIT — for steady latency, disable it (`=0`) and run `wal_checkpoint(PASSIVE)` on a background thread. A long reader stalls the checkpointer, growing the WAL — keep read txns short. `synchronous=NORMAL`+WAL is atomic/consistent but may lose the last commits on power loss; use `FULL` if unacceptable.

## SQLITE_BUSY is normal

Even in WAL you hit `SQLITE_BUSY` when a second writer collides, a conn holds `locking_mode=EXCLUSIVE`, a conn closes, or a crashed DB recovers. Set `busy_timeout` AND make writes retryable. Wrap multi-statement writes in `BEGIN IMMEDIATE`, not bare `BEGIN` (DEFERRED upgrades to a write lock mid-txn → avoidable busy/deadlock).

## Threading & usage gotchas

- Default build is **serialized** (`SQLITE_THREADSAFE=1`): a connection is mutex-guarded; **multi-thread** builds forbid sharing one connection across threads — one per thread. Prefer per-thread connections over legacy **shared-cache** (discouraged).
- **Type affinity, not strict types**: the declared type is a hint, not a constraint. A column declared `INTEGER` still stores the string `'xyz'` as TEXT when it can't be losslessly converted (`typeof()` = `text`). Use `CREATE TABLE ... STRICT` (since 3.37.0) for real type enforcement.
- Run `PRAGMA optimize;` before closing long-lived connections (and `=0x10002` at open, then periodically) to keep `sqlite_stat1` fresh (self-limited via `analysis_limit`). Verify with `integrity_check` (`quick_check` skips UNIQUE); FK violations need `foreign_key_check`.

## Sources
- PRAGMA: https://www.sqlite.org/pragma.html
- Type affinity: https://www.sqlite.org/datatype3.html
- WAL: https://www.sqlite.org/wal.html
- Threads: https://www.sqlite.org/threadsafe.html

# SQLite — Concurrency and WAL

Version: 3.53.3 (2026-06) stable; behavior holds for all 3.7+ builds. SQLite is embedded and **single-writer**: locking is whole-file (no row/table locks), and transactions are SERIALIZABLE except shared-cache readers with `PRAGMA read_uncommitted=ON`. Gates: WAL + persistence since 3.7.0; WAL without `-shm` (`locking_mode=EXCLUSIVE`) since 3.7.4; large-txn parity since 3.11.0; read-only WAL opens since 3.22.0. A rare WAL-reset race (3.7.0–3.51.2) was fixed in 3.51.3 — prefer a current build.

## Two journal models
**Rollback (default, `journal_mode=DELETE`):** one writer OR many readers, never both. A writer climbs SHARED→RESERVED→PENDING→EXCLUSIVE; while EXCLUSIVE, readers block. Plain `BEGIN` is DEFERRED — no lock until the first statement (SHARED on first SELECT, RESERVED on first write).

**WAL (`PRAGMA journal_mode=WAL`):** readers never block the writer and vice versa; still exactly one writer at a time. Readers see a snapshot fixed at their read's "end mark" (snapshot isolation). WAL is **persistent** (survives close/reopen) and applies to every connection once set — enable it once at startup. Its sidecar `-wal`/`-shm` files are part of the database state: copy/move them together, never delete `-wal` by hand.

## The deferred-transaction deadlock (the #1 real bug)
Two connections each `BEGIN` (deferred), each read (take a read lock), then each try to write. One gets RESERVED; the other's upgrade fails — `SQLITE_BUSY` (rollback) or `SQLITE_BUSY_SNAPSHOT` (WAL). A busy timeout **cannot** rescue it: both hold locks, so waiting deadlocks. Fix: start any writing transaction with `BEGIN IMMEDIATE` (takes the write lock up front); once it succeeds, no later statement in that txn returns `SQLITE_BUSY`. `BEGIN EXCLUSIVE` also blocks new readers (rollback only; = IMMEDIATE under WAL). Set `PRAGMA busy_timeout=<ms>` (default 0 = fail instantly) on every connection — it only helps when the blocker will release. On `SQLITE_BUSY_SNAPSHOT`, `ROLLBACK` and retry the whole transaction from a fresh `BEGIN IMMEDIATE` — never replay just the failed statement.

## Checkpointing & durability
The WAL grows until a checkpoint folds it into the main file. Auto-checkpoint fires at **1000 pages** (`PRAGMA wal_autocheckpoint=N`, 0 disables) and is always PASSIVE — it silently skips work while readers/writers are active, so a busy WAL can grow unbounded and slow reads (read cost scales with WAL size). Run `PRAGMA wal_checkpoint(TRUNCATE)` periodically on a dedicated connection to reset it. Pair WAL with `PRAGMA synchronous=NORMAL` (documented WAL sweet spot: fsync only at checkpoint, still consistent, may lose the last commit on power loss); use `FULL`/`EXTRA` for full durability. `FULL` is the rollback default.

## DON'T
- DON'T put a SQLite file on NFS/SMB or any network FS — WAL needs shared memory (`-shm`) across processes on one host; cross-host access corrupts.
- DON'T hold a read transaction open across think-time under WAL: a reader's end mark caps checkpoint progress, so the WAL bloats.
- DON'T change `page_size` after entering WAL (switch to a rollback mode first); DON'T open a WAL DB with a pre-3.7.0 SQLite — it reports "not a database".
- DON'T rely on `BEGIN CONCURRENT` — it lives only in an experimental branch, not the standard release; mainline stays single-writer.
- DON'T mutate a table while stepping a SELECT on the same connection — visibility of those rows is undefined (they may repeat or reappear).

## Sources
- sqlite.org/wal.html (WAL mode, checkpointing, sidecar files, same-host requirement, gates)
- sqlite.org/lockingv3.html (rollback lock states, deferred acquisition, SQLITE_BUSY)
- sqlite.org/isolation.html (serializable isolation, snapshot reads, SQLITE_BUSY_SNAPSHOT)
- sqlite.org/pragma.html (busy_timeout, synchronous, wal_autocheckpoint, journal_mode, locking_mode)

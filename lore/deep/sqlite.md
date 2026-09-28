# SQLite — deep dive

> On-demand companion to `lore/sqlite.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [PRAGMAs & Usage](#pragmas-and-usage) · [Concurrency and WAL](#concurrency-and-wal) · [Types and limits](#types-and-limits) · [Performance](#performance)

## PRAGMAs & Usage <a id="pragmas-and-usage"></a>

Embedded single-writer engine. Stable 3.53.x; WAL since 3.7.0. PRAGMAs are **file-persistent** (header), **connection-scoped** (reset on close), or **session-only**.

### Connection preamble (every new conn)

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

### WAL vs rollback journal

Default is `DELETE`. WAL lets **readers and the writer not block each other, but only ONE writer at a time**. Use WAL for concurrent reads; keep DELETE for single-process or read-only media.

- WAL creates `-wal`/`-shm` sidecars. **The `-wal` is part of the database**: copying only `.db` loses committed data — `wal_checkpoint(TRUNCATE)` first, or copy all files.
- **WAL needs shared memory → fails over NFS/SMB** (all conns same-host). Read-only WAL needs 3.22.0+ plus existing sidecars, a writable dir, or `immutable=1`.
- `page_size` changes only at DB creation or via `VACUUM` in a rollback-journal mode — **never in WAL**. `auto_vacuum` must be set before any tables exist, else needs a full `VACUUM`.

### Checkpointing & durability

Auto-checkpoint (past `wal_autocheckpoint`, default 1000 pages) slows the committing COMMIT — for steady latency, disable it (`=0`) and run `wal_checkpoint(PASSIVE)` on a background thread. A long reader stalls the checkpointer, growing the WAL — keep read txns short. `synchronous=NORMAL`+WAL is atomic/consistent but may lose the last commits on power loss; use `FULL` if unacceptable.

### SQLITE_BUSY is normal

Even in WAL you hit `SQLITE_BUSY` when a second writer collides, a conn holds `locking_mode=EXCLUSIVE`, a conn closes, or a crashed DB recovers. Set `busy_timeout` AND make writes retryable. Wrap multi-statement writes in `BEGIN IMMEDIATE`, not bare `BEGIN` (DEFERRED upgrades to a write lock mid-txn → avoidable busy/deadlock).

### Threading & usage gotchas

- Default build is **serialized** (`SQLITE_THREADSAFE=1`): a connection is mutex-guarded; **multi-thread** builds forbid sharing one connection across threads — one per thread. Prefer per-thread connections over legacy **shared-cache** (discouraged).
- **Type affinity, not strict types**: the declared type is a hint, not a constraint. A column declared `INTEGER` still stores the string `'xyz'` as TEXT when it can't be losslessly converted (`typeof()` = `text`). Use `CREATE TABLE ... STRICT` (since 3.37.0) for real type enforcement.
- Run `PRAGMA optimize;` before closing long-lived connections (and `=0x10002` at open, then periodically) to keep `sqlite_stat1` fresh (self-limited via `analysis_limit`). Verify with `integrity_check` (`quick_check` skips UNIQUE); FK violations need `foreign_key_check`.

### Sources
- PRAGMA: https://www.sqlite.org/pragma.html
- Type affinity: https://www.sqlite.org/datatype3.html
- WAL: https://www.sqlite.org/wal.html
- Threads: https://www.sqlite.org/threadsafe.html

## Concurrency and WAL <a id="concurrency-and-wal"></a>

Version: 3.53.3 (2026-06) stable; behavior holds for all 3.7+ builds. SQLite is embedded and **single-writer**: locking is whole-file (no row/table locks), and transactions are SERIALIZABLE except shared-cache readers with `PRAGMA read_uncommitted=ON`. Gates: WAL + persistence since 3.7.0; WAL without `-shm` (`locking_mode=EXCLUSIVE`) since 3.7.4; large-txn parity since 3.11.0; read-only WAL opens since 3.22.0. A rare WAL-reset race (3.7.0–3.51.2) was fixed in 3.51.3 — prefer a current build.

### Two journal models
**Rollback (default, `journal_mode=DELETE`):** one writer OR many readers, never both. A writer climbs SHARED→RESERVED→PENDING→EXCLUSIVE; while EXCLUSIVE, readers block. Plain `BEGIN` is DEFERRED — no lock until the first statement (SHARED on first SELECT, RESERVED on first write).

**WAL (`PRAGMA journal_mode=WAL`):** readers never block the writer and vice versa; still exactly one writer at a time. Readers see a snapshot fixed at their read's "end mark" (snapshot isolation). WAL is **persistent** (survives close/reopen) and applies to every connection once set — enable it once at startup. Its sidecar `-wal`/`-shm` files are part of the database state: copy/move them together, never delete `-wal` by hand.

### The deferred-transaction deadlock (the #1 real bug)
Two connections each `BEGIN` (deferred), each read (take a read lock), then each try to write. One gets RESERVED; the other's upgrade fails — `SQLITE_BUSY` (rollback) or `SQLITE_BUSY_SNAPSHOT` (WAL). A busy timeout **cannot** rescue it: both hold locks, so waiting deadlocks. Fix: start any writing transaction with `BEGIN IMMEDIATE` (takes the write lock up front); once it succeeds, no later statement in that txn returns `SQLITE_BUSY`. `BEGIN EXCLUSIVE` also blocks new readers (rollback only; = IMMEDIATE under WAL). Set `PRAGMA busy_timeout=<ms>` (default 0 = fail instantly) on every connection — it only helps when the blocker will release. On `SQLITE_BUSY_SNAPSHOT`, `ROLLBACK` and retry the whole transaction from a fresh `BEGIN IMMEDIATE` — never replay just the failed statement.

### Checkpointing & durability
The WAL grows until a checkpoint folds it into the main file. Auto-checkpoint fires at **1000 pages** (`PRAGMA wal_autocheckpoint=N`, 0 disables) and is always PASSIVE — it silently skips work while readers/writers are active, so a busy WAL can grow unbounded and slow reads (read cost scales with WAL size). Run `PRAGMA wal_checkpoint(TRUNCATE)` periodically on a dedicated connection to reset it. Pair WAL with `PRAGMA synchronous=NORMAL` (documented WAL sweet spot: fsync only at checkpoint, still consistent, may lose the last commit on power loss); use `FULL`/`EXTRA` for full durability. `FULL` is the rollback default.

### DON'T
- DON'T put a SQLite file on NFS/SMB or any network FS — WAL needs shared memory (`-shm`) across processes on one host; cross-host access corrupts.
- DON'T hold a read transaction open across think-time under WAL: a reader's end mark caps checkpoint progress, so the WAL bloats.
- DON'T change `page_size` after entering WAL (switch to a rollback mode first); DON'T open a WAL DB with a pre-3.7.0 SQLite — it reports "not a database".
- DON'T rely on `BEGIN CONCURRENT` — it lives only in an experimental branch, not the standard release; mainline stays single-writer.
- DON'T mutate a table while stepping a SELECT on the same connection — visibility of those rows is undefined (they may repeat or reappear).

### Sources
- sqlite.org/wal.html (WAL mode, checkpointing, sidecar files, same-host requirement, gates)
- sqlite.org/lockingv3.html (rollback lock states, deferred acquisition, SQLITE_BUSY)
- sqlite.org/isolation.html (serializable isolation, snapshot reads, SQLITE_BUSY_SNAPSHOT)
- sqlite.org/pragma.html (busy_timeout, synchronous, wal_autocheckpoint, journal_mode, locking_mode)

## Types and limits <a id="types-and-limits"></a>

Dynamic-typing and hard-limit semantics for SQLite 3.5x (current stable ~3.53, 2026-06; back to 3.37). SQLite binds a datatype to each *value*, not the column — the biggest surprise from statically typed engines.

### Storage classes vs. affinity

- Every value is one of **five storage classes**: NULL, INTEGER (0/1/2/3/4/6/8 bytes on disk, loaded as 64-bit signed), REAL (8-byte IEEE double), TEXT, BLOB (verbatim). There is **no BOOLEAN, DATE, DATETIME, or DECIMAL class** — `TRUE`/`FALSE` (keywords since 3.23.0) are literally `1`/`0`.
- A declared type only sets an **affinity** (a recommendation, not a constraint), derived from substrings in order: contains `INT`→INTEGER; else `CHAR`/`CLOB`/`TEXT`→TEXT; else `BLOB`/no type→BLOB; else `REAL`/`FLOA`/`DOUB`→REAL; else→NUMERIC.
- **Gotchas:** `FLOATING POINT`→INTEGER (matches "INT"); `STRING`→NUMERIC (no "CHAR"); `VARCHAR(255)`→TEXT but `(255)` is *ignored* — SQLite enforces **no length limits** on any declared type. A no-type column gets BLOB affinity and coerces nothing.
- NUMERIC/INTEGER/REAL affinity coerce a text literal to a number only when it round-trips losslessly; hex literals (`0x…`) stay TEXT. `CAST(4.0 AS INT)`→`4` but `CAST(4.0 AS NUMERIC)`→`4.0` — the only difference between the two affinities.

### Comparison, sort, and coercion order

- Cross-class ordering is fixed: **NULL < integers/reals (numeric) < TEXT (collation) < BLOB (memcmp)**, so one column holding both `'5'` (text) and `5` (int) sorts them apart. `ORDER BY` does no coercion; `GROUP BY` keeps classes distinct except numerically-equal INTEGER/REAL; set ops apply **no** affinity.
- Before a comparison, affinity applies to the *other* operand only if lossless. Any operator strips a column's affinity — `WHERE x='5'` uses it, `WHERE +x='5'` does not (a classic index-defeating footgun).

### STRICT tables (3.37.0+) — opt into rigidity

- `CREATE TABLE t(a INT, b TEXT, c ANY) STRICT;` — every column **must** name a type, and only `INT INTEGER REAL TEXT BLOB ANY` are allowed. Bad content raises `SQLITE_CONSTRAINT_DATATYPE` rather than silently storing the wrong class; use it for schema-critical data.
- In a STRICT table `ANY` preserves values exactly (`'000123'` stays text); an ordinary `ANY`/no-type column coerces it to integer `123`.
- `INTEGER PRIMARY KEY` is still a rowid alias (NULL auto-assigns a rowid); `INT PRIMARY KEY` is **not** — STRICT does not change this. Combine with `WITHOUT ROWID` in any order.

### Implementation limits (defaults; many settable via `sqlite3_limit`/PRAGMA/compile flags)

- **Bound params** `SQLITE_MAX_VARIABLE_NUMBER`: **999** before 3.32.0, **32766** since — oversized `IN (?,?,…)`/bulk inserts throw "too many SQL variables"; batch or use `carray`/JSON.
- **Columns** 2000 (max 32767); **join tables** hard-capped at **64** (bitmask); **compound SELECT** 500; **expr depth** 1000; **function args** 100→**1000 since 3.48.0**.
- **String/BLOB length** `SQLITE_MAX_LENGTH` 1 GB (max 2³¹−3); a row is encoded as one BLOB, so this also caps row size.
- **DB size**: `SQLITE_MAX_PAGE_COUNT` default became **2³²−2 pages** in 3.45.0; page 512–65536 B → ~17.5 TB at 4 KiB. **Attached DBs** default 10 (ceiling 125).

### Sources
- Datatypes / affinity / comparison: https://www.sqlite.org/datatype3.html
- STRICT tables: https://www.sqlite.org/stricttables.html
- Implementation limits: https://www.sqlite.org/limits.html

## Performance <a id="performance"></a>

SQLite is **in-process**: no network round-trips, so perf is dominated by **transaction commits (fsync) and I/O**, not client/server chatter. Fix them in this order. Stable 3.53.x; behavior holds for 3.7+. Complements the shared `lore/deep/databases.md`; cross-refs `lore/deep/sqlite.md#{pragmas-and-usage,concurrency-and-wal}`.

### Do these first (highest leverage)

1. **Batch writes into ONE transaction.** Per-statement autocommit is the #1 killer: each INSERT/UPDATE fsyncs, capping you at a few dozen commits/sec on spinning disks (SSD is faster, but the amortization win is huge). Wrap bulk writes in `BEGIN IMMEDIATE … COMMIT`. DON'T loop single autocommit writes. Use `IMMEDIATE` (not bare `BEGIN`) to take the write lock up front — avoids the deferred-txn deadlock (see `lore/deep/sqlite.md#concurrency-and-wal`).
2. **Enable WAL** (`PRAGMA journal_mode=WAL`, persists in the header) + **`PRAGMA synchronous=NORMAL`** — the documented WAL sweet spot: fsync only at checkpoint, readers never block the writer. Detail + checkpoint tuning in `lore/deep/sqlite.md#concurrency-and-wal`.
3. **Reuse prepared statements.** Prepare once, `bind` + `reset`/`step` per row — never rebuild SQL strings in a loop (re-parse + replan each call). Also blocks injection (`lore/deep/databases.md#parameterized-queries-and-injection`).
4. **Set `PRAGMA busy_timeout`** (default 0 = fail instantly) so lock collisions retry instead of erroring under concurrency.

### Then tune memory & I/O (PRAGMAs; see lore/deep/sqlite.md#pragmas-and-usage)

- **`cache_size = -N`** → ~N KiB page cache (default `-2000` ≈ 2 MB). Raise it so the working set (esp. index B-trees) stays resident. Positive N = pages, negative = KiB (since 3.7.10).
- **`mmap_size = N`** enables memory-mapped reads (default off/compile-dependent; capped by `SQLITE_MAX_MMAP_SIZE`) — cuts read syscall overhead for read-heavy loads.
- **`page_size`** default 4096 (since 3.12.0); change only before first write or via `VACUUM` in a rollback mode, **never in WAL**.

### Indexes & the planner

- Add indexes matching WHERE/JOIN/ORDER BY; aim for **covering indexes** (all selected cols in the index → no table lookup). Depth: `lore/deep/databases.md#indexing-and-query-plans`.
- **Keep stats fresh:** run `PRAGMA optimize;` before closing short-lived conns; `PRAGMA optimize=0x10002;` at open + periodically for long-lived ones; and after any `CREATE INDEX`. It auto-runs `ANALYZE` (writing `sqlite_stat1`) with a built-in scope limit since 3.46.0. Stale/missing stats → bad plans.

### DON'T

- **DON'T put the DB on NFS/SMB/network FS** — file locking + WAL shared-memory break there → corruption/`SQLITE_BUSY`. Keep it local.
- DON'T reach for `synchronous=OFF` — faster writes, but a crash mid-write can corrupt the file. Prefer batching + WAL/NORMAL.
- DON'T let the WAL bloat (long-held read txns stall checkpoints) — read cost scales with WAL size.

### How to measure (SEE the problem)

- **`EXPLAIN QUERY PLAN <stmt>`** (CLI: `.eqp on`): `SCAN t` = full-table scan (add/adjust an index); `SEARCH t USING [COVERING] INDEX` = good; `USE TEMP B-TREE FOR ORDER BY` = missing sort index. Output is debug-only, format may change across releases.
- CLI **`.timer on`** + **`.stats on`** for wall time and cache-miss/fullscan counters; plain `EXPLAIN` dumps VDBE bytecode when EQP isn't enough.
- **`sqlite3_analyzer`** for on-disk page/fragmentation stats; `PRAGMA compile_options;` to confirm threadsafe/STAT4 build.

### Sources
- INSERT speed / transactions: https://www.sqlite.org/faq.html
- EXPLAIN QUERY PLAN: https://www.sqlite.org/eqp.html
- PRAGMA (cache_size, mmap_size, synchronous, busy_timeout): https://www.sqlite.org/pragma.html
- ANALYZE / PRAGMA optimize: https://www.sqlite.org/lang_analyze.html
- WAL mode: https://www.sqlite.org/wal.html

# Redis — Persistence & eviction

Versions: Redis 8.x current stable (LRM policy 8.6+). Commands execute **single-threaded** (I/O threads handle only socket I/O). License: BSD-3 through 7.2; dual RSALv2/SSPLv1 for the 7.4 line; **tri-license RSALv2/SSPLv1/AGPLv3 since 8.0** (AGPLv3 the sole OSI-approved option). Valkey is the BSD-3 Linux-Foundation fork (9.x).

## Two engines — DO pick per durability need
- **RDB (snapshot):** point-in-time `dump.rdb` via `save <sec> <changes>` (e.g. `save 60 1000`) or `BGSAVE`; `SAVE` blocks — never in prod. Compact, fast restarts, great for backups/DR — but **loses everything since the last snapshot**.
- **AOF (append-only):** `appendonly yes` logs each write in RESP. `appendfsync everysec` (default; ≤1s loss, background fsync), `always` (per batch, slow), or `no` (OS flushes, ~30s). Since 7.0 the AOF is **multi-part** (base + incremental files + manifest) under `appenddirname` (default `appendonlydir`).
- **RDB+AOF together:** on restart the **AOF wins** (most complete). `aof-use-rdb-preamble yes` (default) makes the base an RDB image → smaller, faster load.

## Rewrites & fork cost — DON'T ignore COW
- AOF grows unbounded; compacted by `BGREWRITEAOF`, auto-fired at `auto-aof-rewrite-percentage 100` + `auto-aof-rewrite-min-size 64mb`.
- Every snapshot/rewrite `fork()`s; the parent serves via copy-on-write. **Fork pauses the main thread** (µs–seconds on big datasets; up to ~2× RAM on full churn). Set `vm.overcommit_memory=1`, disable THP, keep RAM headroom. BGSAVE and rewrite are serialized.
- Truncated tail: `aof-load-truncated yes` (default) loads anyway; real corruption → `redis-check-aof --fix`.

## Eviction — DO set maxmemory + a policy (it's a cache)
- `maxmemory` default `0` = unlimited (64-bit; 32-bit implicit 3GB) → OOM / OS-kill risk. `maxmemory-policy` default **`noeviction`** (writes fail with an OOM error; reads serve).
- Policies: `allkeys-lru|lfu|random`, `volatile-lru|lfu|random|ttl`. `volatile-*` touch only keys with a TTL and act like `noeviction` when none have one. `allkeys-lru` is the sane default; `allkeys-lfu` for skewed hot sets; `volatile-ttl` with meaningful TTLs.
- LRU/LFU are **approximated** by sampling: `maxmemory-samples 5` (raise to 10 for near-true LRU at CPU cost). LFU tuning: `lfu-log-factor 10`, `lfu-decay-time 1`.
- Eviction runs **inline in the command path** — the single thread evicts before serving the write, so it steals throughput; a big multi-key write can transiently overshoot `maxmemory`. Repl/AOF buffers don't count toward the evict total — leave headroom.

## Expiration — DO pair TTLs with eviction
Passive (lazy) delete on access + active background sampling (~10 Hz) of volatile keys. Replicas never expire on their own — they serve a stale key until the primary propagates `DEL`/`UNLINK`. Each TTL costs a few bytes.

## Measure
`INFO persistence` (`rdb_last_bgsave_status`, `aof_last_bgrewrite_status`, `latest_fork_usec`), `INFO stats` (`evicted_keys`, `expired_keys`, `keyspace_hits/misses`), `INFO memory` (`used_memory`, `mem_not_counted_for_evict`). See lore/redis/{performance,clustering-and-ha,data-structures-and-patterns}.md and lore/databases/{resilience-and-observability,connection-pooling}.md.

## Sources
- https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- https://redis.io/docs/latest/develop/reference/eviction/
- https://redis.io/legal/licenses/ · https://valkey.io/

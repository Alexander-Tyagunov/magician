# Redis — core digest
Version: 8.x (8.8 latest mid-2026); span 7.x/8.x. License: BSD-3 (≤7.2) → RSALv2/SSPLv1 (7.4) → 8.0 adds AGPLv3 (tri-license; only it is OSI-approved). Valkey = BSD/Linux-Foundation fork (9.1). Single-threaded exec (I/O threads aside): one slow command stalls all clients.

DO set `maxmemory` + `maxmemory-policy` (default `noeviction` errors on write) — RAM is THE limit; size values, big/hot keys concentrate load.
DO keep O(N) cmds (KEYS/SMEMBERS/HGETALL/LRANGE) off the hot path; keyed access is ~O(1).
DO iterate with SCAN/HSCAN (cursor), never KEYS/FLUSH* in prod.
DO cut round-trips: pipeline, MGET/MSET, MULTI/EXEC; pool connections.
DO cache-aside/write-through + TTLs; jitter + single-flight vs stampedes; invalidation is hard.
DO choose durability: RDB vs AOF (appendfsync); not a system of record by default.
DO in Cluster respect 16384 hash slots: multi-key needs one slot, `{hashtag}` co-locates; handle MOVED/ASK.

DON'T run without maxmemory+policy — OOM/swap wrecks latency.
DON'T ship O(N) or huge MULTI on the hot path.
DON'T assume durability/HA by default — set AOF/RDB + Sentinel/Cluster.
DON'T expect server-side JOINs or cross-slot multi-key.

Deep dive when writing non-trivial Redis — read lore/redis/{data-structures-and-patterns,persistence-and-eviction,clustering-and-ha,performance}.md

## Sources
redis.io/docs/latest/{develop/reference/eviction,commands/scan} · redis.io/legal/licenses · valkey.io (2026-07)

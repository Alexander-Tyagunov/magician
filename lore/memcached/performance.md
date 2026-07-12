# Memcached — Performance

Ordered playbook: fix the biggest lever first, measure every change. Memcached IS multithreaded (scales with cores — unlike single-threaded Redis), so the ceilings are RAM, round-trips, and slab layout, not CPU. Verified 1.6.x; depth in the deep-dives.

## 0. Measure first — read `stats` before tuning
- DO baseline: `stats` (`get_hits`/`get_misses`→hit ratio, `evictions`, `expired_unfetched`, `reclaimed`), `stats settings`, `stats slabs`/`stats items` (per-class chunks, evictions, age). Connection exhaustion shows as `listen_disabled_num` — keep it ~0.
- DO load-test with `mc-crusher` at real key sizes and multiget width.
- DO use `stats sizes` for slab-class alignment (needs `-o track_sizes` at start; the old item-walking form that hung the server was removed, safe 1.4.27+). `stats cachedump` is capped, debug-only.

## 1. Cut round-trips (top latency lever)
- DO batch reads with MULTIGET, pipeline writes with meta quiet flags (not ASCII `noreply`); network RTT dwarfs the sub-µs command time. Keep long-lived pooled connections — see lore/databases/connection-pooling.md.
- DON'T open/close a connection per op — the TCP handshake becomes your latency.

## 2. Cap RAM + defeat slab calcification (RAM is THE constraint)
- DO set `-m` to your working set; items evict per-class LRU as slabs fill. Keep `slab_automove` on (default 1; `=2` aggressive) so whole pages migrate to pressured classes; keep `lru_maintainer` on for segmented LRU (HOT/WARM/COLD/TEMP). Tune growth factor `-f` (default 1.25) and right-size values to the slab grid. Detail: lore/memcached/usage-and-slabs.md.
- DON'T ignore rising `evictions` on one class while RAM looks free — that's calcification; rebalance or resize items.

## 3. Protect the hit ratio (TTLs, stampedes, hot keys)
- DO run cache-aside with TTLs + jitter to spread expiry; gate recompute with an `add`-lock or soft-TTL to stop thundering herds. Hit ratio = `get_hits/(get_hits+get_misses)`.
- DON'T let one big or hot key dominate a class/node — split it or add a client-local tier.

## 4. Mind the multiget hole at scale (fan-out)
- DO keep multiget batches bounded — at many nodes each fans out all-to-all, so p99 tracks the slowest node. Co-locate related keys via a shared hash prefix. See lore/memcached/scaling-and-hashing.md.

## 5. Tune threads & connections
- DO leave `-t` near default 4; raise only under extreme load (80+ runs slower). Size `-c` (default 1024) with headroom; favor persistent connections over reconnect churn (watch `TIME_WAIT`).

## 6. Overflow to flash when the set outgrows RAM (extstore)
- DO enable extstore (`-o ext_path=/data:100G`, `ext_threads`): hash table, keys, and item headers stay in RAM, values go to SSD (~12 bytes/item flash pointer). Set `ext_item_size` so only worthwhile items flush.

## Anti-patterns
- DON'T `flush_all` in prod expecting freed RAM — it only marks items expired. DON'T raise `-I` above ~1MB casually; big items churn the LRU. DON'T change node count on a naive-modulo client — you cold-flush the cache; use ketama. DON'T rely on wall-clock for absolute (unix-timestamp) TTLs — a clock jump skews them; relative TTLs use memcached's monotonic clock.

Timeout/retry/observability: lore/databases/resilience-and-observability.md.

## Sources
- docs.memcached.org/features/flashstorage/ · /protocols/meta/ (2026-07)
- github.com/memcached/memcached/wiki/{Performance,ConfiguringServer,ServerMaint,ReleaseNotes1645}

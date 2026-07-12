# Memcached — Usage & Slabs

Version: 1.6.x current (1.6.45, mid-2026). Pure in-memory cache: NO persistence (restart loses all — data must be disposable), NO server-side clustering (client-side sharding). RAM is THE constraint.

## Protocol & connecting
- DO prefer the meta protocol (`mg`/`ms`/`md`/`ma`): flag-driven, folds get+touch+CAS+TTL with real quiet semantics. Legacy ASCII (`set`/`get`…) works; the old binary protocol is deprecated.
- DO pool + reuse connections; defaults `-c` 1024 conns, `-t` 4 threads (threaded, unlike Redis). Exhaustion → `listen_disabled_num`. See lore/databases/connection-pooling.md.
- DON'T use ASCII `noreply` on mutations — errors can't align to requests; use meta quiet flags.

## Core commands (keyed, ~O(1))
- Storage: `set` (upsert), `add` (only if absent — good for locks), `replace` (only if present), `append`/`prepend` (ignore new flags/exptime), `cas` (conditional).
- Retrieval: `get`, `gets` (adds CAS token). MULTIGET — `get k1 k2 k3…` in ONE round trip: the biggest latency lever. Also `delete`, `touch`, `gat`/`gats`.
- `incr`/`decr`: atomic on 64-bit unsigned int text; key must pre-exist + be numeric; decr floors at 0, incr wraps; `set` it first.
- DON'T treat it as a datastore: no queries, scans, secondary indexes, or cross-key transactions.

## Expiration, flags, CAS
- TTL: `0`=never; `1..2592000` (≤30d)=relative seconds; larger=absolute Unix timestamp; past/negative=expire now. `now+31d` as seconds silently means "1970".
- Expiry is LAZY (on access); `lru_crawler` reclaims dead items — RAM held past TTL until then.
- `flags`: opaque 32-bit per item. CAS: `gets`→token, `cas` writes only if unchanged — optimistic concurrency; retry on mismatch.

## Slab allocator & item size
- `-m` (default 64MB) pool is cut into 1MB PAGES; each page goes to a slab CLASS diced into equal CHUNKS. Classes grow by `-f` (default 1.25): ~80B, 104B, 136B… up to 1MB.
- An item lands in the smallest class that fits — the tail is wasted (internal fragmentation). Item size = key + value + overhead (~48–80B; check the `sizes` tool). Right-size values; tune `-f`.
- Default MAX ITEM 1MB; raise with `-I` (e.g. `-I 2m`), but big items waste chunk space and churn the LRU — prefer splitting blobs.

## Calcification, eviction, rebalancing
- A PAGE IS BOUND TO ITS CLASS FOR LIFE. If item sizes shift later → slab CALCIFICATION: one class evicts hot data while another sits on free pages.
- Eviction is PER-CLASS LRU, not global — a full class evicts its own tail even with RAM free elsewhere. Watch `evictions`, `expired_unfetched`, `reclaimed` in `stats items`.
- Modern defaults fight this: slab_automove (default 1; `-o slab_automove=2` aggressive) rebalances pages to pressured classes; segmented LRU (HOT/WARM/COLD + TEMP) via `lru_maintainer` keeps hot items resident.

## Idioms
- DO cache-aside with TTLs + jitter; batch reads via multiget; check `stats slabs`/`stats items` before tuning.
- DON'T lean on `flush_all` in prod (marks all expired), assume durability, or let one giant/hot key dominate a class.
- Working set > RAM: overflow values to SSD with extstore (keys + metadata stay in RAM) — see lore/memcached/performance.md and lore/memcached/scaling-and-hashing.md.

## Sources
- docs.memcached.org/protocols/basic/ · /protocols/meta/ · /features/lru/ (2026-07)
- github.com/memcached/memcached/wiki/{UserInternals,ConfiguringServer,Commands,ReleaseNotes}

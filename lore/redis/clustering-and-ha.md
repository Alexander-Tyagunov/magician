# Redis — Clustering & HA

Versions: Redis 8.8 stable — tri-license RSALv2/SSPLv1/AGPLv3 since 8.0; dual RSALv2/SSPLv1 for the 7.4 line; BSD-3 through 7.2. Valkey 9.1 is the BSD-3-Clause, Linux-Foundation fork (wire/cluster compatible). Command execution stays **single-threaded** (I/O threading aside): one slow command blocks only its own shard, but a hot slot pins that shard's load on one core.

## Two different tools — DON'T conflate
- **Redis Cluster** = automatic sharding across masters **plus** built-in failover. Use it to scale past one node's RAM/CPU.
- **Sentinel** = HA for a **single, non-sharded** master + replicas (monitoring, automatic failover, client service-discovery). No sharding. Don't put Sentinel in front of a Cluster — Cluster fails itself over.

## Cluster mechanics — DO
- Keyspace = **16384 hash slots**; slot = `CRC16(key) mod 16384`. Each master owns a slot range; slots migrate online with **no downtime** (resharding).
- Multi-key ops (MGET/MSET, MULTI/EXEC, Lua) require **all keys in one slot**, else `CROSSSLOT` error. Co-locate with a **hash tag** — only the substring in `{}` is hashed, so `user:{42}:profile` and `user:{42}:cart` share a slot. DON'T over-wrap `{}` until everything collapses onto one slot (hot shard).
- Use a **cluster-aware client** caching the slot map (`CLUSTER SHARDS`). On **`MOVED`** refresh the map (slot relocated permanently); on **`ASK`** send `ASKING` + retry that one command (slot mid-migration) — don't rebuild the whole map.
- Deploy **≥3 masters**; recommended shape is **6 nodes = 3 masters + 3 replicas** (`--cluster-replicas 1`), spread across failure domains. A master whose slots lose every live replica can fail the cluster.

## Availability & consistency — the tradeoff
- Replication is **asynchronous**: the master ACKs the client, then propagates — a crash before propagation **loses acknowledged writes**. `WAIT numreplicas timeout` blocks until N replicas ack (stronger, still not full sync).
- `cluster-node-timeout` drives failure detection/failover; a node that can't reach a **majority of masters** stops serving. Default `cluster-require-full-coverage yes` halts the whole cluster if any slot is unowned — flip `cluster-allow-reads-when-down` only if stale reads are acceptable.
- Sentinel: **run ≥3, never 2**, on independent hosts. `quorum` = sentinels needed to mark a master `ODOWN` (objectively down; a lone sentinel's view is `SDOWN`). But a failover needs a **majority** of all sentinels to elect a leader — so none happens in a minority partition. Clients resolve the master via `SENTINEL get-master-addr-by-name`.

## DON'T
- Fan `KEYS`, `FLUSHALL`, or wide `MGET` across the cluster as if it were one node — each key maps to a specific shard.
- Equate failover with zero data loss; quantify the write-loss window and gate critical writes behind `WAIT`.
- Read from replicas expecting freshness (`READONLY` is a conscious choice) — replication lag serves stale data.

Deep dive: lore/redis/{data-structures-and-patterns,persistence-and-eviction,performance}.md and lore/databases/{connection-pooling,resilience-and-observability}.md.

## Sources
redis.io/docs/latest/operate/oss_and_stack/management/scaling · .../management/sentinel · redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec · redis.io/legal/licenses · valkey.io/download

# Apache Cassandra — Consistency & Replication

Current stable **5.0** (GA); spans 3.x/4.x/5.0. Cassandra is AP-leaning: it favors Availability + Partition-tolerance and offers **tunable, per-operation consistency** — a Dynamo-style `R + W > RF` knob, not ACID. Guarantees are **per single partition**; no cross-partition transactions. ScyllaDB is wire/CQL-compatible and shares these semantics (version gates differ).

## Tunable consistency — set it per query, not per cluster
CL is chosen **per statement** (driver `ConsistencyLevel`), independently for reads and writes. For read-your-writes on `RF=3`: `QUORUM` write + `QUORUM` read (2+2>3 overlaps). Multi-DC: use **`LOCAL_QUORUM`** as the default — it stays in the local DC (no cross-DC latency) yet is strong *within* that DC. Levels: `ONE`/`TWO`/`THREE`, `QUORUM` (`n/2+1` over all replicas), `LOCAL_QUORUM`, `EACH_QUORUM` (writes only), `ALL`, `LOCAL_ONE`, `ANY` (write-only; a stored hint counts). Writes are **always sent to all replicas**; CL only sets how many acks the coordinator awaits. CL alone doesn't make stale replicas converge — schedule repair.

## Replication strategy & RF
DO use **`NetworkTopologyStrategy`** in every real cluster; set RF **per datacenter** (`{'class':'NetworkTopologyStrategy','dc1':3}`) — it places replicas across racks via the snitch. `SimpleStrategy` is DC/rack-blind — test only. RF = copies of each partition (distinct nodes). **Transient replication** is experimental (4.0+): it cuts storage but forbids LWT, logged batches, counters, and monotonic reads — avoid in prod.

## Conflict resolution: last-write-wins on timestamps
Every column mutation carries a timestamp; the highest wins (LWW). Clock skew silently drops writes or resurrects data — DO run NTP on every node. A `DELETE` writes a **tombstone**; DO run `nodetool repair` on **every** table within `gc_grace_seconds` (default **864000 = 10 days**), or a node that missed the delete "resurrects" the row after tombstones are compacted away.

## Anti-entropy: hints, read-repair, repair
Three converging mechanisms: **hinted handoff** (coordinator stores + replays a hint for a down replica, bounded by `max_hint_window`), **read repair** (fixes replicas hit during a read), and **anti-entropy repair** (`nodetool repair`, Merkle-tree comparison). DO prefer **incremental** or **sub-range** repair on large tables; a full repair on a huge dataset streams hard. Repair is the *only* guarantee everything converges — schedule it, don't lean on hints/read-repair.

## LWT & batches — narrow tools, not SQL transactions
**LWT** (`IF NOT EXISTS`, `IF EXISTS`, `IF col=...`) gives single-partition linearizable compare-and-set via **Paxos**, paired with `SERIAL`/`LOCAL_SERIAL` read CL. It costs extra round-trips — DON'T use it on hot paths or as a general lock. **Batches are for atomicity, not speed**: `LOGGED` (default) guarantees all-or-nothing via a batchlog but is slow across partitions; a single-partition LOGGED batch is auto-downgraded to UNLOGGED. `UNLOGGED` multi-partition batches can apply **partially** on failure. Isolation exists **only within one partition**. DON'T batch across partitions to "save round-trips" — it overloads the coordinator; batch only same-partition rows.

## Sources
- cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html (consistency levels, R+W>RF, NetworkTopologyStrategy/SimpleStrategy, transient replication, hints/read-repair/repair, Merkle trees, LWW)
- cassandra.apache.org/doc/latest/cassandra/architecture/guarantees.html (eventual consistency, per-table/local scope, LWT linearizability, batch atomicity)
- cassandra.apache.org/doc/latest/cassandra/developing/cql/dml.html (LWT IF/Paxos cost, BATCH LOGGED/UNLOGGED/COUNTER, single-partition isolation)

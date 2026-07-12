# Cloud Firestore — core digest
Version: Managed serverless document DB (GCP/Firebase); no user version — capacity/pricing evolve. Native mode (realtime, offline, Security Rules) for clients; Datastore mode for backends. Strongly consistent; ACID txns (270s); multi-region replication.

DO model for access patterns: embed read-together data, reference past the 1 MiB cap; no server JOINs — denormalize.
DO spread writes: auto-IDs scatter; monotonic IDs/indexed fields hotspot.
DO ramp 500/50/5: start 500 ops/s, +50% every 5 min; a sequential indexed field caps a collection at 500 writes/s.
DO index every query: single-field auto; compound/range needs composites.
DO paginate with cursors (startAfter + limit), never offset (billed per skip).
DO enforce Security Rules; least-privilege access.

DON'T exceed operator caps: in/array-contains-any ≤30 values, not-in ≤10, OR ≤30 disjunctions; range/inequality ≤10 fields, orderBy leading them.
DON'T hammer one doc: ~1 sustained write/s before contention — shard counters.
DON'T ignore per-op billing: reads/writes/deletes + index-entries + storage + egress; min 1 read/query on 0 results.

Deep dive when writing non-trivial Firestore — read lore/firestore/{data-model-and-documents,queries-and-indexes,realtime-and-security,performance}.md

## Sources
firebase.google.com/docs/firestore · /query-data · /best-practices · /pricing

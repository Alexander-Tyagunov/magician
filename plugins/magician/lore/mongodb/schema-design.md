# MongoDB — Schema design

Data modeling (engine layer). Manual 8.3; 8.0 GA, span 6.0/7.0/8.0. Mongoose subdocs/`ref`/`populate()`: see lore/mongoose.

## Model for the query, not the entity

**Data accessed together is stored together.** No server-side JOINs — `$lookup` is an aggregation stage, not a cheap join. List access patterns FIRST, then shape docs so a screen is one/few single-collection reads.

DO
- Embed the "many" side when loaded with the parent, bounded, owned (1:1, 1:few) — one read, no join.
- Reference (store `_id`, resolve via 2nd query or `$lookup`) when child data is large, shared, unbounded, or queried alone.
- Denormalize read-hot fields you'd otherwise `$lookup` — **Extended Reference** — accepting fan-out updates on change.
- Exploit polymorphism: a collection needn't have uniform fields/types; group docs read together (**Single Collection**, indexed `type`) vs tiny ones.

DON'T
- Don't normalize by reflex — a 3NF collection graph makes every page N `$lookup`s.
- Don't split into a collection per type/tenant when docs are read together (Reduce Number of Collections).

## Single-document atomicity is the design lever

A write to a **single document is always atomic** (all fields, embedded subdocs) — *why* you embed: relationships in one doc need no transaction. Multi-doc ACID txns exist (replica sets 4.0, sharded 4.2) but MongoDB says they're "not a replacement for effective schema design".

DO
- Keep an atomic invariant inside ONE document (order + line items).
- Mutate in place with `$inc`/`$push`/`$pull`/`$addToSet` + array filters; `findOneAndUpdate` for read-modify-write.

DON'T
- Don't make a common op *need* a transaction. If unavoidable: 60s default cap (`transactionLifetimeLimitSeconds`); a txn now spans multiple oplog entries (16MB total-txn cap dropped in 4.2; each *entry* still ≤16MB BSON); callback API auto-retries `TransientTransactionError`.

## Hard limits shape the schema

- **16MB max BSON document**; **100 levels** max nesting.
- **Unbounded arrays = #1 anti-pattern**: they blow the 16MB cap, degrade multikey indexes, and rewrite the whole doc on each push. Cap embedded arrays; if unbounded, reference a child collection or apply **Group Data** (bucket; fixed-size buckets).
- **Bloated documents** (large fields read on each hot query) waste cache — apply **Subset**: embed the top-N, archive the rest.

## Enforce shape; version; design `_id`

DO
- Add `$jsonSchema` validators (`bsonType`/`required`/`properties`/`enum`) via `validator` on `createCollection`/`collMod`; `title`/`description` surface in the descriptive error. Tune `validationLevel` (`strict`|`moderate`) + `validationAction` (`error`|`warn`).
- Stamp a `schemaVersion` field (**Document and Schema Versioning**) — migrate lazily on read, no big-bang.
- Precompute rollups at write (Handle Computed Values); archive cold data.
- Design `_id` deliberately (always-indexed PK): natural key or ObjectId; clustered collections key storage on `_id` for range scans.

DON'T
- Don't skip validation on a shared/prod collection — flexible schema silently accepts typos + wrong types.

Shard-key + index sizing/measurement: lore/mongodb/performance.md, lore/databases/indexing-and-query-plans.md.

## Sources
mongodb.com/docs/manual/ · data-modeling/{design-antipatterns,design-patterns} · core/{transactions,transactions-production-consideration,schema-validation}. Extended Reference & Subset: MongoDB *Building with Patterns* series.

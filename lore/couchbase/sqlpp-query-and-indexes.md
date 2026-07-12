# Couchbase — SQL++ query & indexes

Server 8.0 GA (Oct 2025; latest 8.0.2, Jun 2026); 7.x still common. SQL++ (formerly **N1QL**) is a JSON-native superset of SQL over documents, not rows. Verify gates against the target cluster.

## Address data by keyspace, not table
A keyspace is `` `bucket`.`scope`.`collection` `` (default `_default`); ≤1000 scopes+collections/cluster. The doc key is `meta().id`.
- **Reach known docs by key, never by scan.** `SELECT … FROM hotel USE KEYS ["h1","h2"]` bypasses indexes (sub-ms); reserve SQL++ predicates for *unknown*-key lookups. For one field, KV subdoc beats a query.
- Nested JSON is first-class: dotted paths (`geo.lat`), collection predicates (`ANY`/`EVERY`/`ARRAY … FOR`), object construction in projections.

## Every predicate needs a GSI — index the query
Global Secondary Indexes are async/eventually consistent, on a separate Index service. `CREATE INDEX idx ON hotel(state, city) USING GSI`.
- **The leading key must appear in `WHERE`** or the index isn't selected. Composite `(a,b)` serves predicates anchored on `a`; not `WHERE b = …` alone.
- `MISSING` values aren't indexed — covering/partial indexes qualify only when the query excludes them (`WHERE a IS NOT MISSING`, or a leading-key predicate implying it).
- Batch DDL: create many `WITH {"defer_build":true}`, then one `BUILD INDEX` — a single scan, not one per index.
- Scale/HA: `PARTITION BY HASH(a)` (`num_partition` default 8) spreads a big index across nodes; `num_replica` adds redundancy + scan parallelism. Keep partition keys immutable.
- **Never rely on the primary index in prod.** `CREATE PRIMARY INDEX` allows ad-hoc unindexed queries but every scan walks the whole keyspace (`PrimaryScan`, never covered). Drop it once real indexes exist.

## Covering indexes — the biggest read win
When the index holds every field a query touches, the engine skips the KV fetch — `EXPLAIN` shows an `IndexScan3` with a `covers` array (no `covers` ⇒ a fetch). `covers` always includes `meta().id`, so index keys **plus** `meta().id` must account for every referenced field. You **cannot** stitch coverage across two indexes — build one composite index.

## Arrays, UNNEST & JOINs
Index array elements: `CREATE INDEX ix ON route(DISTINCT ARRAY s.utc FOR s IN schedule END)`, then filter via `UNNEST route.schedule AS s`. Adaptive indexes cover arbitrary fields — handy for sparse ad-hoc filters but larger/slower. JOINs exist (`USE KEYS` lookup, ANSI `JOIN … ON`) but the right side **must** be indexed (or an EE `USE HASH` hint); no cheap cross-node joins — denormalize/embed read-together data instead.

## Query↔index consistency (`scan_consistency`)
- `not_bounded` (**default**): fastest; reads whatever the GSI has indexed — may lag writes.
- `request_plus`: strong per request; waits for the index to reach the current mutation vector ⇒ read-your-own-writes.
- `at_plus`: RYOW for *specific* mutations via a `scan_vector` — cheaper than `request_plus`.
- `statement_plus`: strong per statement. Pick the weakest level tolerable; strong levels wait on index catch-up.

## Pagination, parameters, plans
- `OFFSET` scans then discards skipped rows — **keyset-paginate** on an indexed key (`WHERE id>$last ORDER BY id LIMIT n`).
- Parameterize: named `$name` / positional `$1`/`?` (via `args`); mask secrets with `$_secret_` (7.6.8+). Never string-concat user input.
- `PREPARE`/`EXECUTE` caches the plan; pair with parameters so hot queries skip re-planning.

## Sources
docs.couchbase.com/server/current/n1ql/n1ql-language-reference/{index,covering-indexes}.html · docs.couchbase.com/server/current/settings/query-settings.html · docs.couchbase.com/server/current/learn/services-and-indexes/indexes/global-secondary-indexes.html

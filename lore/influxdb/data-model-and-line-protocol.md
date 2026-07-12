# InfluxDB — Data Model & Line Protocol

Version-adaptive. Same shape everywhere (timestamped tags + fields); container names and cardinality rules differ.

## Containers (know your version)
- **v1**: `database` → `retention policy` → `measurement`; 3-part name `"db"."rp"."measurement"`.
- **v2**: `bucket` (db + retention fused) → `measurement`; org-scoped.
- **v3** (Core/Enterprise): `database` → `table`; a `table` = v1/v2 `measurement`.

Everywhere: a **point** = measurement/table + tags + fields + timestamp; a **series** = unique measurement + tag set. v1/v2 index the **series key**; v3's **primary key** = timestamp + tag set (nulls excluded) and sets Parquet sort order.

## Line protocol (syntax identical v1→v3)
```
measurement,tag1=v1,tag2=v2 field1="s",field2=10i,field3=3.2 1556813561098000000
```
DO respect whitespace: first unescaped space ends tags, second ends fields; `\n` separates points.
DO type fields by marker/quoting (per-field, fixed after first write): float `10`/`-1.2e3` (default), integer `10i`, uinteger `10u`, string `"..."`, bool `t/true/f/false` (never quoted).
DO escape `,`/` `/`=` in measurement, tag keys/values, field keys; escape `"`/`\` in string values.
DON'T write empty tag values — omit the tag instead.
DON'T use `time` as a tag/field key, or `_field`/`_measurement` as keys — points are rejected/dropped.

DUPLICATE points (same measurement/tag set/timestamp) MERGE: field set unions, newest wins (silent overwrite).

## Timestamps
Default precision **ns**; if you send s/ms/us, declare it at write or points land at the wrong epoch. Omitted timestamp = server UTC now (bad for backfills).

## Tags vs fields
- **Tags**: string-only metadata you filter/group by. Indexed in v1/v2; dictionary-encoded column in v3.
- **Fields**: measured values (numeric/bool/string), NOT indexed in v1/v2 (filtering a field scans every value).
DO keep only what you query by in tags; quantities go in fields.
DON'T encode data in measurement/table or key names (Graphite-style `cpu.host1.usage`) — forces regex, blocks aggregation. One tag per attribute.

## Cardinality — the biggest cross-version difference
- **v1/v2 (TSM)**: tag cardinality is THE killer. Unbounded tag values (user/request IDs, UUIDs, hashes, timestamps-as-tags) explode the in-memory series index → OOM. NEVER tag with high-cardinality values. Measure via `SHOW SERIES CARDINALITY` (InfluxQL) or `influxdb.cardinality()` (Flux).
- **v3 (columnar Parquet)**: engine "supports infinite tag value and series cardinality" — cardinality no longer hurts performance. High-cardinality IDs CAN be tags; cost shifts to schema shape: more tags = larger primary key = slower sorting.

## v3 schema-on-write gotchas
Still schema-on-write, but tag columns are immutable and column order fixes on first write (later tags append last). DO order tags by query priority on the first write (most-filtered first, e.g. `region` before `host`). Keep tables homogenous; avoid wide schemas, sparse/null-heavy rows, tag/field name collisions.

Query languages → lore/influxdb/queries-influxql-flux-sql.md; batching/compaction/retention → lore/influxdb/performance.md; universal rules → lore/databases.md.

## Sources
docs.influxdata.com: influxdb3/core reference/line-protocol + write-data/best-practices/schema-design · influxdb/v2 reference/key-concepts/data-elements

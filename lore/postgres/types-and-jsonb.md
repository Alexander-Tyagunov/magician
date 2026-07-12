# PostgreSQL — Types & JSONB

Spans supported majors 14–18 (18 stable; 13 EOL 2025-11). Feature gates noted inline.

## Scalar type choices
- `numeric`/`decimal` is exact; `real`/`double precision` are inexact IEEE floats (`0.1::real+0.2::real` ≠ `0.3`). Use `numeric` for money — never `float` or the locale-dependent `money`.
- `timestamptz` stores no zone: input converts to UTC, renders back in the session `TimeZone`. `timestamp` is zoneless wall-clock. Prefer `timestamptz` and set `TimeZone` explicitly.
- `text`, `varchar`, `varchar(n)` share identical storage; `char(n)` is blank-padded and slower — avoid. Length caps are check constraints, no perf win.
- Prefer `GENERATED ALWAYS AS IDENTITY` over `serial`; key on `bigint` or `uuidv7()` (18). `gen_random_uuid()` is built in (no `pgcrypto`). Arrays are 1-based (`= ANY(arr)`; GIN `array_ops` for `@>`/`&&`). Enum order follows declaration; `ALTER TYPE ... ADD VALUE` can't be used later in the same transaction that added it, and labels can't be reordered/removed.

## json vs jsonb
`json` keeps exact text (whitespace, key order, duplicate keys), is re-parsed per access, and can't be indexed. `jsonb` is decomposed binary: duplicate keys collapse (last wins), order/whitespace lost, numbers normalize to `numeric` (big integers round-trip exactly in-engine, though a JS driver parsing to `double` may lose precision). Default to `jsonb`; pick `json` only for byte-exact reproduction.

## Operators & path
- Extract `->` (jsonb), `->>` (text), `#>`/`#>>` (path) return SQL NULL on a missing path, never error.
- `@>` containment is nested and order-insensitive; `?`/`?|`/`?&` existence is **top-level only**, matching keys/array-elements, never values.
- jsonpath (12+): `@?` (any match), `@@` (predicate) suppress structural/type errors. `lax` (default) auto-wraps/unwraps arrays and swallows structural errors; `strict` raises them — reserve `.**` for strict (it double-selects in lax).
- SQL/JSON constructors + `IS JSON` arrived in 16; `JSON_TABLE`/`JSON_QUERY`/`JSON_VALUE`/`JSON_EXISTS` in 17 — don't reference on ≤15.

## Indexing jsonb
- GIN `jsonb_ops` (default) indexes every key and value; supports `@>`,`@?`,`@@`,`?`,`?|`,`?&`. Larger.
- GIN `jsonb_path_ops` indexes value-paths only; supports just `@>`,`@?`,`@@` (no key-existence), smaller/faster, but emits nothing for valueless structures like `{"a":{}}`.
- `WHERE data->>'k'='v'` uses neither — add a btree **expression index** on `(data->>'k')`, or an expression GIN on a subdocument (`(data->'tags')`).
- GIN serves no ordering or `<`/`>` ranges. `fastupdate` defers inserts to a pending list (flushed by vacuum / `gin_pending_list_limit` / `gin_clean_pending_list()`): fast writes, but searches also scan the list and an oversized one forces a slow foreground cleanup — disable it when latency must be steady.

## Mutation & subscripting
- Subscripting (14+) is 0-based (`data['a']['b']`), auto-creates/pads nested containers, no slices. `jsonb_set(target,path,val,create_if_missing)` edits by path; `jsonb_set_lax` (13+) handles a SQL-NULL value via `null_value_treatment` (`use_json_null` default, or `raise_exception`/`delete_key`/`return_target`). Plain `jsonb_set` with any SQL-NULL argument returns NULL for the whole row — a silent data-wipe.
- MVCC: editing one key rewrites the whole document as a new row version and re-inserts all its GIN entries; large `jsonb` is TOAST-compressed and read/written whole. Keep hot-updated or heavily-filtered fields as real columns, not buried in a blob.

## Driver gotchas
- `?`/`?|`/`?&` collide with `?` bind placeholders. In pgJDBC escape as `??`; else avoid the family with `jsonb_path_exists(col,'$.key')` (no `?` char).
- Bind `jsonb` params with an explicit `::jsonb` cast (or the driver's json type); as `unknown`/text, inference can fail or store as `text`.
- SQL NULL, JSON `null`, and an absent key differ: `->>'missing'` is SQL NULL; `->'k'` of a JSON null is `'null'::jsonb`. A NUL char is illegal inside `jsonb` strings even when escaped.

## Sources
- https://www.postgresql.org/docs/current/datatype-json.html
- https://www.postgresql.org/docs/current/functions-json.html
- https://www.postgresql.org/docs/current/datatype.html
- https://www.postgresql.org/docs/current/gin.html
- https://jdbc.postgresql.org/documentation/query/

# Microsoft SQL Server — T-SQL & types

Spans 2017 (14.x) → 2022 (16.x); current stable 2025 (17.x). Azure SQL DB/MI track "always up-to-date" and often gain features first. Gates noted inline.

## Strings, Unicode & UTF-8
- `nvarchar`/`nchar` store UTF-16 (`n` = byte-*pairs*, ≤4000); `varchar`/`char` store one code page (`n` = *bytes*, ≤8000) — `n` never counts characters. Prefix every Unicode literal `N'…'`: a bare `'…'` is parsed in the code page and silently drops non-representable chars before it reaches the column.
- UTF-8 collations (`…_UTF8`, 2019/15.x; char/varchar only) let `varchar` hold full Unicode: ASCII costs 1 byte (~50% smaller than nvarchar for mostly-ASCII), but CJK costs 3 bytes vs 2 in UTF-16 — choose by data. `_SC` supplementary support is built into 140-version collations; without an SC/UTF8-aware collation, `LEN`/`SUBSTRING`/`LEFT` split surrogate pairs and miscount.
- Comparing/joining columns of different collations raises "cannot resolve the collation conflict"; forcing `COLLATE` fixes it but makes the predicate non-sargable. Keep join-key collations identical.
- `char(n)` is blank-padded. `text`/`ntext`/`image` are deprecated — use the `(max)` types.

## Numbers, money & dates
- `decimal(p,s)`/`numeric` are exact — use for money. `float`/`real` are approximate IEEE — never `=`-compare. `money` is fixed 4-dp and rounds intermediate division badly (`$100/3*3` ≠ `$100`); prefer `decimal(19,4)`.
- `datetime` (1753–9999, accuracy 1/300 s) rounds stored values to .000/.003/.007 s — a silent mutation. `datetime2(n)` (default 7, 0001–9999, 6–8 bytes, 100 ns) is strictly better; make it the default. Neither stores a zone. `datetimeoffset` keeps a *fixed* offset only — no named tz, no DST — and the engine never auto-converts by session tz. Store UTC; convert with `AT TIME ZONE`.

## NULL, precedence & implicit conversion
- Three-valued logic: `col = NULL` is never true — use `IS NULL`. `SET ANSI_NULLS OFF` is deprecated. Unlike Oracle, `''` is an empty string, **not** NULL. `+` propagates NULL; `CONCAT` treats NULL as `''`. 2022 (16.x) adds null-safe `IS [NOT] DISTINCT FROM`.
- Type precedence drives silent conversion: `nvarchar` outranks `varchar`; numerics outrank strings. So `WHERE varchar_col = @nvarchar_param` converts the **column** up to nvarchar, defeating its index (scan) — a common footgun since many drivers bind strings as Unicode by default. Match parameter types to columns; don't pass dates/numbers as strings (forces per-row CONVERT).
- On overflow, 2019+ (and 2017 CU12) report the offending table/column/value (error 2628) instead of the vague 8152 truncation error.

## SET options poison the plan cache
`QUOTED_IDENTIFIER`, `ANSI_NULLS`, `ANSI_WARNINGS`, `ARITHABORT`, `CONCAT_NULL_YIELDS_NULL` are baked into each cached plan and gate the usability of indexed views, computed columns, and filtered indexes. An app whose connection defaults differ from SSMS gets a *separate* plan (the classic "fast in SSMS, slow from the app") and can error on those objects. Set them explicitly and identically in the driver/DSN.

## Version-gated T-SQL surface
- 2017 (14.x): `STRING_AGG` (+`WITHIN GROUP`), `TRIM`, `CONCAT_WS`, `TRANSLATE`, `APPROX_COUNT_DISTINCT`.
- 2022 (16.x): `GREATEST`/`LEAST`, `DATE_BUCKET`, `GENERATE_SERIES`, `STRING_SPLIT` ordinal column, `JSON_OBJECT`/`JSON_ARRAY`, bit-manipulation functions, `WINDOW` clause.
- JSON: functions (`ISJSON`, `JSON_VALUE`, `JSON_QUERY`, `JSON_MODIFY`, `OPENJSON`) exist since 2016 over `nvarchar`. A native binary `json` type (in-place `.modify()`, stored `Latin1_General_100_BIN2_UTF8`, accepts only a top-level object/array) is GA on Azure SQL DB/MI, preview on 2025 (17.x); it can't be an index key — index a computed/`OPENJSON`-derived column.
- 2025 (17.x): regex functions (`REGEXP_LIKE`/`_REPLACE`/`_SUBSTR`…) and the `vector` type.

## Sources
learn.microsoft.com/sql — t-sql/data-types: data-types-transact-sql, data-type-precedence-transact-sql, datetime2-transact-sql, json-data-type · relational-databases/collations/collation-and-unicode-support (UTF-8/_SC) · t-sql/functions: string-agg-transact-sql, logical-functions-greatest-transact-sql (2017/2022 gates)

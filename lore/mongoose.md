# Mongoose (core)

JS/Node ODM for MongoDB — a JS/Node ORM, distinct from the JVM `orm` lore. Assumes js/ts/node lore exists separately.

Version cue: 9.x latest (2026); 8.x/7.x common. `strictQuery` defaults **false** since v7 (unknown filter paths pass through, not stripped). v8: `count()`→`countDocuments()`, `findOneAndRemove()`→`findOneAndDelete()`, `ObjectId` rejects 12-char strings.

DON'T feed untrusted `req.body`/`req.query` objects straight into filters — `{$ne:null}`,`{$gt:''}`,`{$regex}` = operator injection (auth bypass). DO `mongoose.set('sanitizeFilter', true)` (or wrap `mongoose.sanitizeFilter(obj)`); it wraps `$`-key subobjects in `$eq`. Whitelist real selectors via `mongoose.trusted({$gte:x})`.
DO cast scalars first: `String(x)`, `new mongoose.Types.ObjectId(x)` in try/catch.
DON'T use `$where`/`Model.$where` with user input — runs arbitrary JS server-side. Avoid entirely.
DON'T trust `aggregate()` — Mongoose does NOT cast pipeline `$match`; coerce types yourself.
DON'T `.then()`/`await` a query twice → "Query was already executed". Build via chaining, run once with `.exec()`.
DO `lean()` for read-only reads (plain objects, perf win); `select()` to avoid over-fetching.
Schema: `strict:true` (default) drops unknown fields on save; `timestamps:true`; `autoIndex:false` in production.

Commands: `npm i mongoose` (no official CLI).

Deep dive when writing non-trivial mongoose — read lore/mongoose/{schemas-and-models,queries-and-pitfalls}.md

## Sources
mongoosejs.com/docs/{guide,queries,api/mongoose,migrating_to_8}.html; npm mongoose (2026-07)

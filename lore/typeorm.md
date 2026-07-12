# TypeORM — core (JS/Node ORM; NOT the JVM `orm` lore)

Version: 1.0 is latest (upgrade guide from 0.3). 0.3+ uses `new DataSource(opts).initialize()`; `createConnection`/`getConnection` are deprecated 0.2-era. Needs TypeScript 4.5+, `experimentalDecorators`+`emitDecoratorMetadata`, and `import "reflect-metadata"` once at bootstrap.

DO parameterize every dynamic value:
- QueryBuilder: `.where("u.name = :name", { name })`; lists `.where("u.id IN (:...ids)", { ids })`.
- Raw: `repo.query("SELECT * FROM u WHERE name = $1", [name])` (pg `$1`, mysql/sqlite `?`, named `:name`).
DON'T interpolate user input into any SQL/where string — `.where(`name='${x}'`)` and `repo.query(`...${x}`)` are injectable. Same for `Brackets`, `orderBy`, and raw fragments.
DON'T ship `synchronize: true` — data loss on schema drift; use migrations. Never run `schema:sync`/`schema:drop` in prod.
DO scope via `dataSource.getRepository(E)`/`manager`; wrap write batches in `dataSource.transaction()`.

Commands: `typeorm migration:generate -d <datasource> <Name>` · `migration:run -d <ds>` · `migration:revert -d <ds>` · `schema:sync` (dev only).

Deep dive when writing non-trivial typeorm — read lore/typeorm/{entities-and-repositories,migrations-and-pitfalls}.md

## Sources
typeorm.io/docs/getting-started · /data-source · /query-builder/select-query-builder · /working-with-entity-manager/repository-api · /migrations/generating

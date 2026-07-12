# Prisma (lore — core)

JS/Node ORM, TS-first. Not the JVM `orm` lore.

Version: Prisma 6.x (Node ≥18.18, TS ≥5.1). v5→6: `Bytes` is `Uint8Array` not `Buffer`; `NotFoundError` removed → catch `PrismaClientKnownRequestError` code `P2025`. New `prisma-client` generator (ESM, `output` required) supersedes `prisma-client-js`.

DO
- Prefer model methods (findMany/create/update) — parameterized by default.
- Raw only via tagged `` $queryRaw`... WHERE id=${id}` `` or compose with `Prisma.sql`.
- `select`/`include` to avoid over-fetch; paginate (`take`/`cursor`).
- One PrismaClient per process (singleton); `$disconnect()` on shutdown.
- `migrate dev` locally, `migrate deploy` in CI/prod. Multi-write invariants → `$transaction`.

DON'T
- ❌ NEVER interpolate user input into `$queryRawUnsafe`/`$executeRawUnsafe` or `Prisma.raw` — SQL injection. Pass values as `$1,$2` params, or use tagged `$queryRaw`.
- ❌ Don't build raw strings by concatenation even for `$queryRaw` — only real template literals are escaped.
- ❌ Don't `db push` prod (no migration history); don't `migrate reset` prod (drops data).
- ❌ Don't `new PrismaClient()` per request (pool leak).

Commands: prisma init · generate · migrate dev --name x · migrate deploy · db push · db pull · studio · migrate reset

Deep dive when writing non-trivial prisma — read lore/prisma/{schema-and-migrations,client-queries-and-pitfalls}.md

Sources: prisma.io/docs/orm/prisma-client/using-raw-sql/raw-queries · /reference/prisma-cli-reference · /more/upgrade-guides/upgrading-versions/upgrading-to-prisma-6

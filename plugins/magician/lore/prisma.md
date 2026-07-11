Common AI mistakes: forgetting `await` on Prisma calls; not running `prisma generate` after schema changes; using `findUnique` with non-unique fields; forgetting to handle null returns.
Commands: generate: `npx prisma generate`, migrate: `npx prisma migrate dev`, studio: `npx prisma studio`.
Gotchas: Prisma Client must be re-generated after any schema.prisma change; relations use `include` not `join`; `upsert` requires both `create` and `update`.

# NestJS — core

Version cue: NestJS 11 defaults to Express 5 (named wildcards `/*splat`; `simple` query parser) + Fastify 5, Node >=20, `cache-manager`->Keyv (`stores:[...]`). NestJS 10 = Express 4. Check `@nestjs/core`.

DO set a global `ValidationPipe({whitelist:true,forbidNonWhitelisted:true,transform:true})` + class-validator DTOs — blocks unknown props (mass-assignment defense).
DO `app.use(helmet())`; configure `app.enableCors()` deliberately — allow-list origins, never `origin:'*'` with `credentials:true`.
DO register custom providers via `useClass`/`useValue`/`useFactory`/`useExisting`; inject non-class tokens with `@Inject('TOKEN')`.
DO map errors via exception filters; throw `HttpException`; keep secrets in `ConfigModule`.
DO test with `Test.createTestingModule().overrideProvider(X).useValue(mock).compile()`; resolve scoped via `await moduleRef.resolve(X)`.

DON'T leak stack traces or entities — return DTOs, `@Exclude()` secrets; set `NODE_ENV=production`.
DON'T inject REQUEST-scoped providers into singletons (bubbles scope up, hurts perf).
DON'T use unnamed wildcards/`forRoutes('*')` on Nest 11 — use `*splat`.
DON'T trust `@Body/@Query/@Param` unvalidated; parameterize all DB access.

Commands: `nest new` · `nest g resource` · `npm i helmet class-validator class-transformer` · `npm test`

Deep dive when writing non-trivial nestjs — read lore/nestjs/{modules-and-di,request-pipeline,testing}.md

## Sources
docs.nestjs.com/migration-guide · /fundamentals/custom-providers · /techniques/validation · /security/helmet · /fundamentals/unit-testing

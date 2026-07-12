# nestjs — Testing

Framework-specifics only. Assume JS/TS/Node and generic Jest lore live elsewhere.
Verify the major: `npm ls @nestjs/core` → **Nest 11** (current, Node 20+, defaults to
**Express 5**) vs **Nest 10** (Express 4). The `@nestjs/testing` API is stable across
10→11; what bites tests is Express-5 route matching and `supertest` import style.

Two tiers: **unit** (`.spec.ts`, one class + mocked deps, no HTTP) and **e2e**
(`.e2e-spec.ts`, real Nest app + HTTP via `supertest`/Fastify `inject`).

## Test module — DO

- Build every test off `Test.createTestingModule({...}).compile()`. `compile()` is async;
  `await` it. It bootstraps DI but creates **no HTTP adapter/server**.
  ```ts
  import { Test, TestingModule } from '@nestjs/testing';

  const moduleRef: TestingModule = await Test.createTestingModule({
    controllers: [CatsController],
    providers: [CatsService],
  }).compile();

  const controller = moduleRef.get(CatsController);
  ```
- Use `get(token)` for **singleton** (default-scope) providers. Use
  `await resolve(token)` for **REQUEST/TRANSIENT**-scoped providers — `get()` throws for
  those. `resolve()` returns a **fresh instance per call** unless you pin a `contextId`.
- Keep each provider a real class instance and stub methods with `jest.spyOn(svc, 'm')`
  when you only need to intercept one method (see unit example below).
- Import `TestingModule`/`TestingModuleBuilder` types from `@nestjs/testing`, not `@nestjs/common`.

## Test module — DON'T

- DON'T forget `await` on `compile()` / `resolve()` / `app.init()` — silent undefined DI.
- DON'T call `get()` on a request-scoped provider — it throws. Use `resolve()`.
- DON'T read `HttpAdapterHost#httpAdapter` after only `compile()` — `undefined` until
  `createNestApplication()`.

## Overriding providers & enhancers — DO

- Swap real deps with the fluent override chain, then `compile()`. Each override
  (except module) exposes `useValue` / `useClass` / `useFactory`:
  ```ts
  const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
    .overrideProvider(MailService).useValue({ send: jest.fn() })
    .overrideGuard(JwtAuthGuard).useValue({ canActivate: () => true })
    .overrideInterceptor(LoggingInterceptor).useClass(NoopInterceptor)
    .overridePipe(ValidationPipe).useValue({ transform: (v) => v })
    .overrideFilter(AllExceptionsFilter).useValue({ catch: jest.fn() })
    .compile();
  ```
- `overrideModule(RealModule).useModule(FakeModule)` replaces an **entire** module — the
  only override that takes `useModule` (no value/class/factory form).
- To override a **globally** registered enhancer (`APP_GUARD`/`APP_PIPE`/`APP_INTERCEPTOR`/
  `APP_FILTER`), register it with **`useExisting`** pointing at a listed provider, so it
  becomes overridable by token:
  ```ts
  providers: [
    { provide: APP_GUARD, useExisting: JwtAuthGuard }, // NOT useClass
    JwtAuthGuard,
  ]
  // test:
  .overrideProvider(JwtAuthGuard).useClass(MockAuthGuard)
  ```

## Overriding — DON'T

- DON'T expect `.overrideGuard(X)` to hit a global guard registered via
  `{ provide: APP_GUARD, useClass: X }` — that binding is anonymous; switch it to
  `useExisting` first (above), or the override is a no-op.
- DON'T override with a class that has unmet deps not present in the test module — DI fails
  at `compile()`.

## Mocking dependencies — DO

- **Explicit value mock** (clearest, preferred): `.overrideProvider(CatsService)
  .useValue({ findAll: jest.fn() })` — supply only the methods the unit calls.
- **Auto-mock the rest** with `.useMocker(token => ...)` for large graphs — return a mock
  for known tokens, and generate one for the rest via `jest-mock`'s `ModuleMocker`:
  ```ts
  import { ModuleMocker, MockMetadata } from 'jest-mock';
  const moduleMocker = new ModuleMocker(global);

  .useMocker((token) => {
    if (token === CatsService) return { findAll: jest.fn().mockResolvedValue(['x']) };
    if (typeof token === 'function') {
      const meta = moduleMocker.getMetadata(token) as MockMetadata<any, any>;
      const Mock = moduleMocker.generateFromMetadata(meta) as ObjectConstructor;
      return new Mock();
    }
  })
  ```
- For non-class **injection tokens** (`@Inject('CONFIG')`), override by the same string/
  symbol token: `.overrideProvider('CONFIG').useValue({...})`.

## Mocking — DON'T

- DON'T hand-roll deep partials when a method is untouched — `jest.fn()` per used method +
  `useValue` beats a fragile full stub.
- DON'T leak spies across tests — `jest.restoreAllMocks()` in `afterEach` (or
  `restoreMocks: true` in Jest config).

## Unit spec — DO

- One class under test per spec; mock its collaborators; no HTTP, no `createNestApplication`.
  Build in `beforeEach`, resolve with `get()`, stub with `jest.spyOn`:
  ```ts
  const moduleRef = await Test.createTestingModule({
    controllers: [CatsController], providers: [CatsService],
  }).compile();
  const service = moduleRef.get(CatsService);
  const controller = moduleRef.get(CatsController);
  jest.spyOn(service, 'findAll').mockResolvedValue(['test']);
  expect(await controller.findAll()).toEqual(['test']);
  ```

## e2e spec (supertest / Express) — DO

```ts
import request from 'supertest';           // Jest+ts-jest also accepts: import * as request
import { INestApplication } from '@nestjs/common';

describe('Cats (e2e)', () => {
  let app: INestApplication;
  const cats = { findAll: () => ['test'] };

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(CatsService).useValue(cats)
      .compile();
    app = moduleRef.createNestApplication();
    // Mirror prod global setup you rely on — pipes/filters aren't auto-applied here:
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
    await app.init();                       // MUST init before requests
  });

  it('/GET cats', () =>
    request(app.getHttpServer()).get('/cats').expect(200).expect({ data: cats.findAll() }));

  afterAll(async () => { await app.close(); });   // release handles
});
```
- `createNestApplication()` builds the **full runtime + HTTP adapter**; pass
  `request(app.getHttpServer())` to `supertest`.
- **supertest import**: `import * as request from 'supertest'` under Jest/ts-jest; switch to
  default `import request from 'supertest'` when running **Vitest/Vite** — Vitest expects
  the default export. (`supertest` v7 is current.)

## e2e (Fastify) — DO

- Fastify has no live socket in tests; use light-my-request via `app.inject()`, not supertest:
  ```ts
  const app = moduleRef.createNestApplication<NestFastifyApplication>(new FastifyAdapter());
  await app.init();
  await app.getHttpAdapter().getInstance().ready();   // wait for plugins
  const res = await app.inject({ method: 'GET', url: '/cats' });
  expect(res.statusCode).toBe(200);
  ```

## e2e — DON'T

- DON'T skip `app.close()` — open servers/DB pools keep Jest alive (`--detectOpenHandles`).
- DON'T assume `main.ts` global pipes/filters/prefix/versioning apply — the test app only
  has what the module declares; re-apply global config in `beforeAll`.
- DON'T write wildcard routes as `*` on **Nest 11 / Express 5** — path-to-regexp changed;
  use named wildcards e.g. `forRoutes('{*splat}')`. Old `*` patterns silently mis-match.
- DON'T share one `app` across parallel test files with shared state — Jest files run in
  separate workers; e2e suites that touch a real store must isolate data.

## Request-scoped providers — DO

- Pin the DI sub-tree so you can inspect the same instance the request uses:
  ```ts
  const contextId = ContextIdFactory.create();
  jest.spyOn(ContextIdFactory, 'getByRequest').mockImplementation(() => contextId);
  const svc = await moduleRef.resolve(CatsService, contextId);
  ```

## Avoiding a real DB — DO

- **Prefer isolation**: unit-test services with the repository/data-mapper **mocked**
  (`.overrideProvider(getRepositoryToken(Cat)).useValue(mockRepo)`) — no DB at all. Defer
  ORM token specifics to the ORM lore (TypeORM/Prisma/Mongoose).
- When you need real SQL/engine behavior (migrations, constraints, raw queries), spin an
  ephemeral **Testcontainers** container (`@testcontainers/postgresql` etc.) in `beforeAll`,
  inject its URI, tear down in `afterAll`:
  ```ts
  const pg = await new PostgreSqlContainer('postgres:16').start();
  const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
    .overrideProvider(DB_URL).useValue(pg.getConnectionUri()).compile();
  // afterAll: await pg.stop();
  ```
- Raise Jest `testTimeout` for container startup; run e2e serially (`--runInBand`) if suites
  contend for ports.

## Avoiding a real DB — DON'T

- DON'T point tests at a shared/staging DB — flaky, order-dependent, and a data-leak risk.
- DON'T use SQLite as a stand-in for Postgres when you test DB-specific behavior (types,
  JSONB, upserts) — dialect gaps produce false greens. Use a real engine via Testcontainers.
- DON'T reuse one container across suites without truncating between tests — cross-test bleed.

## Security in tests — DO

- Assert `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` strips/rejects
  unknown fields — test the 400 path, not just the happy path.
- Test **both** allow and deny for auth guards (don't only override to always-allow); confirm
  unauthenticated/forbidden requests are rejected.
- Assert error responses **don't leak stack traces / internal messages**; verify `helmet`/
  CORS headers you rely on. Never bake real secrets into fixtures — use throwaway values.

## Spec layout & config — DO

- `*.spec.ts` beside source (unit); `*.e2e-spec.ts` under `/test` (e2e).
- CLI scaffold keeps e2e Jest config in `test/jest-e2e.json` (own `testRegex`/`rootDir`) run
  via `test:e2e`; unit config in `package.json` `jest`. Vitest: separate
  `vitest.config.e2e.ts` with `include: ['**/*.e2e-spec.ts']` (+ supertest default import).

## Sources

- https://docs.nestjs.com/fundamentals/testing
- https://docs.nestjs.com/fundamentals/custom-providers
- https://docs.nestjs.com/migration-guide
- https://docs.nestjs.com/recipes/swc
- https://docs.nestjs.com/techniques/database

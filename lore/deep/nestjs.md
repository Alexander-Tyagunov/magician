# nestjs — deep dive

> On-demand companion to `lore/nestjs.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Modules & dependency injection](#modules-and-di) · [Request pipeline](#request-pipeline) · [Testing](#testing)

## Modules & dependency injection <a id="modules-and-di"></a>

Scope: `@Module` graph, provider scopes, constructor DI + tokens, dynamic modules, circular deps, global modules. NestJS 11 (current) vs 10. Assume TS/Node lore exists separately.

### `@Module` metadata

Four keys: `providers` (instantiated by the injector, shared within the module), `controllers`, `imports` (modules whose *exports* you need), `exports` (subset of providers/imported-modules exposed to importers).

#### DO
- Keep modules feature-scoped and cohesive; wire cross-module use via `imports`/`exports`.
- Export only what consumers need. A provider is invisible to other modules unless `exports`ed.
- Re-export an imported module to pass it through: `exports: [TypeOrmModule]` (importer gets its providers without re-importing).
- `imports: [CommonModule]` — NestJS dedupes; the same module imported twice yields one shared instance.

#### DON'T
- Don't list a provider in `providers` of two sibling modules expecting one instance — you get two. Put it in one module, `export` it, `import` that module.
- Don't put controllers in `imports` or providers in `controllers`. Wrong slot = silent non-registration.
- Don't import a module for a provider it doesn't `export` — resolution fails at bootstrap.

### Providers & constructor DI

Default token is the class itself; Nest resolves by type via `reflect-metadata`.

```ts
@Injectable()
export class CatsService {
  constructor(private readonly repo: CatsRepository) {}
}
```

#### DO
- Prefer class tokens. Use `@Inject(TOKEN)` only for non-class tokens (strings/symbols) or interfaces.
- Define token constants (`export const CONNECTION = Symbol('CONNECTION')`) — avoid magic strings scattered across files.
- Mark optional deps: `@Optional() @Inject('X')`.
- Keep `emitDecoratorMetadata`/`experimentalDecorators` on in `tsconfig`; type-based DI needs it.

#### DON'T
- Don't inject by interface without a token — interfaces vanish at runtime; use `@Inject('IFoo')` + a string/symbol token.
- Don't do work in constructors (I/O, connections). Use lifecycle hooks (`onModuleInit`).

### Custom providers

```ts
// value
{ provide: 'CONNECTION', useValue: connection }
// class (swap impl by env)
{ provide: ConfigService, useClass: process.env.NODE_ENV === 'development'
    ? DevConfigService : ProdConfigService }
// factory with injected deps (optional token supported)
{ provide: 'CONNECTION',
  useFactory: (opts: OptionsProvider) => new DbConnection(opts.get()),
  inject: [OptionsProvider, { token: 'MAYBE', optional: true }] }
// alias -> same instance as an existing provider
{ provide: 'AliasedLogger', useExisting: LoggerService }
```

Async provider: `useFactory: async () => await createConnection(opts)` — bootstrap awaits it before the app is ready.

#### DO
- Use `useExisting` for aliases so both tokens resolve to one singleton.
- Order `inject` array positionally to match factory params.

#### DON'T
- Don't confuse `useClass` (new instance per token) with `useExisting` (shared instance).
- Don't block startup on slow async factories without a timeout/failure path.

### Scopes

`DEFAULT` (singleton, cached at startup — recommended), `REQUEST` (new instance per request), `TRANSIENT` (new instance per consumer).

```ts
@Injectable({ scope: Scope.REQUEST })
export class RequestService {}
```

Scope on custom providers: add `scope: Scope.TRANSIENT` to the provider object.

#### DO
- Default to singleton. Reach for `REQUEST` only when you truly need per-request state (e.g. request-bound context).
- Inject the request in request scope: `constructor(@Inject(REQUEST) private req: Request)` (`REQUEST` from `@nestjs/core`).
- For multi-tenant per-request pooling, use **durable providers** to avoid per-request instantiation cost: `@Injectable({ scope: Scope.REQUEST, durable: true })` + a `ContextIdStrategy` that groups by tenant.

#### DON'T
- Don't scatter `REQUEST` scope. It **bubbles up**: any controller/provider depending on a request-scoped provider becomes request-scoped too, killing singleton caching and adding per-request instantiation latency.
- Don't assume `TRANSIENT` bubbles — it doesn't; a singleton injecting a transient gets one fresh instance and stays singleton.
- Don't `moduleRef.get()` a scoped provider — use `await moduleRef.resolve(Svc, contextId)`; `resolve()` returns a distinct instance per call/sub-tree.

### Dynamic modules (`forRoot` / `forFeature` / `register`)

```ts
@Module({})
export class DatabaseModule {
  static forRoot(opts): DynamicModule {
    return { module: DatabaseModule, providers: [...], exports: [...] };
  }
}
```

Convention: `forRoot`/`forRootAsync` = global-ish one-time config; `forFeature` = per-feature scoping (e.g. `TypeOrmModule.forFeature([User])`); `register` = per-import config.

#### DO
- Prefer `ConfigurableModuleBuilder` for config modules — generates the class + `MODULE_OPTIONS_TOKEN` and `*Async` variants:
  ```ts
  export const { ConfigurableModuleClass, MODULE_OPTIONS_TOKEN } =
    new ConfigurableModuleBuilder<Opts>().setClassMethodName('forRoot').build();
  ```
- Return `global: true` inside the `DynamicModule` to register a configured module globally.

#### DON'T
- Don't hardcode config in `providers`; thread options through the static method + a token.

### Global modules

```ts
@Global()
@Module({ providers: [CatsService], exports: [CatsService] })
export class CatsModule {}
```

#### DO
- Register global modules **once**, in the root/core module. Exports become injectable app-wide without re-importing.

#### DON'T
- Don't overuse `@Global()` — it hides dependency edges and hurts testability/modularity. Reserve for truly cross-cutting infra (config, logger).

### Circular dependencies

#### DON'T
- Don't create circular provider/module refs. First fix: extract shared logic into a third module — restructuring beats `forwardRef`.

#### DO (only if unavoidable)
```ts
constructor(@Inject(forwardRef(() => CatsService)) private cats: CatsService) {}
```
- Module-to-module: `imports: [forwardRef(() => OtherModule)]` on *both* sides.

### Testing

```ts
const moduleRef = await Test.createTestingModule({
  controllers: [CatsController], providers: [CatsService],
}).overrideProvider(CatsService).useValue(mock).compile();

const ctrl = moduleRef.get(CatsController);          // singletons
const svc  = await moduleRef.resolve(RequestSvc);    // scoped: unique per call
```

#### DO
- `overrideProvider(...).useValue/useClass/useFactory(...)` to inject test doubles.
- Use `get()` for singletons, `resolve()` for request/transient.

### NestJS 11 vs 10 (DI-relevant)

- **Express 5** is the default HTTP adapter in v11 (Express 4 in v10). Path matching changed (`path-to-regexp` upgrade): wildcard `*` → named `{*splat}`; v11 auto-converts old Express-4 wildcards but don't rely on it. **Fastify 5** is v11's default Fastify major; Fastify middleware `(.*)` no longer works — use `*splat`.
- **Reflector** type inference improved in v11: `getAllAndOverride` returns `T | undefined`; `getAllAndMerge` returns an object for single object metadata. Adjust guard/interceptor metadata typing when upgrading.
- Overall v10→v11 is a light migration; the above are the main gotchas. Verify against the migration guide before upgrading.

### Security notes (DI surface)

- Never `useValue` secrets inline in module files committed to VCS — thread via config/env behind a token.
- Don't leak internals: keep infra providers unexported unless consumers need them.
- Validate config at the module boundary (e.g. `ConfigModule` schema validation) so bad env fails fast at bootstrap, not per request.

### Sources
- https://docs.nestjs.com/modules
- https://docs.nestjs.com/fundamentals/custom-providers
- https://docs.nestjs.com/fundamentals/dependency-injection
- https://docs.nestjs.com/fundamentals/injection-scopes
- https://docs.nestjs.com/fundamentals/dynamic-modules
- https://docs.nestjs.com/fundamentals/async-components
- https://docs.nestjs.com/fundamentals/circular-dependency
- https://docs.nestjs.com/fundamentals/module-ref
- https://docs.nestjs.com/fundamentals/testing
- https://docs.nestjs.com/migration-guide

## Request pipeline <a id="request-pipeline"></a>

Enhancer order per request (HTTP). Filters wrap the whole thing.

```
middleware → guards → interceptors (pre) → pipes → HANDLER
                    → interceptors (post) → response
         (any throw from guards→handler) → exception filters
```

- Guards run **after all middleware, but before any interceptor or pipe**.
- Interceptors **wrap** the handler: logic runs before *and* after via the returned `Observable`.
- Pipes run **last** before the handler, transforming/validating each argument.
- Exception filters catch throws from guards, pipes, interceptors, and the handler (the "exceptions zone"). Assume Node 20+ / NestJS 11 unless stated.

### Middleware — DO
- Use for framework-level concerns before routing: `helmet()`, `cors()`, `compression`, request logging, raw-body capture.
- Class middleware (`@Injectable()` + `NestMiddleware`) when you need DI; **functional** middleware when you don't.
- Configure in a module via `NestModule.configure(consumer)` — fluent `apply().forRoutes()` / `.exclude()`. `configure()` may be `async`.

```ts
export class AppModule implements NestModule {
  configure(c: MiddlewareConsumer) {
    c.apply(helmet(), LoggerMiddleware)
     .exclude({ path: 'health', method: RequestMethod.GET })
     .forRoutes({ path: 'cats/*splat', method: RequestMethod.ALL });
  }
}
```

### Middleware — DON'T
- DON'T put auth/authz here — use **guards** (they see `ExecutionContext` and the target handler; middleware doesn't).
- DON'T expect DI in `app.use(...)` global middleware — not possible; use functional or `.forRoutes('*')`.
- DON'T reuse Express 4 wildcards on Nest 11. Express 5 / `path-to-regexp` v8: `*` → `*splat`, optional `?` → `{...}`. Fastify 5 middleware: `(.*)` → `*splat`.
- DON'T rely on module order for globals — in Nest 11 middleware from **global modules runs first** regardless of graph position.

### Guards — DO (authz)
- `@Injectable()` implementing `CanActivate.canActivate(ctx)` → `boolean | Promise | Observable`. `true` proceeds, `false` → `ForbiddenException` (403 "Forbidden resource").
- Read route metadata with `Reflector`; drive RBAC off `request.user` (populated by an auth guard upstream).
- Bind: `@UseGuards(RolesGuard)` (method/controller) or globally with DI via `APP_GUARD`.

```ts
export const Roles = Reflector.createDecorator<string[]>();

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}
  canActivate(ctx: ExecutionContext) {
    const roles = this.reflector.get(Roles, ctx.getHandler());
    if (!roles) return true;
    const { user } = ctx.switchToHttp().getRequest();
    return roles.some((r) => user?.roles?.includes(r));
  }
}
// module: { provide: APP_GUARD, useClass: RolesGuard }
```

### Guards — DON'T
- DON'T use `app.useGlobalGuards(new G())` when the guard needs injected deps — use `APP_GUARD` (`useClass`) so DI works.
- DON'T do authn/z in interceptors or pipes — wrong layer, guards short-circuit earliest.
- DON'T trust a role claim without an authentication guard having set `request.user` first.

### Interceptors — DO (cross-cutting)
- `NestInterceptor.intercept(ctx, next)` returns `next.handle()` piped through RxJS: `map` (reshape response), `tap` (log/metrics on success or error), `catchError` (map errors), `timeout`.
- Use for: response envelopes, caching, logging/timing, `ClassSerializerInterceptor` (`@Exclude`/`@Expose`), serialization.
- Bind: `@UseInterceptors(X)` or global-with-DI via `APP_INTERCEPTOR`.

```ts
@Injectable()
export class TransformInterceptor implements NestInterceptor {
  intercept(_: ExecutionContext, next: CallHandler) {
    return next.handle().pipe(map((data) => ({ data })));
  }
}
```

### Interceptors — DON'T
- DON'T forget to return `next.handle()` — omit the call and **the handler never runs**.
- DON'T use `app.useGlobalInterceptors(...)` for DI-needing interceptors — use `APP_INTERCEPTOR`.
- DON'T bury business logic here.

### Pipes / ValidationPipe — DO (validate + sanitize)
- Validate ALL input with a **global** `ValidationPipe` + `class-validator`/`class-transformer` DTOs. DTO decorators are the single source of truth.
- Always set:
  - `whitelist: true` — strip properties without validation decorators.
  - `forbidNonWhitelisted: true` — 400 on unknown properties (surfaces attacks/typos).
  - `transform: true` — instantiate the DTO class (`plainToInstance` + `validate`) and coerce primitives (string `:id` → `number` when the signature says `number`).
- Parse scalars explicitly when not auto-transforming: `@Param('id', ParseIntPipe)`, `ParseUUIDPipe`, `ParseBoolPipe`, `ParseArrayPipe({ items: Dto })`, `DefaultValuePipe` before a `Parse*`.
- Production: `disableErrorMessages: true`. Extra safety: `forbidUnknownValues: true`. Partial updates: `PartialType`/`PickType`/`OmitType` from `@nestjs/mapped-types`.

```ts
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,
  forbidNonWhitelisted: true,
  transform: true,
}));

export class CreateUserDto {
  @IsEmail() email: string;
  @IsString() @MinLength(8) password: string;
}
```

### Pipes — DON'T
- DON'T accept raw `@Body()` without a decorated DTO — no decorators means `whitelist` strips everything.
- DON'T skip `forbidNonWhitelisted` — silent stripping hides malformed/malicious payloads.
- DON'T return validation error detail to clients in prod (`disableErrorMessages: true`).
- DON'T rely on `useGlobalPipes` for gateways/microservices in hybrid apps — it doesn't apply there.
- DON'T use `app.useGlobalPipes` when the pipe needs DI — use `APP_PIPE`.

### Exception filters — DO
- `@Catch(HttpException)` + `ExceptionFilter.catch(exception, host)`; get response via `host.switchToHttp().getResponse()`.
- Throw built-ins (`BadRequestException`, `UnauthorizedException`, `NotFoundException`, `ForbiddenException`, `InternalServerErrorException`) — all extend `HttpException`.
- Catch-all: extend `BaseExceptionFilter`, call `super.catch(...)` for unknowns. Declare the "catch anything" filter **first**.
- Global-with-DI via `APP_FILTER`. Prefer binding **classes** over instances.

### Exception filters — DON'T
- DON'T leak stack traces or internal messages — log server-side, return a sanitized shape.
- DON'T `new` a filter that extends `BaseExceptionFilter` at method/controller scope.
- DON'T swallow non-HTTP errors silently — map them to 500 via the catch-all.

### Version notes
- **NestJS 11** (Node 20+): Express **5** default (async errors auto-forwarded; `path-to-regexp` v8 wildcards; query parser is "simple" — `app.set('query parser','extended')` for nested). Fastify 5 supported (CORS only safelisted methods by default). `Reflector.getAllAndOverride` → `T | undefined`; `getAllAndMerge` returns an object for a single object entry.
- **NestJS 10**: Express **4** by default (Express 4 wildcard/regex route syntax).
- `class-validator`/`class-transformer` and `@nestjs/mapped-types` are separate installs.

### Sources
- https://docs.nestjs.com/middleware
- https://docs.nestjs.com/guards
- https://docs.nestjs.com/interceptors
- https://docs.nestjs.com/pipes
- https://docs.nestjs.com/exception-filters
- https://docs.nestjs.com/techniques/validation
- https://docs.nestjs.com/migration-guide

## Testing <a id="testing"></a>

Framework-specifics only. Assume JS/TS/Node and generic Jest lore live elsewhere.
Verify the major: `npm ls @nestjs/core` → **Nest 11** (current, Node 20+, defaults to
**Express 5**) vs **Nest 10** (Express 4). The `@nestjs/testing` API is stable across
10→11; what bites tests is Express-5 route matching and `supertest` import style.

Two tiers: **unit** (`.spec.ts`, one class + mocked deps, no HTTP) and **e2e**
(`.e2e-spec.ts`, real Nest app + HTTP via `supertest`/Fastify `inject`).

### Test module — DO

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

### Test module — DON'T

- DON'T forget `await` on `compile()` / `resolve()` / `app.init()` — silent undefined DI.
- DON'T call `get()` on a request-scoped provider — it throws. Use `resolve()`.
- DON'T read `HttpAdapterHost#httpAdapter` after only `compile()` — `undefined` until
  `createNestApplication()`.

### Overriding providers & enhancers — DO

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

### Overriding — DON'T

- DON'T expect `.overrideGuard(X)` to hit a global guard registered via
  `{ provide: APP_GUARD, useClass: X }` — that binding is anonymous; switch it to
  `useExisting` first (above), or the override is a no-op.
- DON'T override with a class that has unmet deps not present in the test module — DI fails
  at `compile()`.

### Mocking dependencies — DO

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

### Mocking — DON'T

- DON'T hand-roll deep partials when a method is untouched — `jest.fn()` per used method +
  `useValue` beats a fragile full stub.
- DON'T leak spies across tests — `jest.restoreAllMocks()` in `afterEach` (or
  `restoreMocks: true` in Jest config).

### Unit spec — DO

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

### e2e spec (supertest / Express) — DO

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

### e2e (Fastify) — DO

- Fastify has no live socket in tests; use light-my-request via `app.inject()`, not supertest:
  ```ts
  const app = moduleRef.createNestApplication<NestFastifyApplication>(new FastifyAdapter());
  await app.init();
  await app.getHttpAdapter().getInstance().ready();   // wait for plugins
  const res = await app.inject({ method: 'GET', url: '/cats' });
  expect(res.statusCode).toBe(200);
  ```

### e2e — DON'T

- DON'T skip `app.close()` — open servers/DB pools keep Jest alive (`--detectOpenHandles`).
- DON'T assume `main.ts` global pipes/filters/prefix/versioning apply — the test app only
  has what the module declares; re-apply global config in `beforeAll`.
- DON'T write wildcard routes as `*` on **Nest 11 / Express 5** — path-to-regexp changed;
  use named wildcards e.g. `forRoutes('{*splat}')`. Old `*` patterns silently mis-match.
- DON'T share one `app` across parallel test files with shared state — Jest files run in
  separate workers; e2e suites that touch a real store must isolate data.

### Request-scoped providers — DO

- Pin the DI sub-tree so you can inspect the same instance the request uses:
  ```ts
  const contextId = ContextIdFactory.create();
  jest.spyOn(ContextIdFactory, 'getByRequest').mockImplementation(() => contextId);
  const svc = await moduleRef.resolve(CatsService, contextId);
  ```

### Avoiding a real DB — DO

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

### Avoiding a real DB — DON'T

- DON'T point tests at a shared/staging DB — flaky, order-dependent, and a data-leak risk.
- DON'T use SQLite as a stand-in for Postgres when you test DB-specific behavior (types,
  JSONB, upserts) — dialect gaps produce false greens. Use a real engine via Testcontainers.
- DON'T reuse one container across suites without truncating between tests — cross-test bleed.

### Security in tests — DO

- Assert `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` strips/rejects
  unknown fields — test the 400 path, not just the happy path.
- Test **both** allow and deny for auth guards (don't only override to always-allow); confirm
  unauthenticated/forbidden requests are rejected.
- Assert error responses **don't leak stack traces / internal messages**; verify `helmet`/
  CORS headers you rely on. Never bake real secrets into fixtures — use throwaway values.

### Spec layout & config — DO

- `*.spec.ts` beside source (unit); `*.e2e-spec.ts` under `/test` (e2e).
- CLI scaffold keeps e2e Jest config in `test/jest-e2e.json` (own `testRegex`/`rootDir`) run
  via `test:e2e`; unit config in `package.json` `jest`. Vitest: separate
  `vitest.config.e2e.ts` with `include: ['**/*.e2e-spec.ts']` (+ supertest default import).

### Sources

- https://docs.nestjs.com/fundamentals/testing
- https://docs.nestjs.com/fundamentals/custom-providers
- https://docs.nestjs.com/migration-guide
- https://docs.nestjs.com/recipes/swc
- https://docs.nestjs.com/techniques/database

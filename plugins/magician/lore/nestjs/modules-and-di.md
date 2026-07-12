# nestjs — Modules & dependency injection

Scope: `@Module` graph, provider scopes, constructor DI + tokens, dynamic modules, circular deps, global modules. NestJS 11 (current) vs 10. Assume TS/Node lore exists separately.

## `@Module` metadata

Four keys: `providers` (instantiated by the injector, shared within the module), `controllers`, `imports` (modules whose *exports* you need), `exports` (subset of providers/imported-modules exposed to importers).

### DO
- Keep modules feature-scoped and cohesive; wire cross-module use via `imports`/`exports`.
- Export only what consumers need. A provider is invisible to other modules unless `exports`ed.
- Re-export an imported module to pass it through: `exports: [TypeOrmModule]` (importer gets its providers without re-importing).
- `imports: [CommonModule]` — NestJS dedupes; the same module imported twice yields one shared instance.

### DON'T
- Don't list a provider in `providers` of two sibling modules expecting one instance — you get two. Put it in one module, `export` it, `import` that module.
- Don't put controllers in `imports` or providers in `controllers`. Wrong slot = silent non-registration.
- Don't import a module for a provider it doesn't `export` — resolution fails at bootstrap.

## Providers & constructor DI

Default token is the class itself; Nest resolves by type via `reflect-metadata`.

```ts
@Injectable()
export class CatsService {
  constructor(private readonly repo: CatsRepository) {}
}
```

### DO
- Prefer class tokens. Use `@Inject(TOKEN)` only for non-class tokens (strings/symbols) or interfaces.
- Define token constants (`export const CONNECTION = Symbol('CONNECTION')`) — avoid magic strings scattered across files.
- Mark optional deps: `@Optional() @Inject('X')`.
- Keep `emitDecoratorMetadata`/`experimentalDecorators` on in `tsconfig`; type-based DI needs it.

### DON'T
- Don't inject by interface without a token — interfaces vanish at runtime; use `@Inject('IFoo')` + a string/symbol token.
- Don't do work in constructors (I/O, connections). Use lifecycle hooks (`onModuleInit`).

## Custom providers

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

### DO
- Use `useExisting` for aliases so both tokens resolve to one singleton.
- Order `inject` array positionally to match factory params.

### DON'T
- Don't confuse `useClass` (new instance per token) with `useExisting` (shared instance).
- Don't block startup on slow async factories without a timeout/failure path.

## Scopes

`DEFAULT` (singleton, cached at startup — recommended), `REQUEST` (new instance per request), `TRANSIENT` (new instance per consumer).

```ts
@Injectable({ scope: Scope.REQUEST })
export class RequestService {}
```

Scope on custom providers: add `scope: Scope.TRANSIENT` to the provider object.

### DO
- Default to singleton. Reach for `REQUEST` only when you truly need per-request state (e.g. request-bound context).
- Inject the request in request scope: `constructor(@Inject(REQUEST) private req: Request)` (`REQUEST` from `@nestjs/core`).
- For multi-tenant per-request pooling, use **durable providers** to avoid per-request instantiation cost: `@Injectable({ scope: Scope.REQUEST, durable: true })` + a `ContextIdStrategy` that groups by tenant.

### DON'T
- Don't scatter `REQUEST` scope. It **bubbles up**: any controller/provider depending on a request-scoped provider becomes request-scoped too, killing singleton caching and adding per-request instantiation latency.
- Don't assume `TRANSIENT` bubbles — it doesn't; a singleton injecting a transient gets one fresh instance and stays singleton.
- Don't `moduleRef.get()` a scoped provider — use `await moduleRef.resolve(Svc, contextId)`; `resolve()` returns a distinct instance per call/sub-tree.

## Dynamic modules (`forRoot` / `forFeature` / `register`)

```ts
@Module({})
export class DatabaseModule {
  static forRoot(opts): DynamicModule {
    return { module: DatabaseModule, providers: [...], exports: [...] };
  }
}
```

Convention: `forRoot`/`forRootAsync` = global-ish one-time config; `forFeature` = per-feature scoping (e.g. `TypeOrmModule.forFeature([User])`); `register` = per-import config.

### DO
- Prefer `ConfigurableModuleBuilder` for config modules — generates the class + `MODULE_OPTIONS_TOKEN` and `*Async` variants:
  ```ts
  export const { ConfigurableModuleClass, MODULE_OPTIONS_TOKEN } =
    new ConfigurableModuleBuilder<Opts>().setClassMethodName('forRoot').build();
  ```
- Return `global: true` inside the `DynamicModule` to register a configured module globally.

### DON'T
- Don't hardcode config in `providers`; thread options through the static method + a token.

## Global modules

```ts
@Global()
@Module({ providers: [CatsService], exports: [CatsService] })
export class CatsModule {}
```

### DO
- Register global modules **once**, in the root/core module. Exports become injectable app-wide without re-importing.

### DON'T
- Don't overuse `@Global()` — it hides dependency edges and hurts testability/modularity. Reserve for truly cross-cutting infra (config, logger).

## Circular dependencies

### DON'T
- Don't create circular provider/module refs. First fix: extract shared logic into a third module — restructuring beats `forwardRef`.

### DO (only if unavoidable)
```ts
constructor(@Inject(forwardRef(() => CatsService)) private cats: CatsService) {}
```
- Module-to-module: `imports: [forwardRef(() => OtherModule)]` on *both* sides.

## Testing

```ts
const moduleRef = await Test.createTestingModule({
  controllers: [CatsController], providers: [CatsService],
}).overrideProvider(CatsService).useValue(mock).compile();

const ctrl = moduleRef.get(CatsController);          // singletons
const svc  = await moduleRef.resolve(RequestSvc);    // scoped: unique per call
```

### DO
- `overrideProvider(...).useValue/useClass/useFactory(...)` to inject test doubles.
- Use `get()` for singletons, `resolve()` for request/transient.

## NestJS 11 vs 10 (DI-relevant)

- **Express 5** is the default HTTP adapter in v11 (Express 4 in v10). Path matching changed (`path-to-regexp` upgrade): wildcard `*` → named `{*splat}`; v11 auto-converts old Express-4 wildcards but don't rely on it. **Fastify 5** is v11's default Fastify major; Fastify middleware `(.*)` no longer works — use `*splat`.
- **Reflector** type inference improved in v11: `getAllAndOverride` returns `T | undefined`; `getAllAndMerge` returns an object for single object metadata. Adjust guard/interceptor metadata typing when upgrading.
- Overall v10→v11 is a light migration; the above are the main gotchas. Verify against the migration guide before upgrading.

## Security notes (DI surface)

- Never `useValue` secrets inline in module files committed to VCS — thread via config/env behind a token.
- Don't leak internals: keep infra providers unexported unless consumers need them.
- Validate config at the module boundary (e.g. `ConfigModule` schema validation) so bad env fails fast at bootstrap, not per request.

## Sources
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

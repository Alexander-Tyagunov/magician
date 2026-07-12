# nestjs — Request pipeline

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

## Middleware — DO
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

## Middleware — DON'T
- DON'T put auth/authz here — use **guards** (they see `ExecutionContext` and the target handler; middleware doesn't).
- DON'T expect DI in `app.use(...)` global middleware — not possible; use functional or `.forRoutes('*')`.
- DON'T reuse Express 4 wildcards on Nest 11. Express 5 / `path-to-regexp` v8: `*` → `*splat`, optional `?` → `{...}`. Fastify 5 middleware: `(.*)` → `*splat`.
- DON'T rely on module order for globals — in Nest 11 middleware from **global modules runs first** regardless of graph position.

## Guards — DO (authz)
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

## Guards — DON'T
- DON'T use `app.useGlobalGuards(new G())` when the guard needs injected deps — use `APP_GUARD` (`useClass`) so DI works.
- DON'T do authn/z in interceptors or pipes — wrong layer, guards short-circuit earliest.
- DON'T trust a role claim without an authentication guard having set `request.user` first.

## Interceptors — DO (cross-cutting)
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

## Interceptors — DON'T
- DON'T forget to return `next.handle()` — omit the call and **the handler never runs**.
- DON'T use `app.useGlobalInterceptors(...)` for DI-needing interceptors — use `APP_INTERCEPTOR`.
- DON'T bury business logic here.

## Pipes / ValidationPipe — DO (validate + sanitize)
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

## Pipes — DON'T
- DON'T accept raw `@Body()` without a decorated DTO — no decorators means `whitelist` strips everything.
- DON'T skip `forbidNonWhitelisted` — silent stripping hides malformed/malicious payloads.
- DON'T return validation error detail to clients in prod (`disableErrorMessages: true`).
- DON'T rely on `useGlobalPipes` for gateways/microservices in hybrid apps — it doesn't apply there.
- DON'T use `app.useGlobalPipes` when the pipe needs DI — use `APP_PIPE`.

## Exception filters — DO
- `@Catch(HttpException)` + `ExceptionFilter.catch(exception, host)`; get response via `host.switchToHttp().getResponse()`.
- Throw built-ins (`BadRequestException`, `UnauthorizedException`, `NotFoundException`, `ForbiddenException`, `InternalServerErrorException`) — all extend `HttpException`.
- Catch-all: extend `BaseExceptionFilter`, call `super.catch(...)` for unknowns. Declare the "catch anything" filter **first**.
- Global-with-DI via `APP_FILTER`. Prefer binding **classes** over instances.

## Exception filters — DON'T
- DON'T leak stack traces or internal messages — log server-side, return a sanitized shape.
- DON'T `new` a filter that extends `BaseExceptionFilter` at method/controller scope.
- DON'T swallow non-HTTP errors silently — map them to 500 via the catch-all.

## Version notes
- **NestJS 11** (Node 20+): Express **5** default (async errors auto-forwarded; `path-to-regexp` v8 wildcards; query parser is "simple" — `app.set('query parser','extended')` for nested). Fastify 5 supported (CORS only safelisted methods by default). `Reflector.getAllAndOverride` → `T | undefined`; `getAllAndMerge` returns an object for a single object entry.
- **NestJS 10**: Express **4** by default (Express 4 wildcard/regex route syntax).
- `class-validator`/`class-transformer` and `@nestjs/mapped-types` are separate installs.

## Sources
- https://docs.nestjs.com/middleware
- https://docs.nestjs.com/guards
- https://docs.nestjs.com/interceptors
- https://docs.nestjs.com/pipes
- https://docs.nestjs.com/exception-filters
- https://docs.nestjs.com/techniques/validation
- https://docs.nestjs.com/migration-guide

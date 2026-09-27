# micronaut — deep dive

> On-demand companion to `lore/micronaut.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Compile-time DI & AOT](#di-and-aot) · [HTTP server & declarative clients](#http-server-and-clients) · [Micronaut Data & reactive](#data-and-reactive) · [GraalVM native & testing](#native-and-testing)

## Compile-time DI & AOT <a id="di-and-aot"></a>

Micronaut resolves DI/AOP **at compile time** via annotation processors that generate `BeanDefinition` classes (ASM bytecode). No runtime classpath scanning, no reflection-based injection, no runtime-generated proxies. Startup time and heap are ~independent of codebase size; native-image friendly. Contrast Spring: runtime reflection + runtime proxies, cost scales with bean count.

Version map (verify before asserting):
- **Micronaut 5.x** (current): Java **25** baseline, Groovy 5, Kotlin 2.3, GraalVM 25.0.3; `jakarta.*`.
- **Micronaut 4.x**: Java **17** baseline; completed `javax`→`jakarta` (`jakarta.inject`/`.validation`/`.persistence`).
- **Micronaut 3.x**: Java **8** baseline; accepted both `javax.inject` and `jakarta.inject`.

### DO — annotation processor wiring

- DO register the annotation processor — without it no `BeanDefinition` is generated and the bean is invisible at runtime. The `io.micronaut.application` Gradle plugin wires `micronaut-inject-java`; for plain libs add it manually.
- DO put every processor (inject, validation, data, openapi) on `annotationProcessor`/`ksp`, not `implementation`. Kotlin: use **KSP** on MN 4+ (kapt is legacy).
- DO recompile after annotation changes — DI errors surface at build time, not startup.

### DO — beans, scopes, factories

- DO annotate managed classes with a scope. **Default scope is `@Prototype`** (new instance per injection point); `@Prototype` is a synonym for `@Bean`.
- DO use `jakarta.inject.Singleton` for shared state. Constructor injection is preferred (no annotation needed for a single constructor).

```java
import jakarta.inject.Singleton;

@Singleton
class OrderService {
    private final Repo repo;
    OrderService(Repo repo) { this.repo = repo; } // constructor injection
}
```

- DO use `@Factory` for beans you don't own (third-party/conditional). **Factory methods default to `@Singleton`**; annotate `@Prototype` for per-injection.

```java
import io.micronaut.context.annotation.Factory;
import jakarta.inject.Singleton;

@Factory
class Clients {
    @Singleton HttpClient httpClient() { return HttpClient.create(...); }
}
```

- DO pick scopes deliberately: `@Singleton` (one instance); `@Prototype`/`@Bean` (new each injection, default); `@Context` (eager, built with `ApplicationContext`); `@RequestScope` (per HTTP request); `@Refreshable` (rebuilt on `RefreshEvent`/`/refresh`); `@ThreadLocal`; `@Infrastructure` (unreplaceable core beans).
- DO qualify ambiguous beans with `jakarta.inject.Named` (or custom `@Qualifier`); `@Primary`/`@Secondary` to bias; `@Any` + `BeanProvider<T>` for deferred/multi resolution.
- DO drive conditional beans with `@Requires` (`property`, `beans`, `classes`, `env`, `missingBeans`). Use `@Replaces(Bean.class)` to override (great for tests).

### DON'T

- DON'T rely on runtime component scanning / `@ComponentScan` — nothing is discovered at runtime; if it wasn't compile-time processed it doesn't exist.
- DON'T inject into `private` fields — Micronaut falls back to reflection there (breaks native-image assumptions). Use constructor or `protected`/package-private `@Inject`.
- DON'T expect Spring proxies. AOP advice is a generated `MethodInterceptor` applied only to advice-annotated methods; self-invocation bypasses it (as in Spring).
- DON'T mix `javax.inject` on MN 4/5 (removed). DON'T assume a factory method is prototype — it's singleton unless annotated.

### DO — configuration (type-safe, compile-time)

- DO model config with `@ConfigurationProperties("prefix")`. Prefer **immutable** config via `@ConfigurationInject` on the constructor.

```java
@ConfigurationProperties("engine")
public class EngineConfig {
    @ConfigurationInject
    public EngineConfig(@Nullable String name, int year) { ... }
}
```

- DO use `@EachProperty("my.datasources")` + `@Parameter` for one-bean-per-sub-key config; `@EachBean` for a dependent bean per existing bean.
- DO inject single values with `@Value("${x:default}")` or `@Property(name="x")`; add `jakarta.validation` constraints — validated at startup.

### DO — reflection-free data & native image

- DO annotate value/DTO types with `@Introspected` for compile-time `BeanIntrospection` (reflection-free property access). Required for many bind/serialize paths under native-image.
- DO prefer **Micronaut Serialization** (`micronaut-serialization`, `@Serdeable`) over Jackson Databind for native builds — serializers computed at build time. With Jackson Databind, non-introspected types need `@ReflectiveAccess` (MN 5) or GraalVM metadata.
- DON'T add libs needing runtime reflection/CGLIB without GraalVM reachability metadata — they fail in native image.

### DO — AOT (ahead-of-time optimization)

Micronaut AOT is a **build-time** post-processor (not a runtime dep) that precomputes startup work. Experimental — pin versions. Enable via the build plugin, not app config.

- Gradle: apply both plugins; configure the `aot` DSL.

```groovy
plugins {
    id("io.micronaut.application") version "..."
    id("io.micronaut.aot")         version "..."
}
micronaut {
    aot {
        convertYamlToJava.set(true)     // YAML → Java config
        precomputeOperations.set(true)
        cacheEnvironment.set(true)      // env immutable after startup
        netty { enabled.set(true) }     // Netty startup props
    }
}
```

- Maven: `micronaut-maven-plugin` (`<configuration><aot>…`).
- DO build/run optimized artifacts: Gradle tasks `optimizedJar`, `optimizedRun`, `optimizedJitJarAll` (fat jar, needs shadow), `nativeOptimizedCompile`, `optimizedDockerBuild`.
- DO push non-DSL optimizers via `configFile.set(file("gradle/micronaut-aot.properties"))` or `aotPlugins`; diagnostics report: `micronaut.aot.report.enabled=true`.
- DON'T hand-edit AOT-generated sources or add these keys to `application.yml` — they belong to the build plugin only.

### Spring → Micronaut deltas (reviewer notes)

- `@Component/@Service/@Repository` → `@Singleton` (+ `@Introspected` where needed); `@Bean` methods → `@Factory` methods.
- `@Autowired` → constructor injection / `jakarta.inject.Inject`; `@Qualifier` → `@Named`.
- `@Conditional...` → `@Requires`; `@Profile` → `@Requires(env=...)`.
- No `BeanFactoryPostProcessor`/runtime-proxy tricks — extend via annotation processors, `@Introduction`/`@Around` AOP, or bean events.

### Sources

- Micronaut User Guide (latest / 5.x): https://docs.micronaut.io/latest/guide/
- Micronaut 4 User Guide (Java 17 baseline, javax→jakarta): https://docs.micronaut.io/4.9.0/guide/
- Micronaut Guides: https://guides.micronaut.io/
- micronaut-core (IoC scopes, factories, config, introspection, breaking changes): https://github.com/micronaut-projects/micronaut-core
- Micronaut 5 Release notes (Java 25 / Groovy 5 / Kotlin 2.3 / GraalVM 25.0.3): https://github.com/micronaut-projects/micronaut-core/wiki/Micronaut-5-Release
- Micronaut AOT reference: https://micronaut-projects.github.io/micronaut-aot/latest/guide/
- Micronaut Gradle plugin (application + AOT plugins, DSL, tasks): https://micronaut-projects.github.io/micronaut-gradle-plugin/latest/
- Micronaut Serialization (`@Serdeable`, build-time serializers): https://github.com/micronaut-projects/micronaut-serialization

## HTTP server & declarative clients <a id="http-server-and-clients"></a>

Framework-specifics only (Java-language lore lives in `lore/deep/java.md`). Netty-based, compile-time (annotation processor) — no runtime reflection/proxies. **Micronaut 5.x** current (JDK 25 baseline); prior **4.x** (JDK 17). Both use `jakarta.*` (`jakarta.inject`, `jakarta.validation`); 3.x used some `javax.*` — don't port 3.x imports blindly.

### Controllers & routing

DO annotate the class `@Controller("/path")` and methods with `@Get`/`@Post`/`@Put`/`@Delete`/`@Patch`/`@Head` from `io.micronaut.http.annotation`. Routes returning objects serialize to JSON by default.
DO bind params explicitly: `@PathVariable`, `@QueryValue`, `@Body`, `@Header`, `@CookieValue`, `@RequestAttribute` — all from `io.micronaut.http.annotation`. URI template vars (`@Get("/{id}")`) bind by name automatically.
DO set content types with `produces`/`consumes` on the method or `@Produces`/`@Consumes`, using `io.micronaut.http.MediaType` constants.
DON'T rely on classpath scanning — a controller not found means the annotation processor didn't run (wire `micronaut-inject-java` / `kapt` / `ksp`). DON'T return `null` for "not found"; return `HttpResponse.notFound()` or throw and handle.

```java
@Controller("/pets")
public class PetController {
    @Get("/{name}")                       // GET /pets/Fido
    public Pet get(@PathVariable String name) { ... }

    @Post                                  // JSON body -> POJO
    @Status(HttpStatus.CREATED)            // io.micronaut.http.annotation.Status
    public Pet add(@Body @Valid PetCmd cmd) { ... }
}
```

DO put `@Introspected` on request/response POJOs (reflection-free serde; required for GraalVM native).

### Blocking vs reactive return types

Netty runs on a small event loop. The return type controls threading.
DO return a **reactive type** (Reactor `Mono`/`Flux`, RxJava, or `Publisher`) or `CompletableFuture` for non-blocking I/O — Micronaut subscribes on the event loop.
DO offload **blocking** work (JDBC, blocking clients) with `@ExecuteOn(TaskExecutors.BLOCKING)` (`io.micronaut.scheduling.annotation.ExecuteOn`, `io.micronaut.scheduling.TaskExecutors`) — never run it on the event loop.
DON'T block inside a method that returns a reactive type. DON'T call `.block()`/`toBlocking()` on the event loop.

On Micronaut 4+/JDK 21+, `TaskExecutors.BLOCKING` uses **virtual threads** automatically when available, else falls back to the `io` pool.

```java
@Get("/{id}")
@ExecuteOn(TaskExecutors.BLOCKING)   // JDBC is blocking
public Order load(@PathVariable Long id) { return repo.findById(id); }

@Get("/stream")
public Flux<Event> stream() { return service.events(); }  // reactive, no @ExecuteOn
```

### Declarative @Client (headline feature)

DO define an **interface** annotated `@Client` (`io.micronaut.http.client.annotation.Client`) — Micronaut generates the implementation at **compile time** (no reflection/proxies). Requires the `micronaut-http-client` dependency.
DO reuse the same HTTP-method/param annotations as controllers — a controller interface can be shared and implemented by both server and client.
DO choose the return type for semantics: `Mono<T>`/`Publisher<T>` (non-blocking), `CompletableFuture<T>`, or a plain type `T` (blocking call). A `@Body Object` with no `@Produces` defaults Content-Type to `application/json`.
DO target by URL, service id, or `@Client(id = "svcName")` for service discovery / load balancing.
DON'T hand-write `HttpClient` calls when a declarative client fits. DON'T ignore errors: non-2xx throws `HttpClientResponseException` (`io.micronaut.http.client.exceptions`) on blocking calls / signals `onError` on reactive.

```java
@Client("https://api.example.com")
public interface PetClient {
    @Get("/pets/{name}") Mono<Pet> find(@PathVariable String name);
    @Post("/pets")       Pet create(@Body @Valid PetCmd cmd);   // blocking
}
```

DO add `@Retryable`/`@CircuitBreaker` for resilience; a `@Fallback` bean (`io.micronaut.retry.annotation.Fallback`) supplies a backup impl after retries exhaust. Use the low-level `HttpClient` only for dynamic URLs.

### Validation

Since **Micronaut 4**, validation is a **separate module** — add `io.micronaut.validation:micronaut-validation` and the `micronaut-validation-processor` on the annotation-processor path. (Micronaut 3 shipped it in core / via hibernate-validator.)
DO annotate the controller class `@Validated` (`io.micronaut.validation.Validated`) and put `jakarta.validation.constraints.*` (`@NotBlank`, `@NotNull`, `@Min`, …) on params; `@Valid` cascades into `@Body` POJOs.
DON'T expect validation without `@Validated` on the type. A violation throws `jakarta.validation.ConstraintViolationException`, mapped to **HTTP 400** by the built-in `ConstraintExceptionHandler`.

```java
@Validated
@Controller("/email")
public class EmailController {
    @Get("/send/{to}")
    public String send(@PathVariable @NotBlank String to) { ... }
}
```

### Error handling

DO handle exceptions locally with `@Error` (`io.micronaut.http.annotation.Error`) inside a controller, or globally with a `@Singleton` bean implementing `ExceptionHandler<E, HttpResponse>`.
DO set status via `@Status` or by returning `HttpResponse.status(...)`.
DON'T let raw exceptions leak; map to a stable response (`JsonError`/`io.micronaut.http.hateoas` or a custom body).

```java
@Error(global = true, exception = OutOfStock.class)
public HttpResponse<JsonError> oos() {
    return HttpResponse.badRequest(new JsonError("out of stock"));
}
```

### Filters

**Micronaut 4+ (preferred): annotation filter methods.** DO declare a bean `@ServerFilter("/path/**")` (or `@ClientFilter` for clients) with methods annotated `@RequestFilter` (runs before) / `@ResponseFilter` (runs after). Filter method params bind like controllers (`HttpRequest`, `MutableHttpResponse`, `@Header`, etc.); add `@PreMatching` to run before route matching.
DO order with `@Order`/`@Priority`/`Ordered`: request filters run highest→lowest, response filters lowest→highest.

```java
@ServerFilter("/**")
@Order(HIGHEST_PRECEDENCE)
public class TraceFilter {
    @RequestFilter void onRequest(HttpRequest<?> req) { MDC.put("rid", newId()); }
    @ResponseFilter void onResponse(MutableHttpResponse<?> res) { res.header("X-Trace", ...); }
}
```

**Legacy (still supported):** implement `HttpServerFilter.doFilter(request, chain)` returning `Publisher<MutableHttpResponse<?>>`, annotated `@Filter("/path/**")`. DON'T block inside it — chain on the reactive result. Prefer the annotation style for new code.

### Testing

DO use `@MicronautTest` (`micronaut-test-junit5`); inject `EmbeddedServer` and an `@Client` or `HttpClient`; assert via `httpClient.toBlocking().exchange(...)`.

### Sources

- Micronaut User Guide (5.x): https://docs.micronaut.io/latest/guide/
- micronaut-core source docs (branch 5.1.x): https://github.com/micronaut-projects/micronaut-core/tree/5.1.x/src/main/docs/guide
- HTTP client / declarative `@Client`: https://docs.micronaut.io/latest/guide/#httpClient
- Data validation: https://docs.micronaut.io/latest/guide/#validation
- HTTP filters (design + methods): https://github.com/micronaut-projects/micronaut-core/wiki/Filter-design-doc
- Micronaut Guides: https://guides.micronaut.io/

## Micronaut Data & reactive <a id="data-and-reactive"></a>

Framework-specific checklist for Micronaut Data (compile-time repositories) and the reactive/R2DBC stack. Assumes `lore/deep/java.md` covers the language. Complements `jdbc`/`orm` lore.

**Version map (verify against the target project's build file):**
- **Micronaut Framework 5.x** (current, `5.1.x`) — JDK 25 baseline, Groovy 5, Kotlin 2.3.
- **Micronaut Framework 4.x** (prior major) — JDK 17 baseline; 3.x — JDK 8 minimum.
- **Micronaut Data 5.x** (current, `5.0.x`/`5.1.x`) ships with framework 5. Micronaut Data 4.x pairs with framework 4.x.
- All coordinates use groupId `io.micronaut.data`. Prefer Micronaut Launch/CLI `--features` over hand-writing coordinates.

### Core model — DO
- DO treat Micronaut Data as **AoT / compile-time**: queries are pre-computed by the annotation processor. No runtime model, no query translation, no reflection, no runtime proxies. A missing/ambiguous root entity is a **compile error**, not a runtime one.
- DO add the annotation processor. It is mandatory or repositories generate nothing:
  ```gradle
  annotationProcessor("io.micronaut.data:micronaut-data-processor")
  // MongoDB/Cosmos instead use micronaut-data-document-processor
  ```
- DO define repositories as **interfaces** extending a repository type, annotated per backend:
  ```java
  @JdbcRepository(dialect = Dialect.POSTGRES)          // JDBC
  public interface BookRepository extends CrudRepository<Book, Long> {}
  ```
- DO map entities with Micronaut Data annotations (`io.micronaut.data.annotation.*`): `@MappedEntity`, `@Id`, `@GeneratedValue`, `@Version` (optimistic lock), `@Query`, `@Join`, `@Where`. For JPA/Hibernate backend, use `jakarta.persistence.*` on entities instead.
- DO add `@Serdeable` (or configure serde) on entities exposed via JSON — Micronaut avoids reflection.

### Core model — DON'T
- DON'T omit `dialect` on SQL repositories. Queries are compiled per-dialect: `@JdbcRepository(dialect = Dialect.X)` / `@R2dbcRepository(dialect = Dialect.X)`. Wrong dialect → wrong SQL at build time.
- DON'T unit-test against H2 while production is Postgres by silently swapping. DO test against the real dialect via Testcontainers; if you must run H2 in tests, define a `@Replaces` subinterface pinned to `Dialect.H2`.
- DON'T expect Spring Data-style runtime query parsing. Everything derivable from the method name/return type is resolved at compile time.

### Backend selection — DO
- **JDBC** (blocking, lightweight, no JPA): feature `data-jdbc`, `io.micronaut.data:micronaut-data-jdbc` + a pool feature (`jdbc-hikari`). Use `@JdbcRepository`.
- **R2DBC** (non-blocking SQL): feature `data-r2dbc`, `io.micronaut.data:micronaut-data-r2dbc`. Use `@R2dbcRepository`. Repository methods return reactive types.
- **JPA/Hibernate**: feature `data-hibernate-jpa`. Use `@Repository`; full Hibernate/JPQL. Heaviest runtime.
- **Hibernate Reactive**: feature `data-hibernate-reactive` — reactive JPA on a Vert.x SQL client.
- **MongoDB / Azure Cosmos**: document backends via `micronaut-data-document-processor`.

### Datasources & transactions — DO
- DO configure datasources under `datasources.*` (JDBC) / `r2dbc.datasources.*` (R2DBC):
  ```yaml
  datasources:
    default:
      url: jdbc:postgresql://localhost:5432/app
      dialect: POSTGRES
      driver-class-name: org.postgresql.Driver
  ```
- DO scope a repo to a named datasource when multiple exist: `@JdbcRepository(dialect = ..., dataSource = "inventory")`; default is the primary datasource.
- DO drive blocking transactions with `@Transactional` (`jakarta.transaction.Transactional`, or `io.micronaut.transaction.annotation.Transactional` for datasource-qualified `@Transactional("inventory")`). Mark reads `@Transactional(readOnly = true)`.
- DON'T call `@Transactional` methods from within the same bean (self-invocation bypasses the AOP interceptor). Split into a collaborating bean.

### Reactive repositories — DO
- DO pick the repository interface by reactive runtime; methods return the matching type:
  - `ReactiveStreamsCrudRepository` → `Publisher`
  - `ReactorCrudRepository` / `ReactorPageableRepository` → `Mono`/`Flux` (needs `io.micronaut.reactor:micronaut-reactor`)
  - `RxJavaCrudRepository` → **RxJava 2** (`io.reactivex.*` types; module `io.micronaut.rxjava2:micronaut-rxjava2`). For RxJava 3 (`io.reactivex.rxjava3.*`) add `io.micronaut.rxjava3:micronaut-rxjava3` and return its `Single`/`Flowable` from a `ReactiveStreamsCrudRepository`.
  - `CoroutineCrudRepository` / `CoroutinePageableCrudRepository` → Kotlin `suspend` + `Flow`
  - `AsyncCrudRepository` → `CompletableFuture`
- DO use R2DBC (or Hibernate Reactive) as the backend for reactive repos so I/O is truly non-blocking. When the driver natively supports reactive types, the I/O thread pool is **not** used — the driver handles it.
- DO manage reactive transactions declaratively with `@Transactional` on a `@R2dbcRepository`, or programmatically:
  ```java
  r2dbcOperations.withTransaction(status -> /* Mono/Flux */ Mono.empty());
  ```

### Reactive — DON'T
- DON'T put a **JDBC** (`@JdbcRepository`) repo behind a reactive controller expecting non-blocking behavior — JDBC is blocking regardless of return type. Use R2DBC, or offload with `@ExecuteOn` (see virtual threads).
- DON'T call `.block()` / `.toBlocking()` on repository results in production request paths.
- DON'T mix reactive dependencies you didn't add: `Mono`/`Flux` need `micronaut-reactor` on the classpath.

### Blocking on virtual threads (framework 4+/JDK 21+) — DO
- DO offload blocking work (JDBC, blocking clients) off the Netty event loop with `@ExecuteOn`:
  ```java
  @Get @ExecuteOn(TaskExecutors.BLOCKING)
  public List<Book> list() { return repo.findAll(); }  // JDBC repo, safe here
  ```
- DO rely on the `blocking` executor auto-using **virtual threads** when the JDK supports them; otherwise Micronaut aliases `blocking` to the `io` pool. On JDK 19/20 it required `--enable-preview`; finalized in JDK 21.
- DON'T block the event loop directly. DON'T pin virtual threads inside `synchronized` blocks holding JDBC connections — prefer `ReentrantLock`. The experimental Netty `loom-carrier` flag (`micronaut.netty.event-loops.default.loom-carrier: true`) needs preview features + open JDK internals — avoid outside experiments.

### Sources
- Micronaut Data reference (5.x): https://micronaut-projects.github.io/micronaut-data/latest/guide/
- Micronaut Framework reference (5.1.x): https://docs.micronaut.io/latest/guide/
- Virtual Threads / thread pools: https://docs.micronaut.io/latest/guide/#virtualThreads
- Access a DB with Micronaut Data JDBC (guide): https://guides.micronaut.io/latest/micronaut-data-jdbc-repository.html
- Micronaut Data source (5.1.x branch): https://github.com/micronaut-projects/micronaut-data
- Micronaut Core source (5.1.x branch): https://github.com/micronaut-projects/micronaut-core

## GraalVM native & testing <a id="native-and-testing"></a>

Senior-reviewer checklist. Framework-specifics only (Java-language lore lives in `lore/deep/java.md`). Verify version facts against docs, never memory.

Versions: **Micronaut 5.x** current (5.1.x; JDK 25 baseline). Prior **4.x** (Java 17). Both use `jakarta.*`. Native/test annotations below are stable across 4→5. Native build wiring is the same; only the JDK/GraalVM baseline moves.

Micronaut's edge is compile-time DI/AOT — it emits GraalVM reflection/resource/proxy metadata for its own beans automatically. You only configure the reflection GraalVM can't see: your reflectively-accessed types and third-party libs.

### GraalVM native build

DO scaffold with the `graalvm` feature: `mn create-app --features=graalvm demo` — wires the native plugin + a GraalVM base Dockerfile.
DO build the native executable:
- Gradle: `./gradlew nativeCompile` (via `io.micronaut.application` plugin, which applies `org.graalvm.buildtools.native`). Native container image: `./gradlew dockerBuildNative`.
- Maven: `./mvnw package -Dpackaging=native-image`. Native container: `-Dpackaging=docker-native`.
DO run the build on a **GraalVM JDK** matching the framework baseline (JDK 25 for MN 5, 17 for MN 4) with the `native-image` component installed. Verify with `native-image --version`.
DON'T hand-invoke `native-image` — let the build plugin pass the generated arg files. DON'T expect a plain OpenJDK to compile native.

### Reflection & resource config

DO annotate every POJO crossing DI / serialization / HTTP boundaries with `@Introspected` — compile-time, reflection-free bean access; the native-safe default.
DO use `@ReflectiveAccess` (`io.micronaut.core.annotation`) on the specific type/constructor/method/field that genuinely needs runtime reflection.
DO bulk-configure third-party types you can't annotate with `@TypeHint`:
```java
@TypeHint(value = { LinkedHashMap.class, HashSet.class },
          accessType = TypeHint.AccessType.ALL_DECLARED_CONSTRUCTORS)
```
DO use `@ReflectionConfig` (repeatable) to model GraalVM reflect entries per type in Java instead of raw JSON.
DON'T reach for hand-written `reflect.json` unless nothing else fits — it's the legacy escape hatch; prefer the annotations, which the AOT step merges into the generated config.
DO keep runtime-loaded files (templates, `application.yml`, `logback.xml`) on the classpath — Micronaut auto-registers config + logging resources for native. For extra resources add `META-INF/native-image/<group>/<artifact>/resource-config.json` (or `-H:IncludeResources` regex) so GraalVM bundles them.
DON'T rely on `Class.forName`, classpath scanning, or dynamic proxies of arbitrary interfaces at runtime — none survive native without explicit metadata.

### What breaks in native (and the fix)

DON'T use `jackson-databind` for JSON on native without help — it's reflection-heavy. DO use **Micronaut Serde** (`io.micronaut.serde:micronaut-serde-jackson`) with `@Serdeable` on DTOs — compile-time, reflection-free, native-ready. If you must keep Jackson databind, annotate each model `@ReflectiveAccess`.
DON'T assume a library "just works" — pull **GraalVM Reachability Metadata** (the buildtools plugin consumes the shared metadata repo automatically) for common libs (JDBC drivers, Netty, etc.).
DO move heavy/illegal-at-build-time work out of static initializers — build-time class init can capture host state or fail. Push such init to runtime (or mark the class for runtime init via native-image args).
DON'T read env/hostname/wall-clock at build init and bake it into the image.
DO regenerate metadata for unknown reflection with the **GraalVM tracing agent** on the JVM run (`-agentlib:native-image-agent=config-output-dir=...`), then feed the output into `META-INF/native-image`. Treat it as a last resort after annotations.

### @MicronautTest

DO add `io.micronaut.test:micronaut-test-junit5` (or `-spock` / `-kotest`) as a test dependency and ensure the annotation processor runs (`micronaut-inject-java` on `annotationProcessor`/`kapt`/`ksp`) — without it the context won't build.
DO annotate the test class; it starts an `ApplicationContext` (and the embedded server when needed) and injects beans:
```java
@MicronautTest
class OrderControllerTest {
  @Inject @Client("/") HttpClient client;   // server auto-started
  @Inject OrderService service;             // real bean injected
}
```
Key options (verify against your version):
- `transactional` (default **true**) — each test method runs in a transaction rolled back at the end. Set `@MicronautTest(rollback = false)` to commit; `transactional = false` to disable wrapping.
- `startApplication = false` — build the context but don't start the HTTP server (unit-style).
- `environments = {"test","integration"}` — activate env-specific config.
- `application = App.class` / `packages = "com.acme"` — scope for integrations needing classpath scanning.
DO replace collaborators with `@MockBean`:
```java
@MockBean(MathService.class)
MathService mathService() { return Mockito.mock(MathService.class); }
```
DON'T rely on field injection order or shared static state across methods — the context is per-class by default.
DO inject test-only properties inline with `@Property(name="foo", value="bar")`, or dynamically via `TestPropertyProvider.getProperties()` (requires `@TestInstance(PER_CLASS)`).

### Test Resources & Testcontainers

DO prefer **Micronaut Test Resources** over hand-wiring Testcontainers. It resolves a *missing* config property by spinning up a throwaway container:
- Gradle: apply `io.micronaut.test-resources`. Maven: set `micronaut.test.resources.enabled`. Easiest via Micronaut Launch `test-resources` feature.
- Leave `datasources.default.url` **unset** in test config → it auto-provides `url`/`username`/`password`/`driver-class-name` (and R2DBC `r2dbc.datasources.*`). Detection needs one of `db-type`, `dialect`, or `driver-class-name`.
- Modules cover postgres/mysql/mariadb/oracle/mssql, kafka (`kafka.bootstrap.servers`), redis (`redis.uri`), mongodb (`mongodb.uri`), rabbitmq, elasticsearch, localstack, etc.
- Override images with `test-resources.containers.<db-type>.image-name`; MSSQL needs `test-resources.containers.mssql.accept-license=true`.
DON'T set the property AND expect a test resource — a present property short-circuits provisioning (that's how prod/CI overrides work).
DO hand-wire raw Testcontainers only when Test Resources lacks the module: implement `TestPropertyProvider` (needs `@TestInstance(PER_CLASS)`), `db.start()`, and return `datasources.default.url`/`username`/`password` from `getProperties()`.
DON'T point integration tests at shared/staging infra; bind slow ITs to `*IT` + Failsafe, keep fast `@MicronautTest` units on Surefire (see `lore/deep/java.md#build-and-testing`).

### Sources

- Micronaut Reference (guide): https://docs.micronaut.io/latest/guide/
- GraalVM support (graalServices/graalFAQ): https://docs.micronaut.io/latest/guide/#graal
- Micronaut Guides: https://guides.micronaut.io/
- Micronaut Test: https://micronaut-projects.github.io/micronaut-test/latest/guide/
- Micronaut Test Resources: https://micronaut-projects.github.io/micronaut-test-resources/latest/guide/
- Micronaut Serde: https://micronaut-projects.github.io/micronaut-serde/latest/guide/
- micronaut-core (5.1.x docs source): https://github.com/micronaut-projects/micronaut-core
- GraalVM Native Build Tools: https://graalvm.github.io/native-build-tools/latest/

# micronaut — HTTP server & declarative clients

Framework-specifics only (Java-language lore lives in `lore/java/*`). Netty-based, compile-time (annotation processor) — no runtime reflection/proxies. **Micronaut 5.x** current (JDK 25 baseline); prior **4.x** (JDK 17). Both use `jakarta.*` (`jakarta.inject`, `jakarta.validation`); 3.x used some `javax.*` — don't port 3.x imports blindly.

## Controllers & routing

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

## Blocking vs reactive return types

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

## Declarative @Client (headline feature)

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

## Validation

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

## Error handling

DO handle exceptions locally with `@Error` (`io.micronaut.http.annotation.Error`) inside a controller, or globally with a `@Singleton` bean implementing `ExceptionHandler<E, HttpResponse>`.
DO set status via `@Status` or by returning `HttpResponse.status(...)`.
DON'T let raw exceptions leak; map to a stable response (`JsonError`/`io.micronaut.http.hateoas` or a custom body).

```java
@Error(global = true, exception = OutOfStock.class)
public HttpResponse<JsonError> oos() {
    return HttpResponse.badRequest(new JsonError("out of stock"));
}
```

## Filters

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

## Testing

DO use `@MicronautTest` (`micronaut-test-junit5`); inject `EmbeddedServer` and an `@Client` or `HttpClient`; assert via `httpClient.toBlocking().exchange(...)`.

## Sources

- Micronaut User Guide (5.x): https://docs.micronaut.io/latest/guide/
- micronaut-core source docs (branch 5.1.x): https://github.com/micronaut-projects/micronaut-core/tree/5.1.x/src/main/docs/guide
- HTTP client / declarative `@Client`: https://docs.micronaut.io/latest/guide/#httpClient
- Data validation: https://docs.micronaut.io/latest/guide/#validation
- HTTP filters (design + methods): https://github.com/micronaut-projects/micronaut-core/wiki/Filter-design-doc
- Micronaut Guides: https://guides.micronaut.io/

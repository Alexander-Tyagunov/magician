# spring — Web: MVC (servlet) vs WebFlux (reactive)

Framework-specific lore. Java-language rules live in `lore/java/*`.

Two web stacks, never mix in one request path:
- **Spring MVC** — servlet, blocking, thread-per-request. Default embedded server **Tomcat**. Starter `spring-boot-starter-web`.
- **Spring WebFlux** — reactive, non-blocking, event-loop. Default embedded server **Reactor Netty**. Starter `spring-boot-starter-webflux`. Built on **Project Reactor** (`Mono`/`Flux`), since Spring Framework 5.0.

## Version baselines (verify against current docs before asserting)
- **Boot 4.x** (current GA 4.1.0): Java 17+ (tested to Java 26), Spring Framework 7.0.8+, `jakarta.*`.
- **Boot 3.x**: Java 17+, Spring Framework 6, `jakarta.*`.
- **Boot 2.x** (OSS EOL): Java 8+, Spring Framework 5, `javax.*`. Migrating off 2.x = `javax.*` → `jakarta.*` package rename.

## DO — choosing the stack
- DO default to **MVC** for typical CRUD/REST/DB apps. Simpler stack traces, blocking JDBC, imperative code.
- DO pick **WebFlux** only when you need non-blocking end-to-end: high-concurrency I/O fan-out, streaming (SSE/`Flux`), or a reactive datastore (R2DBC, reactive Mongo). Reactive only pays off if the *whole* chain is reactive.
- DO use **virtual threads** (Boot 3.2+, `spring.threads.virtual.enabled=true`, **Java 21+**, Java 24+ recommended) to get high-concurrency scaling on the **MVC** stack without rewriting to Reactor. This is the modern answer for "MVC but scale to many blocked I/O calls."
  ```properties
  spring.threads.virtual.enabled=true
  ```
- DON'T reach for WebFlux just for throughput if the app blocks on JDBC — virtual-thread MVC is simpler and usually sufficient.
- DON'T put both `-starter-web` and `-starter-webflux` on the classpath expecting reactive: MVC (web) wins auto-config. Pick one.

## DON'T — the cardinal WebFlux rule
- DON'T **ever block a Reactor event-loop thread**. No `.block()`, no blocking JDBC, no `Thread.sleep`, no blocking file I/O inside a reactive chain. It starves the whole server (few threads = whole app stalls).
- DO offload unavoidable blocking work: `Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())`.
- DON'T subscribe manually in controllers — return the `Mono`/`Flux`; the framework subscribes.

## Controllers
- DO annotate with `@RestController` (`@Controller` + `@ResponseBody`) for JSON APIs; `@Controller` for view rendering.
- DO use the same annotation model in both stacks: `@GetMapping`, `@PostMapping`, `@RequestBody`, `@PathVariable`, `@RequestParam`, `@ResponseStatus`.
- MVC returns `T` / `ResponseEntity<T>` (blocking). WebFlux returns `Mono<T>` / `Flux<T>` / `ResponseEntity<Mono<T>>`.
  ```java
  // MVC
  @RestController @RequestMapping("/users")
  class UserController {
    @GetMapping("/{id}") User get(@PathVariable long id) { return service.find(id); }
  }
  // WebFlux
  @RestController @RequestMapping("/users")
  class UserController {
    @GetMapping("/{id}") Mono<User> get(@PathVariable long id) { return service.find(id); }
    @GetMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    Flux<User> stream() { return service.streamAll(); }
  }
  ```
- DO consider functional endpoints (`RouterFunction`/`HandlerFunction`, `ServerResponse`) in WebFlux when you want routes as code instead of annotations. MVC has the equivalent `RouterFunction` (`WebMvc.fn`).

## Validation
- DO add `spring-boot-starter-validation` (Jakarta Bean Validation / Hibernate Validator). Not transitive on `-starter-web` since Boot 2.3+ — add it explicitly.
- DO annotate the body with `@Valid` (or `@Validated`) and put constraints (`@NotNull`, `@Size`, `@Email`) on the DTO. Boot 3+ uses `jakarta.validation.*`; Boot 2 uses `javax.validation.*`.
  ```java
  @PostMapping User create(@Valid @RequestBody CreateUser body) { ... }
  ```
- MVC failure → `MethodArgumentNotValidException`. WebFlux failure → `WebExchangeBindException`. Handle in advice (below).

## Error handling — @ControllerAdvice + ProblemDetail (RFC 9457)
- DO centralize with `@RestControllerAdvice` + `@ExceptionHandler`. Extend `ResponseEntityExceptionHandler` to reuse Spring's built-in handling.
- DO use **`ProblemDetail`** (Spring Framework 6.0+ / Boot 3.0+) for `application/problem+json` machine-readable errors.
  ```java
  @RestControllerAdvice
  class ApiExceptionHandler extends ResponseEntityExceptionHandler {
    @ExceptionHandler(NotFoundException.class)
    ProblemDetail handle(NotFoundException ex) {
      ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
      pd.setType(URI.create("https://example.org/problems/not-found"));
      return pd;
    }
  }
  ```
- DO enable auto Problem Details for framework exceptions: MVC `spring.mvc.problemdetails.enabled=true`; WebFlux `spring.webflux.problemdetails.enabled=true`. (Boot 3.0+.)
- Boot 2 / Framework 5: no `ProblemDetail` — return a custom error DTO in the advice.
- DON'T leak stack traces: `server.error.include-stacktrace=never` (default), keep `include-message`/`include-binding-errors` tight in prod.

## HTTP clients — calling other services
- DO use **`RestClient`** (Spring Framework 6.1+ / Boot 3.2+) for imperative/blocking calls in MVC apps — modern fluent replacement for `RestTemplate`. Inject the auto-configured `RestClient.Builder`.
  ```java
  RestClient client = builder.baseUrl("https://api.example.com").build();
  User u = client.get().uri("/users/{id}", id).retrieve().body(User.class);
  ```
- DO use **`WebClient`** (reactive, non-blocking) in WebFlux apps or wherever you need reactive/streaming calls. From `spring-webflux`; auto-configured `WebClient.Builder` available.
- DON'T use `RestClient` inside a Reactor chain (it's blocking) and DON'T `.block()` a `WebClient` call on an event-loop thread.
- `RestTemplate` still works but is maintenance-mode; prefer `RestClient` on 3.2+. Pre-3.2 fallback: `RestTemplate`.

## Quick decision checklist
1. Reactive datastore + streaming + everything non-blocking end-to-end? → WebFlux.
2. Otherwise → MVC. Need to scale blocked I/O? → MVC + virtual threads (Java 21+, Boot 3.2+).
3. Never `.block()` on a Reactor thread; offload to `boundedElastic`.
4. `@RestController` + `@Valid` + `@RestControllerAdvice`/`ProblemDetail`; add `-starter-validation` explicitly.
5. Client: `RestClient` (imperative) / `WebClient` (reactive).

## Sources
- Spring Boot reference — Servlet web: https://docs.spring.io/spring-boot/reference/web/servlet.html
- Spring Boot reference — Reactive web: https://docs.spring.io/spring-boot/reference/web/reactive.html
- Spring Boot reference — Calling REST services (RestClient/WebClient): https://docs.spring.io/spring-boot/reference/io/rest-client.html
- Spring Boot reference — Task execution & virtual threads: https://docs.spring.io/spring-boot/reference/features/spring-application.html
- Spring Boot system requirements: https://docs.spring.io/spring-boot/system-requirements.html
- Spring Boot project / version mappings: https://spring.io/projects/spring-boot , https://spring.io/projects/generations
- Spring Framework reference (Web MVC / WebFlux): https://docs.spring.io/spring-framework/reference/index.html
- Spring Boot GitHub: https://github.com/spring-projects/spring-boot

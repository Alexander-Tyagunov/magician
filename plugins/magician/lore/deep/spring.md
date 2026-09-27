# spring — deep dive

> On-demand companion to `lore/spring.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [DI, configuration & Boot conventions](#di-config-and-boot) · [Web: MVC (servlet) vs WebFlux (reactive)](#web-mvc-vs-webflux) · [Data access (JDBC, JPA, Data)](#data-access) · [Security & Actuator](#security-and-actuator) · [Testing](#testing)

## DI, configuration & Boot conventions <a id="di-config-and-boot"></a>

Framework-specifics only (Java-language lore lives in `lore/deep/java.md`). Verify version facts against Sources before asserting.

### Version baseline (verified)

| Boot | Spring Framework | Java | Namespace |
|------|------------------|------|-----------|
| 4.x (current, e.g. 4.1.0) | 7.0.x | 17–26, Servlet 6.1+ | `jakarta.*` |
| 3.x (prior, e.g. 3.5.x) | 6.2.x | 17–25, Servlet 5.0/6.0 | `jakarta.*` |
| 2.x (EOL OSS) | 5.x | 8+, Servlet 3.1–4 | `javax.*` |

- DON'T assume `javax.*`. Boot 3+ / Framework 6+ moved every EE API to `jakarta.*` (`jakarta.servlet`, `jakarta.persistence`, `jakarta.validation`, `jakarta.annotation`); `javax.*` is Boot 2.x only. Biggest 2→3 break.
- DON'T target Java <17 for Boot 3/4 (Boot 2 baseline is Java 8).

### Dependency injection

- DO use **constructor injection** for all mandatory deps. It gives immutability (`final` fields), non-null guarantees, and fully-initialized objects. Team-recommended.
- DON'T use field injection (`@Autowired` on a field). Untestable without reflection, hides deps, permits circular refs to slip through.

```java
@Service
public class OrderService {
  private final PaymentClient payments;      // final = mandatory
  OrderService(PaymentClient payments) {     // no @Autowired needed
    this.payments = payments;
  }
}
```

- DO omit `@Autowired` when a class has one constructor (auto-detected since Framework 4.3). Add it only to disambiguate multiple constructors.
- DO use setter/config-method injection **only** for optional deps with sane defaults, or reconfigurable ones (JMX MBeans). Large ctor arg counts are a code smell — split the class.

#### Circular dependencies

- DON'T create A↔B constructor cycles → `BeanCurrentlyInCreationException` at startup. Fix the design (extract a third collaborator); don't paper over it with `@Lazy` or setter injection.

### Stereotypes & config

- DO annotate beans by role: `@Component` (generic), `@Service` (business), `@Repository` (persistence — adds exception translation), `@Controller`/`@RestController` (web). All are meta-`@Component`, scanned by `@ComponentScan`.
- DO use `@Configuration` + `@Bean` factory methods for beans you don't own or must wire manually.
- DO set `@Configuration(proxyBeanMethods = false)` when `@Bean` methods never call each other — skips CGLIB proxying, faster startup. Keep default `true` only if one `@Bean` method calls another and needs the same singleton.

```java
@Configuration(proxyBeanMethods = false)
class ClientConfig {
  @Bean RestClient restClient(RestClient.Builder b) { return b.build(); }
}
```

### Scopes & lifecycle

- Scopes: `singleton` (default, one per container), `prototype` (new each request), plus web-aware `request` / `session` / `application` / `websocket`.
- DO keep singletons **stateless** and thread-safe; use `prototype` for stateful beans.
- DON'T rely on destruction callbacks for prototypes. Spring calls `@PostConstruct` but **not** `@PreDestroy` on prototypes — the client owns cleanup.
- DON'T inject a prototype directly into a singleton (it resolves once, frozen). Use `ObjectProvider<T>` (`getObject()` per call), `@Lookup`, or a scoped proxy.
- DO use `@PostConstruct` / `@PreDestroy` for init/teardown (from `jakarta.annotation` in Boot 3+; `javax.annotation` in Boot 2).

### @ConfigurationProperties vs @Value

- DO prefer `@ConfigurationProperties(prefix = "...")` for grouped/hierarchical config: type-safe, relaxed binding, JSR-303 validation, IDE metadata.
- DO use immutable **constructor binding** (records or `final` fields). `@ConstructorBinding` is only required when a class has multiple constructors (Boot 2.2+; behavior refined in 3.x).

```java
@ConfigurationProperties("app.mail")
record MailProps(String host, @DefaultValue("25") int port, boolean tls) {}
```

- DO register via `@ConfigurationPropertiesScan` (on the app class) or `@EnableConfigurationProperties(X.class)`. DON'T use `@Component` for constructor-bound types — it forces JavaBean/setter binding.
- DO validate with `@Validated` + `jakarta.validation` constraints (`@NotNull`, `@Min`); needs `spring-boot-starter-validation`, fails fast at startup.
- DON'T inject other beans into a `@ConfigurationProperties` type — it reads the `Environment` only.
- DON'T scatter many `@Value("${...}")` fields — reserve `@Value` for one-off values. Use canonical kebab-case in placeholders (`${app.item-price}`).
- Relaxed binding: `app.remote-address` == `app.remoteAddress` == `APP_REMOTEADDRESS` (env vars bind via UPPER_SNAKE).

### Profiles

- DO mark environment-specific beans with `@Profile("dev")` / `@Profile("!prod")`; activate via `spring.profiles.active` (property/env/`--arg`).
- DON'T use the old `spring.profiles` key inside a document — replaced by `spring.config.activate.on-profile` (Boot 2.4+). Group profiles with `spring.profiles.group.<name>` (Boot 2.4+), not `spring.profiles.include`.

### Config files & precedence

- DON'T put both `application.yml` and `application.properties` in one location — **`.properties` wins**. Pick one format.
- Profile-specific files (`application-<profile>.yml`) always override the plain file. With multiple active profiles, **last-listed wins**.
- Property source precedence (high→low): command-line args → `SPRING_APPLICATION_JSON` → JNDI → Java system props → OS env → config data (`application*.yml`) → `@PropertySource` → `SpringApplication` defaults. (Test sources sit above CLI args.)
- DO externalize secrets/K8s config via `spring.config.import=configtree:/etc/config/` (file-per-key) or `optional:file:./x.yml`. Imported values override the importing file.
- DO use `spring.config.additional-location` to add search paths; `spring.config.location` **replaces** defaults (rarely what you want).

### Auto-configuration & starters

- `@SpringBootApplication` = `@EnableAutoConfiguration` + `@ComponentScan` + `@SpringBootConfiguration`. Put it on the top package; scan runs from there down.
- DO depend on official starters (`spring-boot-starter-web`, `-data-jpa`, `-security`, `-validation`, `-actuator`); the jar triggers matching auto-config via `@Conditional*` checks. DON'T name a third-party starter `spring-boot-starter-*` (reserved) — use `<name>-spring-boot-starter`.
- DO register your own auto-config classes in `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` (one FQN/line), annotated `@AutoConfiguration`. DON'T use `META-INF/spring.factories` — deprecated for this in Boot 2.7.
- DO gate custom beans with `@ConditionalOnMissingBean` / `@ConditionalOnClass` / `@ConditionalOnProperty` so users can override.
- DO disable auto-config via `@SpringBootApplication(exclude = X.class)` or `spring.autoconfigure.exclude`. Diagnose with `--debug` or the Actuator `conditions` endpoint.

### Sources

- Spring Boot reference (4.1): https://docs.spring.io/spring-boot/index.html
- System requirements (4.1): https://docs.spring.io/spring-boot/system-requirements.html
- System requirements (3.5): https://docs.spring.io/spring-boot/3.5/system-requirements.html
- Externalized configuration: https://docs.spring.io/spring-boot/reference/features/external-config.html
- Auto-configuration: https://docs.spring.io/spring-boot/reference/using/auto-configuration.html
- Spring Framework — DI / collaborators: https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html
- Spring Framework — bean scopes: https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html
- Spring Boot project / version mappings: https://spring.io/projects/spring-boot

## Web: MVC (servlet) vs WebFlux (reactive) <a id="web-mvc-vs-webflux"></a>

Framework-specific lore. Java-language rules live in `lore/deep/java.md`.

Two web stacks, never mix in one request path:
- **Spring MVC** — servlet, blocking, thread-per-request. Default embedded server **Tomcat**. Starter `spring-boot-starter-web`.
- **Spring WebFlux** — reactive, non-blocking, event-loop. Default embedded server **Reactor Netty**. Starter `spring-boot-starter-webflux`. Built on **Project Reactor** (`Mono`/`Flux`), since Spring Framework 5.0.

### Version baselines (verify against current docs before asserting)
- **Boot 4.x** (current GA 4.1.0): Java 17+ (tested to Java 26), Spring Framework 7.0.8+, `jakarta.*`.
- **Boot 3.x**: Java 17+, Spring Framework 6, `jakarta.*`.
- **Boot 2.x** (OSS EOL): Java 8+, Spring Framework 5, `javax.*`. Migrating off 2.x = `javax.*` → `jakarta.*` package rename.

### DO — choosing the stack
- DO default to **MVC** for typical CRUD/REST/DB apps. Simpler stack traces, blocking JDBC, imperative code.
- DO pick **WebFlux** only when you need non-blocking end-to-end: high-concurrency I/O fan-out, streaming (SSE/`Flux`), or a reactive datastore (R2DBC, reactive Mongo). Reactive only pays off if the *whole* chain is reactive.
- DO use **virtual threads** (Boot 3.2+, `spring.threads.virtual.enabled=true`, **Java 21+**, Java 24+ recommended) to get high-concurrency scaling on the **MVC** stack without rewriting to Reactor. This is the modern answer for "MVC but scale to many blocked I/O calls."
  ```properties
  spring.threads.virtual.enabled=true
  ```
- DON'T reach for WebFlux just for throughput if the app blocks on JDBC — virtual-thread MVC is simpler and usually sufficient.
- DON'T put both `-starter-web` and `-starter-webflux` on the classpath expecting reactive: MVC (web) wins auto-config. Pick one.

### DON'T — the cardinal WebFlux rule
- DON'T **ever block a Reactor event-loop thread**. No `.block()`, no blocking JDBC, no `Thread.sleep`, no blocking file I/O inside a reactive chain. It starves the whole server (few threads = whole app stalls).
- DO offload unavoidable blocking work: `Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())`.
- DON'T subscribe manually in controllers — return the `Mono`/`Flux`; the framework subscribes.

### Controllers
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

### Validation
- DO add `spring-boot-starter-validation` (Jakarta Bean Validation / Hibernate Validator). Not transitive on `-starter-web` since Boot 2.3+ — add it explicitly.
- DO annotate the body with `@Valid` (or `@Validated`) and put constraints (`@NotNull`, `@Size`, `@Email`) on the DTO. Boot 3+ uses `jakarta.validation.*`; Boot 2 uses `javax.validation.*`.
  ```java
  @PostMapping User create(@Valid @RequestBody CreateUser body) { ... }
  ```
- MVC failure → `MethodArgumentNotValidException`. WebFlux failure → `WebExchangeBindException`. Handle in advice (below).

### Error handling — @ControllerAdvice + ProblemDetail (RFC 9457)
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

### HTTP clients — calling other services
- DO use **`RestClient`** (Spring Framework 6.1+ / Boot 3.2+) for imperative/blocking calls in MVC apps — modern fluent replacement for `RestTemplate`. Inject the auto-configured `RestClient.Builder`.
  ```java
  RestClient client = builder.baseUrl("https://api.example.com").build();
  User u = client.get().uri("/users/{id}", id).retrieve().body(User.class);
  ```
- DO use **`WebClient`** (reactive, non-blocking) in WebFlux apps or wherever you need reactive/streaming calls. From `spring-webflux`; auto-configured `WebClient.Builder` available.
- DON'T use `RestClient` inside a Reactor chain (it's blocking) and DON'T `.block()` a `WebClient` call on an event-loop thread.
- `RestTemplate` still works but is maintenance-mode; prefer `RestClient` on 3.2+. Pre-3.2 fallback: `RestTemplate`.

### Quick decision checklist
1. Reactive datastore + streaming + everything non-blocking end-to-end? → WebFlux.
2. Otherwise → MVC. Need to scale blocked I/O? → MVC + virtual threads (Java 21+, Boot 3.2+).
3. Never `.block()` on a Reactor thread; offload to `boundedElastic`.
4. `@RestController` + `@Valid` + `@RestControllerAdvice`/`ProblemDetail`; add `-starter-validation` explicitly.
5. Client: `RestClient` (imperative) / `WebClient` (reactive).

### Sources
- Spring Boot reference — Servlet web: https://docs.spring.io/spring-boot/reference/web/servlet.html
- Spring Boot reference — Reactive web: https://docs.spring.io/spring-boot/reference/web/reactive.html
- Spring Boot reference — Calling REST services (RestClient/WebClient): https://docs.spring.io/spring-boot/reference/io/rest-client.html
- Spring Boot reference — Task execution & virtual threads: https://docs.spring.io/spring-boot/reference/features/spring-application.html
- Spring Boot system requirements: https://docs.spring.io/spring-boot/system-requirements.html
- Spring Boot project / version mappings: https://spring.io/projects/spring-boot , https://spring.io/projects/generations
- Spring Framework reference (Web MVC / WebFlux): https://docs.spring.io/spring-framework/reference/index.html
- Spring Boot GitHub: https://github.com/spring-projects/spring-boot

## Data access (JDBC, JPA, Data) <a id="data-access"></a>

Framework-specifics only. Complements `lore/jdbc.md` and `lore/orm.md`; assumes Java lore in `lore/deep/java.md`.

Version map (tie to Java baseline):
- **Spring Boot 3.x** → Spring Framework 6.x, **Java 17+**, Jakarta EE (`jakarta.persistence.*`, `jakarta.transaction.*`). Boot **3.2+** = Framework **6.1** (adds `JdbcClient`). Current line: Boot 4.x → Framework 7.x, Java 17+.
- **Spring Boot 2.x** → Framework 5.x, **Java 8+**, `javax.persistence.*`. No `JdbcClient`; use `JdbcTemplate`/`NamedParameterJdbcTemplate`.

### `@Transactional` semantics

DO
- Put `@Transactional` on the **service** layer, not repositories/controllers. Repos already run in their own tx.
- Use `@Transactional(readOnly = true)` on all read methods — enables Hibernate flush-mode `MANUAL` and driver read-only hints.
- Keep `PROPAGATION_REQUIRED` (default). Use `Propagation.REQUIRES_NEW` only for a truly independent unit (e.g. audit log that must commit even if caller rolls back).
- Remember: rollback fires on `RuntimeException`/`Error` only; **checked exceptions do NOT roll back** by default. Add `@Transactional(rollbackFor = Exception.class)` when you throw checked and want rollback.
- Boot autoconfigures the right `PlatformTransactionManager` (`JpaTransactionManager` with JPA, `DataSourceTransactionManager`/`JdbcTransactionManager` for plain JDBC). Don't declare one manually unless multi-datasource.

DON'T
- **Self-invocation trap:** calling a `@Transactional` method from another method of the *same bean* bypasses the proxy — no transaction/new propagation applies. Fix: move the method to another bean, self-inject the proxy, or switch to AspectJ weaving mode.
- Don't annotate `private` methods — never advised. (Since 6.0, `protected`/package methods work only with **class-based (CGLIB) proxies**; interface proxies still need `public`.)
- Don't expect `isolation`/`timeout`/`readOnly` to apply under `NESTED`/`SUPPORTS`/`MANDATORY` etc. — they only take effect for `REQUIRED`/`REQUIRES_NEW`.
- Don't do slow I/O (HTTP, external calls) inside a tx — holds the DB connection.

```java
@Service
public class OrderService {
  @Transactional(readOnly = true)
  public Order find(Long id) { ... }

  @Transactional(rollbackFor = PaymentException.class)
  public void place(Order o) throws PaymentException { ... }
}
```
Global switch (Framework 6.2+) for consistent rollback incl. checked: `@EnableTransactionManagement(rollbackOn = ALL_EXCEPTIONS)`.

### Spring Data JPA repositories

DO
- Extend `JpaRepository<T, ID>` (adds `CrudRepository` + `PagingAndSortingRepository` + flush/batch). Prefer derived queries for simple cases: `findByEmailAndActiveTrue(...)`.
- Use `@Query` (JPQL) for anything non-trivial; it takes precedence over `@NamedQuery`. Add `@Param` for named binds (omit-able on Framework 7 / Boot 4 if compiled with `-parameters`).
- Use `@Modifying` on bulk update/delete `@Query`; set `clearAutomatically = true` (and consider `flushAutomatically`) so the persistence context doesn't serve stale entities after a bulk write.
- Return `Optional<T>` for single lookups.

DON'T
- Don't hand-write CRUD/boilerplate DAOs when a derived method suffices.
- Don't rely on derived `deleteByX(...)` for volume — it **loads then deletes one-by-one** (fires lifecycle callbacks). Use `@Modifying @Query("delete from ...")` for a single bulk statement (skips callbacks).
- Don't put function calls in `Sort.by("LENGTH(name)")` — throws; use `JpaSort.unsafe(...)`.

### N+1 avoidance

DO
- Default associations to **`FetchType.LAZY`** (`@OneToMany` is lazy already; make `@ManyToOne`/`@OneToOne` explicit `LAZY`).
- Fetch the graph you need in one query: `@Query("select o from Order o join fetch o.items where ...")`, or **`@EntityGraph(attributePaths = {"items"})`** on the repo method (declarative, works with derived + paged methods).
- Detect N+1 early: log SQL and enable `spring.jpa.properties.hibernate.generate_statistics=true` in tests.

DON'T
- Don't set `FetchType.EAGER` to "fix" N+1 — it just moves the problem and breaks pagination.
- Don't `join fetch` a collection **and** paginate in the same query — Hibernate pages in memory (warns/OOM). Paginate on the root, fetch collections via `@EntityGraph` or a second query (`@BatchSize` / `hibernate.default_batch_fetch_size`).

```java
public interface OrderRepo extends JpaRepository<Order, Long> {
  @EntityGraph(attributePaths = "items")
  List<Order> findByStatus(Status s);
}
```

### Projections

DO
- Use **interface projections** (closed) to select only needed columns — Spring generates a narrow query:
  ```java
  interface NameOnly { String getFirstname(); String getLastname(); }
  List<NameOnly> findByActiveTrue();
  ```
- Use **DTO/record class projections** via constructor expression when shaping: `@Query("select new com.x.NameDto(u.firstname, u.lastname) from User u")`, or a record as the return type.

DON'T
- Don't fetch full entities just to read two fields — wastes SQL and hydrates the persistence context.
- Avoid **open** projections (SpEL `@Value("#{...}")` getters): they force full-entity fetch, defeating the point.

### Pagination

DO
- Accept `Pageable` (`PageRequest.of(page, size, Sort.by(...))`). Return **`Page<T>`** when you need total count, **`Slice<T>`** when you only need "has next" (skips the count query). Use `Window<T>` + keyset (`ScrollPosition.keyset()`) for deep/large scans.
- For native paged `@Query`, supply an explicit `countQuery` (or add JSqlParser for auto-derivation).

DON'T
- Don't return `Page` on hot paths that don't display totals — the extra `count(*)` is wasted.
- Don't offset-paginate huge tables — deep offsets are O(n); prefer keyset scrolling.

### JdbcTemplate / JdbcClient (Boot 3.2+)

DO
- **New code on Boot 3.2+ / Framework 6.1+:** prefer **`JdbcClient`** — unified fluent facade over positional + named params. Boot autoconfigures the bean (`JdbcClientAutoConfiguration`, needs a `NamedParameterJdbcTemplate`); just inject it.
  ```java
  Optional<Actor> a = jdbcClient
      .sql("select * from actor where id = :id")
      .param("id", id)
      .query(Actor.class).optional();     // .single() / .list() / .update()
  ```
- On Boot 2.x (or existing code): `NamedParameterJdbcTemplate` (named `:params`) or `JdbcTemplate` (positional `?`). Both are autoconfigured and thread-safe.
- Use plain JDBC / `JdbcClient` when you want explicit SQL, complex reporting joins, bulk writes, or to avoid ORM overhead.

DON'T
- Don't reach for `JdbcTemplate.queryForObject` when it can return 0 rows — throws `EmptyResultDataAccessException`; use `JdbcClient...optional()`.
- Don't use `JdbcClient` for batch inserts / stored procs — still need `SimpleJdbcInsert`/`SimpleJdbcCall`/`JdbcTemplate.batchUpdate`.

### Spring Data JPA vs plain JDBC/jOOQ

- **Spring Data JPA** — domain-centric CRUD, entity graphs, derived queries, dirty-checking. Best for aggregate-oriented models.
- **JdbcClient / Spring Data JDBC** — no lazy loading / no dirty tracking; predictable SQL, lighter. Good for simple tables, CQRS read side, high-throughput.
- **jOOQ** — type-safe SQL DSL, compile-checked against schema. Best for complex/analytical SQL where JPQL is awkward. Combine: JPA for writes, jOOQ/`JdbcClient` for reporting reads.

### Sources
- https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html
- https://docs.spring.io/spring-framework/reference/data-access/jdbc/core.html
- https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html
- https://docs.spring.io/spring-boot/3.5/reference/data/sql.html
- https://docs.spring.io/spring-boot/system-requirements.html
- https://docs.spring.io/spring-boot/index.html

## Security & Actuator <a id="security-and-actuator"></a>

Framework-specific lore. Java-language rules live in `lore/deep/java.md`. Verify version facts against current docs before asserting.

### Version baseline (pick the right era)

- **Spring Boot 3.x** (3.0 Nov 2022 → 3.5) requires **Java 17+**, Spring Framework 6.x, **Spring Security 6.x**, `jakarta.*` namespace. Boot 4.x (4.0 Nov 2025, 4.1 Jun 2026) also Java 17+, Security 7.x.
- **Spring Boot 2.x** (max 2.7, OSS EOL Jun 2023; commercial to 2029) is Java 8+, Spring Framework 5.x, **Spring Security 5.x**, `javax.*`.
- DO default to Boot 3.x lambda-DSL patterns. DON'T write `javax.*` imports for 3.x/4.x — it's `jakarta.*`.

### SecurityFilterChain (config)

- DO configure security by publishing a `SecurityFilterChain` **bean** from a `@Configuration @EnableWebSecurity` class.
- DON'T extend `WebSecurityConfigurerAdapter`. Deprecated in **Security 5.7**, **removed in 6.0**. It does not exist in Boot 3.x.
- DO use the lambda DSL (`Customizer`), not the old `.and()` chaining.
- DO use `authorizeHttpRequests` (Security 6+). `authorizeRequests` is deprecated/removed — that's the 5.x form.

```java
@Configuration
@EnableWebSecurity
class SecurityConfig {
  @Bean
  SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
      .authorizeHttpRequests(auth -> auth
        .requestMatchers("/public/**").permitAll()
        .requestMatchers("/admin/**").hasRole("ADMIN")
        .anyRequest().authenticated())
      .httpBasic(Customizer.withDefaults());
    return http.build();
  }
}
```

- DO scope multiple chains with `@Order` + `http.securityMatcher(...)`. `requestMatchers(...)` scopes rules *inside* a chain.
- DON'T leave requests unmatched — provide one chain with no `securityMatcher` as a catch-all, or they're unprotected.

### Password encoding

- DO expose a `PasswordEncoder` bean via `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (default `{bcrypt}`, strength 10). Storage format is `{id}hash`, enabling multi-algorithm match + upgrade.
- DON'T use `NoOpPasswordEncoder` (plaintext) or `User.withDefaultPasswordEncoder()` (demo-only — hash lands in memory/source) in production. Both deprecated.
- DO tune bcrypt strength so a hash takes ~1s (`new BCryptPasswordEncoder(strength)`); or use argon2/pbkdf2/scrypt encoders.

### Method security

- DO annotate a `@Configuration` with `@EnableMethodSecurity` (Security 5.6+, standard in 6.x). Enables `@PreAuthorize`/`@PostAuthorize`/`@PreFilter`/`@PostFilter` by default.
- DON'T use `@EnableGlobalMethodSecurity` — deprecated (that's the pre-5.6 form).
- DO opt in explicitly for legacy annotations: `@EnableMethodSecurity(securedEnabled=true)` for `@Secured`, `jsr250Enabled=true` for `@RolesAllowed`. Prefer `@PreAuthorize` (SpEL, more expressive).
- DON'T assume unannotated methods are protected — method security only guards annotated methods. Keep an `HttpSecurity` catch-all.

```java
@PreAuthorize("hasRole('ADMIN')")
Account read(Long id) { ... }
@PostAuthorize("returnObject.owner == authentication.name")
Account mine(Long id) { ... }
```

### CSRF

- CSRF is **ON by default** (unsafe methods) in both 5.x and 6.x. Security 6 adds deferred token loading + BREACH protection (`XorCsrfTokenRequestAttributeHandler`).
- DO `http.csrf(csrf -> csrf.disable())` **only** for stateless, non-browser APIs (JWT bearer in `Authorization` header — not CSRF-vulnerable). Pair with `sessionManagement(s -> s.sessionCreationPolicy(STATELESS))`.
- DO keep CSRF for cookie/session browser apps. For SPAs use `csrf.spa()` (Security 6.x) or `CookieCsrfTokenRepository.withHttpOnlyFalse()`.
- DON'T blanket-disable CSRF on a hybrid app that also serves browser sessions.

### CORS

- DO enable via `http.cors(Customizer.withDefaults())` and publish a `UrlBasedCorsConfigurationSource` bean; Spring Security wires it into the filter chain (also feeds MVC).
- DON'T rely on `@CrossOrigin`/MVC CORS alone when Security is present — Security's filter runs first. Set explicit `setAllowedOrigins`/`setAllowedMethods`; avoid `*` with credentials.

### OAuth2 resource server / JWT

- DO add `spring-boot-starter-oauth2-resource-server` (pulls `oauth2-resource-server` + `oauth2-jose`).
- DO set one of:
```yaml
spring.security.oauth2.resourceserver.jwt.issuer-uri: https://idp.example.com   # auto-discovers JWKS + validates iss
# or, to avoid startup dependency:
spring.security.oauth2.resourceserver.jwt.jwk-set-uri: https://idp.example.com/.well-known/jwks.json
```
- DO enable `.oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))`. Scopes map to `SCOPE_` authorities; check via `hasAuthority("SCOPE_message:read")` (6.x). `sub` becomes the principal name.
- DO set `...jwt.audiences` to validate the `aud` claim when the IdP is multi-tenant.

### Actuator

- Default exposure over HTTP/JMX is **only `health`**. Base path `/actuator`. `shutdown` endpoint disabled by default.
- DO expose deliberately and minimally:
```yaml
management.endpoints.web.exposure.include: health,info,metrics,prometheus
```
- DON'T set `include: "*"` on a public/internet-facing app. `env`, `beans`, `configprops`, `heapdump`, `threaddump`, `loggers`, `httpexchanges` leak internals. `exclude` wins over `include`.
- DO secure endpoints with a dedicated chain (Boot backs off its auto-config once *any* `SecurityFilterChain` exists — so you must cover both actuator and app):
```java
@Bean
SecurityFilterChain actuator(HttpSecurity http) throws Exception {
  http.securityMatcher(EndpointRequest.toAnyEndpoint())
      .authorizeHttpRequests(r -> r.anyRequest().hasRole("ENDPOINT_ADMIN"))
      .httpBasic(Customizer.withDefaults());
  return http.build();
}
```
- DO gate detail leakage: `management.endpoint.health.show-details: when-authorized` (default `never`; avoid `always` on secured apps).
- DO use access control to remove endpoints entirely: `management.endpoints.access.default: none` then per-endpoint `management.endpoint.<id>.access: read-only`.
- DO run actuator on a separate port when feasible: `management.server.port`.

### Health, probes & metrics

- DO enable K8s probes: `management.endpoint.health.probes.enabled: true` → `/actuator/health/liveness` + `/readiness`. Use `add-additional-paths=true` for `/livez`,`/readyz` on the main port.
- DON'T put external-system checks in the **liveness** probe — a downstream outage would trigger pod restarts (cascading failure). Readiness may include external checks via a health group.
- DO implement custom checks with a `HealthIndicator` bean (bean `FooHealthIndicator` → id `foo`).
- Metrics are **Micrometer**-backed. For Prometheus scraping add `micrometer-registry-prometheus`, then expose the `prometheus` endpoint (not exposed by default). `metrics` endpoint is for diagnostics, not scraping.

### Sources

- https://docs.spring.io/spring-security/reference/servlet/configuration/java.html
- https://docs.spring.io/spring-security/reference/servlet/authorization/method-security.html
- https://docs.spring.io/spring-security/reference/features/authentication/password-storage.html
- https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html
- https://docs.spring.io/spring-security/reference/6.5/servlet/integrations/cors.html
- https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html
- https://docs.spring.io/spring-boot/reference/actuator/endpoints.html
- https://spring.io/projects/spring-boot
- https://github.com/spring-projects/spring-boot

## Testing <a id="testing"></a>

Framework-specifics for Spring Boot tests. Java-language testing lore lives in `lore/deep/java.md`.

Version map (verify against the project's `spring-boot.version`):
- **Boot 3.x** → Java 17+, Jakarta EE, `jakarta.*` imports, JUnit 5, Spring Framework 6.x.
- **Boot 2.x** → Java 8+, `javax.*` imports, JUnit 5 (JUnit 4 needs `@RunWith(SpringRunner.class)`), Spring Framework 5.x.
- `@MockitoBean`/`@MockitoSpyBean`, `DynamicPropertyRegistrar` → **Spring Framework 6.2 / Boot 3.4+**.
- `@ServiceConnection` → **Boot 3.1+**. `@ImportTestcontainers` → **Boot 3.1+**.

---

### Choose the right test — DO

- **DO** default to a plain unit test (no Spring context) for pure logic. Construct the class, pass mocks (Mockito `@Mock`/`@ExtendWith(MockitoExtension.class)`). No `@SpringBootTest`. Fastest.
- **DO** use a **slice** when you need a narrow part of the container wired. One slice per test:
  - `@WebMvcTest(FooController.class)` — MVC web layer only. Autoconfigures `MockMvc` (and `MockMvcTester` if AssertJ present). Does **not** load `@Service`/`@Repository`/`@Component` — provide collaborators with `@MockitoBean`.
  - `@WebFluxTest(FooController.class)` — reactive web layer. Autoconfigures `WebTestClient`. Controllers only.
  - `@DataJpaTest` — JPA repos + entities. Transactional, **rolls back each test**, replaces the `DataSource` with an embedded in-memory DB. Injects `TestEntityManager`.
  - `@JdbcTest`, `@DataMongoTest`, `@DataRedisTest`, `@JsonTest`, `@RestClientTest` — analogous narrow slices.
- **DO** use `@SpringBootTest` only for full-context / end-to-end integration tests. It builds the context via `SpringApplication`, searching upward for `@SpringBootApplication`/`@SpringBootConfiguration`.

### Choose the right test — DON'T

- **DON'T** reach for `@SpringBootTest` to test one controller or one repository — a slice is far faster and the context cache is shared across identically-configured slices.
- **DON'T** stack slice annotations (`@WebMvcTest` + `@DataJpaTest`). Unsupported. Pick one `@…Test` and add the others' `@AutoConfigure…` annotations by hand, or use `@SpringBootTest` + specific `@AutoConfigure…`.
- **DON'T** expect `@Component`/`@ConfigurationProperties` beans inside a slice. Use `@MockitoBean`, `@Import(...)`, or `@EnableConfigurationProperties`. `@Bean`-defined beans are not filtered by slices — import them explicitly.

---

### webEnvironment — DO / DON'T

`@SpringBootTest(webEnvironment = ...)`:
- `MOCK` (**default**) — mock servlet env, **no** embedded server. Pair with `@AutoConfigureMockMvc` / `@AutoConfigureWebTestClient`.
- `RANDOM_PORT` — real embedded server on a random port; inject with `@LocalServerPort`.
- `DEFINED_PORT` — real server on the configured/default port.
- `NONE` — context, no web env.

- **DON'T** rely on `@Transactional` rollback with `RANDOM_PORT`/`DEFINED_PORT` — the server runs on a separate thread; server-side changes are **not** rolled back.
- **DON'T** test servlet-container concerns (custom error pages, filters at container level) with `MockMvc` — it stops at the Spring MVC layer; use a running server.

---

### Web test clients — DO

```java
@WebMvcTest(UserController.class)
class UserControllerTests {
    @Autowired MockMvc mvc;              // Hamcrest; or MockMvcTester (AssertJ)
    @MockitoBean UserService service;   // Boot 3.4+ (Spring Framework annotation)

    @Test void ok() throws Exception {
        given(service.name()).willReturn("x");
        mvc.perform(get("/name")).andExpect(status().isOk());
    }
}
```

- **DO** use `MockMvcTester` (AssertJ, `assertThat(mvc.get()...)`) for new MVC tests when available.
- **DO** use `WebTestClient` for WebFlux (`@WebFluxTest`) and for `RANDOM_PORT` end-to-end (`@AutoConfigureWebTestClient`). Requires `spring-webflux` on the classpath.
- **DO** use `@WithMockUser`/`@WithUserDetails` (from `spring-security-test`) with `@WebMvcTest` when Security is present — it scans `SecurityFilterChain`/`WebSecurityConfigurer` beans. Don't just disable security.

---

### Mocking beans — DO / DON'T (version-critical)

- **DO (Boot 3.4+ / Spring Framework 6.2+)** use `@MockitoBean` / `@MockitoSpyBean` from `org.springframework.test.context.bean.override.mockito`. This is the current API; `@MockBean`/`@SpyBean` are **deprecated in 3.4** and **removed in Boot 4.x**.
- **DO (Boot ≤ 3.3 / 2.x)** use `@MockBean` / `@SpyBean` from `org.springframework.boot.test.mock.mockito` — the only option there.
- **DON'T** confuse with Mockito's `@Mock`: `@Mock` makes a bare mock (unit tests, no context); `@MockitoBean` replaces a bean **in the Spring context**.
- **DON'T** use `@TestConfiguration` + `@Bean` when a single `@MockitoBean` field suffices.

---

### Testcontainers — DO

Module: **`spring-boot-testcontainers`** (test scope) + the relevant `org.testcontainers` module.

**Boot 3.1+ — prefer `@ServiceConnection`** (`org.springframework.boot.testcontainers.service.connection`). Auto-wires `ConnectionDetails` beans; overrides `spring.datasource.*`/`spring.data.*` connection props automatically — no manual property mapping.

```java
@SpringBootTest
@Testcontainers
class OrderRepoIT {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16");
}
```

- **DO** make `@Container` fields **`static`** so one container serves the whole class.
- **DO** use `@ServiceConnection(name = "redis")` on a `GenericContainer` `@Bean` (image name can't be inferred there); use `type = ...` to narrow which `ConnectionDetails` are created.
- **DO** reuse a container across the suite via `@ImportTestcontainers` (Boot 3.1+) or a shared `@TestConfiguration`, so the cached `ApplicationContext` outlives per-class container lifecycle.

### Testcontainers — DON'T

- **DON'T** expect `@ServiceConnection` in Boot **2.x / ≤3.0** — it doesn't exist. Fall back to `@DynamicPropertySource` (Spring Framework 5.2.5+):

```java
@DynamicPropertySource
static void props(DynamicPropertyRegistry r) {
    r.add("spring.datasource.url", db::getJdbcUrl);
    r.add("spring.datasource.username", db::getUsername);
    r.add("spring.datasource.password", db::getPassword);
}
```
  (Boot 3.4+ also offers a bean-based `DynamicPropertyRegistrar`.)
- **DON'T** hand-map connection props with `@DynamicPropertySource` when `@ServiceConnection` covers the container (Postgres, MySQL, Mongo, Redis, Kafka, RabbitMQ, Neo4j, Cassandra, etc.).

---

### Speed & context caching — DO / DON'T

- **DO** keep test configuration identical across classes so Spring **reuses the cached context**. Each distinct config/property set = a new context = slower.
- **DON'T** sprinkle `@DirtiesContext` — it evicts the cache and forces rebuilds. Only use it when a test truly mutates shared state (e.g. `spring.jmx.enabled=true`).
- **DON'T** add `@MockitoBean`/`properties`/`@TestPropertySource` variations you don't need — each variation fragments the context cache.

### Sources

- Spring Boot reference — Testing: https://docs.spring.io/spring-boot/reference/testing/spring-boot-applications.html
- Spring Boot reference — Testcontainers: https://docs.spring.io/spring-boot/reference/testing/testcontainers.html
- Spring Boot how-to — Testing: https://docs.spring.io/spring-boot/how-to/testing.html
- Spring Boot 3.5 reference — Testing: https://docs.spring.io/spring-boot/3.5/reference/testing/spring-boot-applications.html
- `@DataJpaTest` Javadoc: https://docs.spring.io/spring-boot/3.5/api/java/org/springframework/boot/test/autoconfigure/orm/jpa/DataJpaTest.html
- `@WebFluxTest` Javadoc: https://docs.spring.io/spring-boot/3.5/api/java/org/springframework/boot/test/autoconfigure/web/reactive/WebFluxTest.html
- Spring Framework reference: https://docs.spring.io/spring-framework/reference/testing.html
- Spring Boot project: https://github.com/spring-projects/spring-boot

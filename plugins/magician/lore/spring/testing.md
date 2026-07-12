# spring — Testing

Framework-specifics for Spring Boot tests. Java-language testing lore lives in `lore/java/*`.

Version map (verify against the project's `spring-boot.version`):
- **Boot 3.x** → Java 17+, Jakarta EE, `jakarta.*` imports, JUnit 5, Spring Framework 6.x.
- **Boot 2.x** → Java 8+, `javax.*` imports, JUnit 5 (JUnit 4 needs `@RunWith(SpringRunner.class)`), Spring Framework 5.x.
- `@MockitoBean`/`@MockitoSpyBean`, `DynamicPropertyRegistrar` → **Spring Framework 6.2 / Boot 3.4+**.
- `@ServiceConnection` → **Boot 3.1+**. `@ImportTestcontainers` → **Boot 3.1+**.

---

## Choose the right test — DO

- **DO** default to a plain unit test (no Spring context) for pure logic. Construct the class, pass mocks (Mockito `@Mock`/`@ExtendWith(MockitoExtension.class)`). No `@SpringBootTest`. Fastest.
- **DO** use a **slice** when you need a narrow part of the container wired. One slice per test:
  - `@WebMvcTest(FooController.class)` — MVC web layer only. Autoconfigures `MockMvc` (and `MockMvcTester` if AssertJ present). Does **not** load `@Service`/`@Repository`/`@Component` — provide collaborators with `@MockitoBean`.
  - `@WebFluxTest(FooController.class)` — reactive web layer. Autoconfigures `WebTestClient`. Controllers only.
  - `@DataJpaTest` — JPA repos + entities. Transactional, **rolls back each test**, replaces the `DataSource` with an embedded in-memory DB. Injects `TestEntityManager`.
  - `@JdbcTest`, `@DataMongoTest`, `@DataRedisTest`, `@JsonTest`, `@RestClientTest` — analogous narrow slices.
- **DO** use `@SpringBootTest` only for full-context / end-to-end integration tests. It builds the context via `SpringApplication`, searching upward for `@SpringBootApplication`/`@SpringBootConfiguration`.

## Choose the right test — DON'T

- **DON'T** reach for `@SpringBootTest` to test one controller or one repository — a slice is far faster and the context cache is shared across identically-configured slices.
- **DON'T** stack slice annotations (`@WebMvcTest` + `@DataJpaTest`). Unsupported. Pick one `@…Test` and add the others' `@AutoConfigure…` annotations by hand, or use `@SpringBootTest` + specific `@AutoConfigure…`.
- **DON'T** expect `@Component`/`@ConfigurationProperties` beans inside a slice. Use `@MockitoBean`, `@Import(...)`, or `@EnableConfigurationProperties`. `@Bean`-defined beans are not filtered by slices — import them explicitly.

---

## webEnvironment — DO / DON'T

`@SpringBootTest(webEnvironment = ...)`:
- `MOCK` (**default**) — mock servlet env, **no** embedded server. Pair with `@AutoConfigureMockMvc` / `@AutoConfigureWebTestClient`.
- `RANDOM_PORT` — real embedded server on a random port; inject with `@LocalServerPort`.
- `DEFINED_PORT` — real server on the configured/default port.
- `NONE` — context, no web env.

- **DON'T** rely on `@Transactional` rollback with `RANDOM_PORT`/`DEFINED_PORT` — the server runs on a separate thread; server-side changes are **not** rolled back.
- **DON'T** test servlet-container concerns (custom error pages, filters at container level) with `MockMvc` — it stops at the Spring MVC layer; use a running server.

---

## Web test clients — DO

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

## Mocking beans — DO / DON'T (version-critical)

- **DO (Boot 3.4+ / Spring Framework 6.2+)** use `@MockitoBean` / `@MockitoSpyBean` from `org.springframework.test.context.bean.override.mockito`. This is the current API; `@MockBean`/`@SpyBean` are **deprecated in 3.4** and **removed in Boot 4.x**.
- **DO (Boot ≤ 3.3 / 2.x)** use `@MockBean` / `@SpyBean` from `org.springframework.boot.test.mock.mockito` — the only option there.
- **DON'T** confuse with Mockito's `@Mock`: `@Mock` makes a bare mock (unit tests, no context); `@MockitoBean` replaces a bean **in the Spring context**.
- **DON'T** use `@TestConfiguration` + `@Bean` when a single `@MockitoBean` field suffices.

---

## Testcontainers — DO

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

## Testcontainers — DON'T

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

## Speed & context caching — DO / DON'T

- **DO** keep test configuration identical across classes so Spring **reuses the cached context**. Each distinct config/property set = a new context = slower.
- **DON'T** sprinkle `@DirtiesContext` — it evicts the cache and forces rebuilds. Only use it when a test truly mutates shared state (e.g. `spring.jmx.enabled=true`).
- **DON'T** add `@MockitoBean`/`properties`/`@TestPropertySource` variations you don't need — each variation fragments the context cache.

## Sources

- Spring Boot reference — Testing: https://docs.spring.io/spring-boot/reference/testing/spring-boot-applications.html
- Spring Boot reference — Testcontainers: https://docs.spring.io/spring-boot/reference/testing/testcontainers.html
- Spring Boot how-to — Testing: https://docs.spring.io/spring-boot/how-to/testing.html
- Spring Boot 3.5 reference — Testing: https://docs.spring.io/spring-boot/3.5/reference/testing/spring-boot-applications.html
- `@DataJpaTest` Javadoc: https://docs.spring.io/spring-boot/3.5/api/java/org/springframework/boot/test/autoconfigure/orm/jpa/DataJpaTest.html
- `@WebFluxTest` Javadoc: https://docs.spring.io/spring-boot/3.5/api/java/org/springframework/boot/test/autoconfigure/web/reactive/WebFluxTest.html
- Spring Framework reference: https://docs.spring.io/spring-framework/reference/testing.html
- Spring Boot project: https://github.com/spring-projects/spring-boot

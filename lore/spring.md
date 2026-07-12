# Spring (core)

DO constructor-inject (final fields; no `@Autowired` on the sole constructor) — testable, immutable, no circular deps. DON'T field-inject (`@Autowired` on fields).
DO bind config via `@ConfigurationProperties` over scattered `@Value`; keys in `application.yml`/`.properties` (pick one). DO annotate entry class `@SpringBootApplication` — keep beans in/below its package.
DON'T self-invoke `@Transactional`/`@Async`/`@Cacheable` (`this.x()`) — bypasses the proxy; call across beans. DO put `@Transactional` on public methods only.
DO use `@RestController` for JSON, `@Controller` for views; `@GetMapping`/`@PostMapping` for routes. DON'T mix blocking JDBC with WebFlux — use R2DBC or stay on MVC.
DO slice tests (`@WebMvcTest`, `@DataJpaTest`); `@SpringBootTest` loads full context (slow). Watch JPA N+1 from lazy loading.

Version: Boot 4.x current (Spring Framework 7, Java 17+, `jakarta.*`); prior 3.x (Framework 6, Java 17+, `jakarta.*`). Boot 2.x = Java 8+, `javax.*` — `javax.*` imports break on 3+.
Commands: run `./mvnw spring-boot:run` / `./gradlew bootRun`; build `./mvnw package` / `./gradlew bootJar`; test `./mvnw test` / `./gradlew test`.

Deep dive when writing non-trivial spring — read lore/spring/{di-config-and-boot,web-mvc-vs-webflux,data-access,security-and-actuator,testing}.md

Sources: docs.spring.io/spring-boot, docs.spring.io/spring-framework, spring.io/projects/spring-boot, github.com/spring-projects/spring-boot

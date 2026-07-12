# spring — DI, configuration & Boot conventions

Framework-specifics only (Java-language lore lives in `lore/java/*`). Verify version facts against Sources before asserting.

## Version baseline (verified)

| Boot | Spring Framework | Java | Namespace |
|------|------------------|------|-----------|
| 4.x (current, e.g. 4.1.0) | 7.0.x | 17–26, Servlet 6.1+ | `jakarta.*` |
| 3.x (prior, e.g. 3.5.x) | 6.2.x | 17–25, Servlet 5.0/6.0 | `jakarta.*` |
| 2.x (EOL OSS) | 5.x | 8+, Servlet 3.1–4 | `javax.*` |

- DON'T assume `javax.*`. Boot 3+ / Framework 6+ moved every EE API to `jakarta.*` (`jakarta.servlet`, `jakarta.persistence`, `jakarta.validation`, `jakarta.annotation`); `javax.*` is Boot 2.x only. Biggest 2→3 break.
- DON'T target Java <17 for Boot 3/4 (Boot 2 baseline is Java 8).

## Dependency injection

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

### Circular dependencies

- DON'T create A↔B constructor cycles → `BeanCurrentlyInCreationException` at startup. Fix the design (extract a third collaborator); don't paper over it with `@Lazy` or setter injection.

## Stereotypes & config

- DO annotate beans by role: `@Component` (generic), `@Service` (business), `@Repository` (persistence — adds exception translation), `@Controller`/`@RestController` (web). All are meta-`@Component`, scanned by `@ComponentScan`.
- DO use `@Configuration` + `@Bean` factory methods for beans you don't own or must wire manually.
- DO set `@Configuration(proxyBeanMethods = false)` when `@Bean` methods never call each other — skips CGLIB proxying, faster startup. Keep default `true` only if one `@Bean` method calls another and needs the same singleton.

```java
@Configuration(proxyBeanMethods = false)
class ClientConfig {
  @Bean RestClient restClient(RestClient.Builder b) { return b.build(); }
}
```

## Scopes & lifecycle

- Scopes: `singleton` (default, one per container), `prototype` (new each request), plus web-aware `request` / `session` / `application` / `websocket`.
- DO keep singletons **stateless** and thread-safe; use `prototype` for stateful beans.
- DON'T rely on destruction callbacks for prototypes. Spring calls `@PostConstruct` but **not** `@PreDestroy` on prototypes — the client owns cleanup.
- DON'T inject a prototype directly into a singleton (it resolves once, frozen). Use `ObjectProvider<T>` (`getObject()` per call), `@Lookup`, or a scoped proxy.
- DO use `@PostConstruct` / `@PreDestroy` for init/teardown (from `jakarta.annotation` in Boot 3+; `javax.annotation` in Boot 2).

## @ConfigurationProperties vs @Value

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

## Profiles

- DO mark environment-specific beans with `@Profile("dev")` / `@Profile("!prod")`; activate via `spring.profiles.active` (property/env/`--arg`).
- DON'T use the old `spring.profiles` key inside a document — replaced by `spring.config.activate.on-profile` (Boot 2.4+). Group profiles with `spring.profiles.group.<name>` (Boot 2.4+), not `spring.profiles.include`.

## Config files & precedence

- DON'T put both `application.yml` and `application.properties` in one location — **`.properties` wins**. Pick one format.
- Profile-specific files (`application-<profile>.yml`) always override the plain file. With multiple active profiles, **last-listed wins**.
- Property source precedence (high→low): command-line args → `SPRING_APPLICATION_JSON` → JNDI → Java system props → OS env → config data (`application*.yml`) → `@PropertySource` → `SpringApplication` defaults. (Test sources sit above CLI args.)
- DO externalize secrets/K8s config via `spring.config.import=configtree:/etc/config/` (file-per-key) or `optional:file:./x.yml`. Imported values override the importing file.
- DO use `spring.config.additional-location` to add search paths; `spring.config.location` **replaces** defaults (rarely what you want).

## Auto-configuration & starters

- `@SpringBootApplication` = `@EnableAutoConfiguration` + `@ComponentScan` + `@SpringBootConfiguration`. Put it on the top package; scan runs from there down.
- DO depend on official starters (`spring-boot-starter-web`, `-data-jpa`, `-security`, `-validation`, `-actuator`); the jar triggers matching auto-config via `@Conditional*` checks. DON'T name a third-party starter `spring-boot-starter-*` (reserved) — use `<name>-spring-boot-starter`.
- DO register your own auto-config classes in `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` (one FQN/line), annotated `@AutoConfiguration`. DON'T use `META-INF/spring.factories` — deprecated for this in Boot 2.7.
- DO gate custom beans with `@ConditionalOnMissingBean` / `@ConditionalOnClass` / `@ConditionalOnProperty` so users can override.
- DO disable auto-config via `@SpringBootApplication(exclude = X.class)` or `spring.autoconfigure.exclude`. Diagnose with `--debug` or the Actuator `conditions` endpoint.

## Sources

- Spring Boot reference (4.1): https://docs.spring.io/spring-boot/index.html
- System requirements (4.1): https://docs.spring.io/spring-boot/system-requirements.html
- System requirements (3.5): https://docs.spring.io/spring-boot/3.5/system-requirements.html
- Externalized configuration: https://docs.spring.io/spring-boot/reference/features/external-config.html
- Auto-configuration: https://docs.spring.io/spring-boot/reference/using/auto-configuration.html
- Spring Framework — DI / collaborators: https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html
- Spring Framework — bean scopes: https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html
- Spring Boot project / version mappings: https://spring.io/projects/spring-boot

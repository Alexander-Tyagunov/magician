Common AI mistakes: field injection (`@Autowired` on field) instead of constructor injection; not using `@Transactional` on service methods; N+1 with lazy loading in JPA; circular dependencies from field injection.
Commands: build: `./mvnw package`, test: `./mvnw test`, run: `./mvnw spring-boot:run`.
Gotchas: `@SpringBootTest` loads full context (slow) — use `@WebMvcTest` for controller tests; `application.properties` vs `application.yml` — pick one; Actuator exposes `/actuator/health`.

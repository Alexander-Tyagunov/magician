# spring — Security & Actuator

Framework-specific lore. Java-language rules live in `lore/java/*`. Verify version facts against current docs before asserting.

## Version baseline (pick the right era)

- **Spring Boot 3.x** (3.0 Nov 2022 → 3.5) requires **Java 17+**, Spring Framework 6.x, **Spring Security 6.x**, `jakarta.*` namespace. Boot 4.x (4.0 Nov 2025, 4.1 Jun 2026) also Java 17+, Security 7.x.
- **Spring Boot 2.x** (max 2.7, OSS EOL Jun 2023; commercial to 2029) is Java 8+, Spring Framework 5.x, **Spring Security 5.x**, `javax.*`.
- DO default to Boot 3.x lambda-DSL patterns. DON'T write `javax.*` imports for 3.x/4.x — it's `jakarta.*`.

## SecurityFilterChain (config)

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

## Password encoding

- DO expose a `PasswordEncoder` bean via `PasswordEncoderFactories.createDelegatingPasswordEncoder()` (default `{bcrypt}`, strength 10). Storage format is `{id}hash`, enabling multi-algorithm match + upgrade.
- DON'T use `NoOpPasswordEncoder` (plaintext) or `User.withDefaultPasswordEncoder()` (demo-only — hash lands in memory/source) in production. Both deprecated.
- DO tune bcrypt strength so a hash takes ~1s (`new BCryptPasswordEncoder(strength)`); or use argon2/pbkdf2/scrypt encoders.

## Method security

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

## CSRF

- CSRF is **ON by default** (unsafe methods) in both 5.x and 6.x. Security 6 adds deferred token loading + BREACH protection (`XorCsrfTokenRequestAttributeHandler`).
- DO `http.csrf(csrf -> csrf.disable())` **only** for stateless, non-browser APIs (JWT bearer in `Authorization` header — not CSRF-vulnerable). Pair with `sessionManagement(s -> s.sessionCreationPolicy(STATELESS))`.
- DO keep CSRF for cookie/session browser apps. For SPAs use `csrf.spa()` (Security 6.x) or `CookieCsrfTokenRepository.withHttpOnlyFalse()`.
- DON'T blanket-disable CSRF on a hybrid app that also serves browser sessions.

## CORS

- DO enable via `http.cors(Customizer.withDefaults())` and publish a `UrlBasedCorsConfigurationSource` bean; Spring Security wires it into the filter chain (also feeds MVC).
- DON'T rely on `@CrossOrigin`/MVC CORS alone when Security is present — Security's filter runs first. Set explicit `setAllowedOrigins`/`setAllowedMethods`; avoid `*` with credentials.

## OAuth2 resource server / JWT

- DO add `spring-boot-starter-oauth2-resource-server` (pulls `oauth2-resource-server` + `oauth2-jose`).
- DO set one of:
```yaml
spring.security.oauth2.resourceserver.jwt.issuer-uri: https://idp.example.com   # auto-discovers JWKS + validates iss
# or, to avoid startup dependency:
spring.security.oauth2.resourceserver.jwt.jwk-set-uri: https://idp.example.com/.well-known/jwks.json
```
- DO enable `.oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))`. Scopes map to `SCOPE_` authorities; check via `hasAuthority("SCOPE_message:read")` (6.x). `sub` becomes the principal name.
- DO set `...jwt.audiences` to validate the `aud` claim when the IdP is multi-tenant.

## Actuator

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

## Health, probes & metrics

- DO enable K8s probes: `management.endpoint.health.probes.enabled: true` → `/actuator/health/liveness` + `/readiness`. Use `add-additional-paths=true` for `/livez`,`/readyz` on the main port.
- DON'T put external-system checks in the **liveness** probe — a downstream outage would trigger pod restarts (cascading failure). Readiness may include external checks via a health group.
- DO implement custom checks with a `HealthIndicator` bean (bean `FooHealthIndicator` → id `foo`).
- Metrics are **Micrometer**-backed. For Prometheus scraping add `micrometer-registry-prometheus`, then expose the `prometheus` endpoint (not exposed by default). `metrics` endpoint is for diagnostics, not scraping.

## Sources

- https://docs.spring.io/spring-security/reference/servlet/configuration/java.html
- https://docs.spring.io/spring-security/reference/servlet/authorization/method-security.html
- https://docs.spring.io/spring-security/reference/features/authentication/password-storage.html
- https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html
- https://docs.spring.io/spring-security/reference/6.5/servlet/integrations/cors.html
- https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html
- https://docs.spring.io/spring-boot/reference/actuator/endpoints.html
- https://spring.io/projects/spring-boot
- https://github.com/spring-projects/spring-boot

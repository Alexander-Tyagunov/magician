# Java — Java version decision guide (8 -> 11 -> 17 -> 21 -> 25 -> later)

Per-release capability + decision matrix. Never claim a feature ships earlier than the release that *finalized* it (preview ≠ final). Default target: **Java 25 (LTS)**; always give the older-baseline fallback.

## DO: detect the project's Java version before writing code

Never guess the baseline. Check, in order:

- **Maven** — `pom.xml`: `<maven.compiler.release>` (preferred) or `<release>`/`<source>`/`<target>` on `maven-compiler-plugin`.
  ```xml
  <properties><maven.compiler.release>21</maven.compiler.release></properties>
  ```
- **Gradle** — `build.gradle[.kts]`: toolchain (preferred) or `sourceCompatibility`/`targetCompatibility`.
  ```kotlin
  java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
  ```
- **Version managers** — `.java-version` (jenv/asdf), `.sdkmanrc` (SDKMAN), `.tool-versions`.
- **Environment** — `JAVA_HOME`, `java -version`, `javac --version`.
- **At runtime** — `Runtime.version()` (prefer over parsing `System.getProperty("java.version")`).

DO write to the `release` you detect, not to the JDK that happens to be installed. The `release` flag is the source of truth for available APIs.

## DO: know the LTS cadence

- Feature release every **6 months**; **LTS every 2 years** since JDK 21.
- LTS line: **8, 11, 17, 21, 25**. JDK 25 released **2025-09-16**.
- Non-LTS releases (18, 19, 20, 22, 23, 24…) are stepping stones — assume prod baselines sit on an LTS. Treat "we're on Java 20" as "target 21".

## Capability matrix — which release FINALIZED each feature (JEP)

| Feature | Final in | JEP |
|---|---|---|
| `var` local-variable type inference | 10 | JEP 286 |
| Standard HTTP Client (`java.net.http`) | 11 | JEP 321 |
| Switch expressions (`yield`, arrow) | 14 | JEP 361 |
| Text blocks (`"""`) | 15 | JEP 378 |
| ZGC production-ready | 15 | JEP 377 |
| Records | 16 | JEP 395 |
| Pattern matching for `instanceof` | 16 | JEP 394 |
| Sealed classes | 17 | JEP 409 |
| Sequenced collections | 21 | JEP 431 |
| Generational ZGC | 21 | JEP 439 |
| Record patterns (deconstruction) | 21 | JEP 440 |
| Pattern matching for `switch` | 21 | JEP 441 |
| **Virtual threads** | 21 | JEP 444 |
| Foreign Function & Memory API | 22 | JEP 454 |
| Unnamed variables & patterns (`_`) | 22 | JEP 456 |
| Stream gatherers (`Stream.gather`) | 24 | JEP 485 |
| ZGC: non-generational mode removed | 24 | JEP 490 |
| **Scoped values** | 25 | JEP 506 |
| Module import declarations (`import module`) | 25 | JEP 511 |
| Compact source files & instance `main` | 25 | JEP 512 |
| Flexible constructor bodies | 25 | JEP 513 |
| Generational Shenandoah | 25 | JEP 521 |

DON'T treat these as final — still **preview/incubator** as of JDK 25, API may change; do not use in production code you can't easily rewrite:
- **Structured concurrency** — `java.util.concurrent.StructuredTaskScope`, still preview (JEP 505, 5th preview).
- **Primitive types in patterns/`instanceof`/`switch`** — preview (JEP 507).
- **Stable values** — preview (JEP 502). **PEM encodings** — preview (JEP 470). **Vector API** — incubator (JEP 508).
- **String templates** — was preview in 21/22, **dropped**, never finalized. Do NOT use; concatenate or `String.format`/`MessageFormat`.

## DO: concurrency by baseline

- **Java 21+**: one virtual thread per task for blocking I/O.
  ```java
  try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
      exec.submit(task);
  }
  ```
  DON'T pool virtual threads and DON'T `synchronized` around blocking calls on hot paths (prefer `ReentrantLock`; JDK 24+ removed most pinning, but locks are still cleaner).
- **Java 8–17**: bounded platform-thread pool sized to the workload; never `newCachedThreadPool()` for unbounded fan-out.
  ```java
  ExecutorService exec = Executors.newFixedThreadPool(n);
  ```
- Task groups: **Java 25** may use preview `StructuredTaskScope`; **≤24** use `ExecutorService.invokeAll` / `CompletableFuture.allOf`.
- Request/context propagation: **Java 25** `ScopedValue` (final); **≤24** `ThreadLocal` (and beware leaks with pooled threads).

## DO: data modeling & control flow

- **DTO / value carrier** — Java 16+: `record`. Java ≤15: final class with explicit fields/`equals`/`hashCode`.
  ```java
  record Point(int x, int y) {}
  ```
- **Closed hierarchy** — Java 17+: `sealed` + `permits`, then exhaustive `switch` (no `default`). Java ≤16: enum or visitor.
- **Type test** — Java 16+: `if (o instanceof String s)`. Java ≤15: cast after `instanceof`.
- **Switch over shapes** — Java 21+: pattern `switch` + record patterns.
  ```java
  return switch (shape) {
      case Circle(double r)    -> Math.PI * r * r;
      case Rect(double w, double h) -> w * h;
  };
  ```
  Java ≤20: `if`/`else instanceof` chain.
- **Multiline strings** — Java 15+: text blocks. Java ≤14: `\n` concatenation.
- **First/last of a `List`/`LinkedHashSet`/`LinkedHashMap`** — Java 21+: `getFirst()`/`getLast()`/`reversed()` (SequencedCollection). Java ≤20: `list.get(0)` / `list.get(size-1)`.
- **Custom stream stage** — Java 24+: `Stream.gather(Gatherer)`. Java ≤23: `collect` / manual iteration.

## DO: GC & runtime defaults

- Default collector is **G1** (since JDK 9). DON'T set `-XX:+UseParallelGC` unless you measured throughput needs.
- Low pause, large heaps — Java 21+: `-XX:+UseZGC` (generational is default; non-generational removed in 24). Java 15–20: ZGC available but non-generational.
- Java 25: `-XX:+UseShenandoahGC` is generational; compact object headers (`-XX:+UseCompactObjectHeaders`) are product for heap savings.
- Containers: JDKs are container-aware by default; prefer `-XX:MaxRAMPercentage` over hardcoded `-Xmx`.

## DON'T (cross-version traps)

- DON'T use `--illegal-access`; JDK internals are strongly encapsulated by default since JDK 17 (JEP 403), and the flag is now an obsolete no-op (accepted but ignored with a warning), not a workaround.
- DON'T rely on the Security Manager — deprecated (JDK 17) and permanently disabled (JDK 24, JEP 486).
- DON'T ship `sun.misc.Unsafe` memory access — warned in JDK 24 (JEP 498); migrate to VarHandle / FFM API.
- DON'T assume `Executors.newVirtualThreadPerTaskExecutor()` exists below 21, or `record`/`sealed` below 16/17. Guard by detected `release`.

## Sources

- JEP Index — https://openjdk.org/jeps/0
- JDK 25 (Project) — https://openjdk.org/projects/jdk/25/
- JDK 21 (Project) — https://openjdk.org/projects/jdk/21/
- JDK 17 (Project) — https://openjdk.org/projects/jdk/17/
- Oracle Java SE Support Roadmap (LTS cadence) — https://www.oracle.com/java/technologies/java-se-support-roadmap.html
- dev.java — Java evolution — https://dev.java/evolution/
- Key JEPs cited above (browse at https://openjdk.org/jeps/NNN): 286 var; 321 HTTP Client; 361 Switch Expressions; 377 ZGC; 378 Text Blocks; 394 Pattern Matching for instanceof; 395 Records; 403 Strongly Encapsulate JDK Internals; 409 Sealed Classes; 431 Sequenced Collections; 439 Generational ZGC; 440 Record Patterns; 441 Pattern Matching for switch; 444 Virtual Threads; 454 Foreign Function & Memory API; 456 Unnamed Variables & Patterns; 485 Stream Gatherers; 486 Permanently Disable the Security Manager; 490 ZGC Remove Non-Generational Mode; 498 Warn on sun.misc.Unsafe; 505 Structured Concurrency (Preview); 506 Scoped Values; 507 Primitive Types in Patterns (Preview); 511 Module Import Declarations; 512 Compact Source Files & Instance Main Methods; 513 Flexible Constructor Bodies; 519 Compact Object Headers; 521 Generational Shenandoah
- InfoQ release coverage (JDK 14/15/16/17/21/22/24/25) — https://www.infoq.com/news/2025/09/java25-released/

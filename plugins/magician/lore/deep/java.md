# Java — deep dive

> On-demand companion to `lore/java.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Java version decision guide (8 -> 11 -> 17 -> 21 -> 25 -> later)](#versions) · [Language & idioms](#language-and-idioms) · [Concurrency & virtual threads](#concurrency) · [Sync vs async & reactive](#async-and-reactive) · [I/O & servers (Netty vs Tomcat)](#io-and-servers) · [Errors & resources](#errors-and-resources) · [Performance & GC](#performance-and-gc) · [Build & testing](#build-and-testing)

## Java version decision guide (8 -> 11 -> 17 -> 21 -> 25 -> later) <a id="versions"></a>

Per-release capability + decision matrix. Never claim a feature ships earlier than the release that *finalized* it (preview ≠ final). Default target: **Java 25 (LTS)**; always give the older-baseline fallback.

### DO: detect the project's Java version before writing code

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

### DO: know the LTS cadence

- Feature release every **6 months**; **LTS every 2 years** since JDK 21.
- LTS line: **8, 11, 17, 21, 25**. JDK 25 released **2025-09-16**.
- Non-LTS releases (18, 19, 20, 22, 23, 24…) are stepping stones — assume prod baselines sit on an LTS. Treat "we're on Java 20" as "target 21".

### Capability matrix — which release FINALIZED each feature (JEP)

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

### DO: concurrency by baseline

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

### DO: data modeling & control flow

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

### DO: GC & runtime defaults

- Default collector is **G1** (since JDK 9). DON'T set `-XX:+UseParallelGC` unless you measured throughput needs.
- Low pause, large heaps — Java 21+: `-XX:+UseZGC` (generational is default; non-generational removed in 24). Java 15–20: ZGC available but non-generational.
- Java 25: `-XX:+UseShenandoahGC` is generational; compact object headers (`-XX:+UseCompactObjectHeaders`) are product for heap savings.
- Containers: JDKs are container-aware by default; prefer `-XX:MaxRAMPercentage` over hardcoded `-Xmx`.

### DON'T (cross-version traps)

- DON'T use `--illegal-access`; JDK internals are strongly encapsulated by default since JDK 17 (JEP 403), and the flag is now an obsolete no-op (accepted but ignored with a warning), not a workaround.
- DON'T rely on the Security Manager — deprecated (JDK 17) and permanently disabled (JDK 24, JEP 486).
- DON'T ship `sun.misc.Unsafe` memory access — warned in JDK 24 (JEP 498); migrate to VarHandle / FFM API.
- DON'T assume `Executors.newVirtualThreadPerTaskExecutor()` exists below 21, or `record`/`sealed` below 16/17. Guard by detected `release`.

### Sources

- JEP Index — https://openjdk.org/jeps/0
- JDK 25 (Project) — https://openjdk.org/projects/jdk/25/
- JDK 21 (Project) — https://openjdk.org/projects/jdk/21/
- JDK 17 (Project) — https://openjdk.org/projects/jdk/17/
- Oracle Java SE Support Roadmap (LTS cadence) — https://www.oracle.com/java/technologies/java-se-support-roadmap.html
- dev.java — Java evolution — https://dev.java/evolution/
- Key JEPs cited above (browse at https://openjdk.org/jeps/NNN): 286 var; 321 HTTP Client; 361 Switch Expressions; 377 ZGC; 378 Text Blocks; 394 Pattern Matching for instanceof; 395 Records; 403 Strongly Encapsulate JDK Internals; 409 Sealed Classes; 431 Sequenced Collections; 439 Generational ZGC; 440 Record Patterns; 441 Pattern Matching for switch; 444 Virtual Threads; 454 Foreign Function & Memory API; 456 Unnamed Variables & Patterns; 485 Stream Gatherers; 486 Permanently Disable the Security Manager; 490 ZGC Remove Non-Generational Mode; 498 Warn on sun.misc.Unsafe; 505 Structured Concurrency (Preview); 506 Scoped Values; 507 Primitive Types in Patterns (Preview); 511 Module Import Declarations; 512 Compact Source Files & Instance Main Methods; 513 Flexible Constructor Bodies; 519 Compact Object Headers; 521 Generational Shenandoah
- InfoQ release coverage (JDK 14/15/16/17/21/22/24/25) — https://www.infoq.com/news/2025/09/java25-released/

## Language & idioms <a id="language-and-idioms"></a>

Senior-reviewer checklist for modern Java. Target **Java 25 (LTS)**; fallbacks noted per baseline. Feature = *finalized* release, not preview.

### Records (JEP 395, final Java 16)

DO use `record` for immutable data carriers, DTOs, multi-value returns, compound map keys, local grouping types.
```java
record Point(int x, int y) {}                     // final; auto equals/hashCode/toString/accessors
```
DO validate/normalize in a **compact constructor** — params are auto-assigned to fields at the end.
```java
record Range(int lo, int hi) {
    Range { if (lo > hi) throw new IllegalArgumentException("lo>hi"); }  // no this.lo = lo
}
```
DO defensive-copy mutable components; records are only *shallowly* immutable, and components are public API.
DON'T use records when you need mutability, inheritance, or hidden fields — they are implicitly `final`, extend `java.lang.Record`, and forbid extra instance fields/initializers.

**Java 8–15:** hand-write the class (final fields, all-args ctor, `equals`/`hashCode`/`toString`), or use Lombok `@Value` / AutoValue.

### Sealed types (JEP 409, final Java 17)

DO seal a hierarchy you control to make it a closed algebraic type; each permitted subtype must be `final`, `sealed`, or `non-sealed`, and (unnamed module) in the same package/module.
```java
sealed interface Shape permits Circle, Square {}
record Circle(double r) implements Shape {}
record Square(double s) implements Shape {}
```
DO pair sealed + records + switch for exhaustive, `default`-free matching (compiler enforces coverage).
DON'T use `non-sealed` unless you genuinely want open extension — it reopens the hierarchy.

**Java 8–16:** no language support. Enforce with package-private constructors + a controlled subclass set, or an enum-of-subtypes; document the closed set.

### Pattern matching

DO use `instanceof` patterns (JEP 394, final Java 16) — no cast, flow-scoped binding.
```java
if (o instanceof String s && !s.isBlank()) use(s);
```
DO use switch patterns (JEP 441, final **Java 21**) with `when` guards; handle `null` via a `case null` (else NPE as before).
```java
String d = switch (shape) {
    case null            -> "none";
    case Circle c when c.r() > 10 -> "big circle";
    case Circle c        -> "circle";
    case Square s        -> "square";           // exhaustive: no default needed for sealed
};
```
DO deconstruct with record patterns (JEP 440, final Java 21), nesting allowed: `case Circle(double r)`.
DON'T add a `default` to an exhaustive sealed switch — it silences future-subtype compile errors you want.

**Java 8–20:** cast after `instanceof`; use if/else chains or classic `switch` on an enum/tag field.

### Text blocks (JEP 378, final Java 15)

DO use `"""` for multi-line SQL/JSON/HTML; align the closing `"""` to set the left margin (incidental whitespace is stripped). Use `\` to suppress a newline, `\s` to keep trailing space.
DON'T build multi-line strings with `+"\n"`. **Java 8–14:** concatenation or `String.join("\n", ...)`.

### var (JEP 286, Java 10)

DO use `var` for locals when the initializer makes the type obvious (`var users = new ArrayList<User>();`).
DON'T use it when it hides the type (`var x = getThing();`), on `null`/no initializer, or for fields/params/returns (not allowed there anyway).

### Enums

DO put behavior on enums (constant-specific methods, fields, constructors); use `EnumMap`/`EnumSet` over `HashMap`/`HashSet` for enum keys.
DON'T use `ordinal()` for persistence or logic — order changes break you; store `name()` or an explicit code.

### Generics & wildcards

DO apply **PECS**: `? extends T` for producers you read, `? super T` for consumers you write — `void copy(List<? super T> dst, List<? extends T> src)`.
DO prefer generic methods/bounded types over raw types; never use raw `List`.
DON'T create generic arrays or rely on runtime type args (erasure) — pass a `Class<T>` token if needed.

### Optional (Java 8; `Optional.stream()` Java 9)

DO use `Optional` only as a **return type** for "maybe absent". Chain `map`/`filter`/`flatMap`/`ifPresent`.
DO prefer `orElseGet(supplier)` over `orElse(expensive())` (arg is always evaluated); `orElseThrow()` over `get()`.
DON'T use `Optional` for fields, parameters, collection elements, or map values; DON'T call `get()` unguarded or return `null` from an `Optional` method. Return empty collections, not `Optional<Collection>`.

### Immutability, equals/hashCode/toString

DO make fields `final`, copy in/out defensively, expose no setters, prefer unmodifiable collections.
DO keep `equals`/`hashCode` in lockstep (equal ⇒ equal hashCodes; same fields in both); make `equals` reflexive/symmetric/transitive/consistent. Records give this free.
DON'T mutate fields used in `equals`/`hashCode` while the object is a key; DON'T leak secrets in `toString`.

### Comparable / Comparator

DO build comparators with combinators (Java 8): `Comparator.comparing(User::name).thenComparingInt(User::age).reversed()`; `nullsFirst`/`nullsLast` for nullable keys.
DON'T hand-roll `a - b` comparisons — overflow reorders; use `Integer.compare`. Keep `compareTo` consistent with `equals`.

### Streams & Collectors

DO stream for declarative bulk transforms; keep lambdas pure and side-effect-free.
DO collect immutably: `stream.toList()` (Java 16+, unmodifiable) or `Collectors.toUnmodifiableList()` (Java 10+). Pre-16 use `Collectors.toList()` (mutable, no type/serializability guarantee).
DON'T mutate external state in `forEach` or use `peek` for logic; DON'T reuse a consumed stream. Avoid `parallel()` unless the source splits well, work is large/CPU-bound, and ops are stateless/associative.
DON'T stream when a plain loop is clearer or hotter — index iteration, early exit, or single-pass mutation often reads better and allocates less.

**Java 8–15:** `collect(Collectors.toList())`; wrap with `Collections.unmodifiableList(...)` when you need immutability.

### Collections choice

DO pick by access pattern: `ArrayList` (default list, random access), `ArrayDeque` (stack/queue — not `Stack`/`LinkedList`), `HashMap`/`HashSet` (default), `LinkedHashMap` (insertion/LRU order), `TreeMap`/`TreeSet` (sorted), `EnumMap`/`EnumSet` (enum keys), `ConcurrentHashMap` (concurrent — not `Collections.synchronizedMap`).
DO create small immutables with `List.of`/`Set.of`/`Map.of` (JEP 269, Java 9) — reject nulls and duplicates.
DON'T use legacy `Vector`/`Hashtable`/`Stack`. DON'T size-blind: pass initial capacity for large known-size maps/lists.

### Sources

- JEP 395: Records — https://openjdk.org/jeps/395
- JEP 409: Sealed Classes — https://openjdk.org/jeps/409
- JEP 441: Pattern Matching for switch — https://openjdk.org/jeps/441
- JEP 394: Pattern Matching for instanceof — https://openjdk.org/jeps/394
- JEP 440: Record Patterns — https://openjdk.org/jeps/440
- JEP 378: Text Blocks — https://openjdk.org/jeps/378
- JEP 361: Switch Expressions — https://openjdk.org/jeps/361
- JEP 286: Local-Variable Type Inference (var) — https://openjdk.org/jeps/286
- JEP 269: Convenience Factory Methods for Collections — https://openjdk.org/jeps/269
- Oracle Java SE 25 Language Updates — https://docs.oracle.com/en/java/javase/25/language/
- Oracle: Records — https://docs.oracle.com/en/java/javase/25/language/records.html
- Oracle: Text Blocks — https://docs.oracle.com/en/java/javase/25/language/text-blocks.html
- dev.java: Records — https://dev.java/learn/records/
- dev.java: Pattern Matching — https://dev.java/learn/pattern-matching/
- dev.java: Using var — https://dev.java/learn/language-basics/using-var/
- Javadoc: java.util.Optional — https://docs.oracle.com/javase/8/docs/api/java/util/Optional.html
- Javadoc: java.util.stream.Stream (toList) — https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/stream/Stream.html

## Concurrency & virtual threads <a id="concurrency"></a>

Senior-reviewer checklist. Verify the target JDK before applying any rule.
Finality map (do not misremember): Virtual Threads **final in 21** (JEP 444);
synchronized-pinning fix **in 24** (JEP 491); Scoped Values **final in 25** (JEP 506);
Structured Concurrency **still preview in 25** (JEP 505) — `StructuredTaskScope` is not stable API.

### Threads vs ExecutorService

- **DON'T** create raw `new Thread(...).start()` for tasks — unbounded, unmanaged, no result/error channel.
- **DO** submit to an `ExecutorService` and always shut it down (try-with-resources on 19+; `ExecutorService` is `AutoCloseable`, `close()` awaits termination).
```java
try (var pool = Executors.newFixedThreadPool(8)) {
    Future<Integer> f = pool.submit(() -> compute());
    int r = f.get();
} // close() blocks until tasks finish
```
- **DO** size platform pools to the workload: CPU-bound ≈ `Runtime.getRuntime().availableProcessors()`; I/O-bound needs more — but prefer virtual threads (21+) over a huge platform pool.
- **DON'T** use `newCachedThreadPool()` for untrusted/bursty load — unbounded, can exhaust the OS.
- **DON'T** call `Thread.stop()`/`suspend()`/`resume()`. Cancel via interruption + a checked flag.

### Virtual threads (JEP 444, final in Java 21)

- **DO** use virtual threads for high-throughput, thread-per-request, blocking I/O — **21+ only**.
```java
// Java 21+
try (var vexec = Executors.newVirtualThreadPerTaskExecutor()) {
    for (var req : requests) vexec.submit(() -> handle(req));
}
// or: Thread.ofVirtual().start(runnable);
```
- **Java 8–17 fallback:** no virtual threads. Use a **bounded** platform pool (`newFixedThreadPool`) or `CompletableFuture` + async I/O — never unbounded pools.
- **DON'T pool virtual threads.** Cheap and disposable — one per task. Never build a `newFixedThreadPool` of virtual threads; never reuse them.
- **DON'T** use virtual threads for CPU-bound work — no speed, only scale (Little's Law). Keep a platform `ForkJoinPool` for parallel compute.
- **DON'T** cap concurrency by pool size on virtual threads. Limit a scarce resource with a `Semaphore`, not a small pool.
- Virtual threads have fixed `NORM_PRIORITY` (`setPriority` no-op) and always support `ThreadLocal`.

#### Pinning

- Pinning = a virtual thread cannot unmount from its carrier while blocked, starving the scheduler.
- **Java 21–23:** `synchronized` blocks/methods that guard blocking I/O **pin**. **DO** replace those hot `synchronized` regions with `ReentrantLock`.
```java
private final ReentrantLock lock = new ReentrantLock();
lock.lock(); try { blockingIo(); } finally { lock.unlock(); }
```
- **Java 24+ (JEP 491):** `synchronized` no longer pins in nearly all cases — the migration above is usually unnecessary. Remaining pinning: native/JNI and foreign-function calls.
- **DO** detect pinning via the `jdk.VirtualThreadPinned` JFR event (on by default, 20 ms threshold). (`-Djdk.tracePinnedThreads` was the 21–23 diagnostic.)

### Structured concurrency (JEP 505 — PREVIEW in 25, not final)

- **STATUS:** `StructuredTaskScope` is **preview** through JDK 25 (fifth; sixth = JEP 525 in 26). Requires `--enable-preview`. Do not adopt where a stable API surface is required.
- **DO** (25 preview) open via static factory + `Joiner`; scope is `AutoCloseable`:
```java
// Java 25 preview
try (var scope = StructuredTaskScope.open()) {          // all-success policy
    Subtask<String>  a = scope.fork(() -> query(left));
    Subtask<Integer> b = scope.fork(() -> query(right));
    scope.join();                                       // throws if any fails
    return new Result(a.get(), b.get());
}
```
- `fork`/`join`/`close` are owner-thread only; `join()` runs once; `fork` cannot follow `join`. Joiners: `awaitAllSuccessfulOrThrow`, `allSuccessfulOrThrow`, `anySuccessfulResultOrThrow`, `awaitAll`.
- **Pre-25 / no preview:** coordinate fan-out with `ExecutorService.invokeAll` or `CompletableFuture.allOf` — cancel siblings on failure yourself.

### ScopedValue vs ThreadLocal (JEP 506 — final in 25)

- **DO** (25+) use `ScopedValue` for one-way, immutable, bounded-lifetime context — cheaper than `ThreadLocal`, safe for millions of virtual threads.
```java
// Java 25+
static final ScopedValue<User> USER = ScopedValue.newInstance();
ScopedValue.where(USER, user).run(() -> handle());   // USER.get() valid only inside
```
- **DON'T** reach for `ThreadLocal` as ambient context with virtual threads: mutable, unbounded lifetime, per-thread copies leak at scale. `ScopedValue` is immutable and auto-cleared at scope exit.
- **Pre-25 fallback:** `ThreadLocal` (`private static final`), and **always** `remove()` in a `finally` when reusing platform threads to avoid leaks/stale reads.
- `ThreadLocal` still fits expensive mutable per-thread caches (e.g. legacy `SimpleDateFormat`; better: share an immutable `DateTimeFormatter`).

### java.util.concurrent building blocks

- **DO** prefer `ConcurrentHashMap` over `Collections.synchronizedMap`; use atomic composites — `computeIfAbsent`, `merge`, `compute` — never get-then-put (a race). Iterators are weakly consistent.
- **DO** use `java.util.concurrent.atomic` for lock-free counters; `LongAdder` beats `AtomicLong` under high contention.
- **DON'T** hand-roll producer/consumer — use a `BlockingQueue` (`ArrayBlockingQueue` bounded, `SynchronousQueue`) for backpressure.
- **DO** compose async with `CompletableFuture` (`thenCompose`/`thenCombine`/`allOf`); pass an explicit `Executor` to `*Async` — the default common `ForkJoinPool` is shared and small. **Always** attach `exceptionally`/`handle`; a dropped future swallows exceptions.
- **DO** pick the right lock: `ReentrantLock` (try/timeout/fairness), `ReadWriteLock`/`StampedLock` (read-heavy; `StampedLock` optimistic, non-reentrant, no `Condition`), `Semaphore`, `CountDownLatch` (one-shot), `CyclicBarrier`/`Phaser` (reusable).

### Memory model & happens-before

- **DON'T** assume one thread's writes are visible to another without a happens-before edge. Unsynchronized shared mutable state = data race = undefined (torn/stale reads, reordering).
- **Edges you can rely on:** program order in a thread; monitor unlock → later lock of same monitor; `volatile` write → later read of that field; `Thread.start()` → the thread's actions; a thread's actions → another returning from its `join()`; `final` fields via a properly constructed object.
- **j.u.c. edges:** put into a concurrent collection → later read/remove; `Lock.unlock`→`lock`, `Semaphore.release`→`acquire`, `countDown`→`await`; submit → execution → `Future.get()`.
- **DO** mark a cross-thread flag `volatile` (e.g. a stop signal). `volatile` gives visibility + ordering, **not** atomicity of compound ops (`count++` still races — use an atomic/lock).
- **DO** publish safely (immutable `final`-field objects, or via `volatile`/`final`/concurrent collection). **DON'T** leak `this` from a constructor.

### Sources

- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444) — final in JDK 21
- [JEP 491: Synchronize Virtual Threads without Pinning](https://openjdk.org/jeps/491) — delivered JDK 24
- [JEP 506: Scoped Values](https://openjdk.org/jeps/506) — final in JDK 25
- [JEP 505: Structured Concurrency (Fifth Preview)](https://openjdk.org/jeps/505) — preview in JDK 25
- [JEP 525: Structured Concurrency (Sixth Preview)](https://openjdk.org/jeps/525) — preview in JDK 26
- [java.util.concurrent package summary (JDK 25)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/package-summary.html) — happens-before rules, classes
- [StructuredTaskScope (JDK 25 preview)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/StructuredTaskScope.html)
- [dev.java — Learn Java](https://dev.java/learn/)
- JLS §17.4 Memory Model / happens-before order

## Sync vs async & reactive <a id="async-and-reactive"></a>

Senior-reviewer checklist. Pick ONE model per call path; never mix blocking calls into a
non-blocking chain. Target Java 25 LTS; fallbacks noted per rule.

### Choosing a model (decision first)

- **DO** default to plain **blocking, thread-per-task** code on **Java 21+** — virtual threads
  make it scale. Reserve reactive for pre-21 baselines or genuine event-loop/streaming needs.
- **DO** use **CompletableFuture** for a *few* independent async steps you compose in one method.
- **DO** use **Reactor/RxJava** only when you need operator pipelines, backpressure across a
  network boundary, or you're already in a reactive stack (WebFlux, R2DBC).
- **DON'T** adopt reactive "for performance" on Java 21+; virtual threads give the same
  throughput with debuggable stack traces. Reactive's cost is real: hard debugging.

### Virtual threads (Java 21+, JEP 444)

Finalized in **Java 21** (JEP 444). A blocking call *unmounts* the virtual thread from its
carrier, so the OS thread is free — millions of VTs are fine.

- **DO** create one VT per task; the executor is auto-closeable and joins on close:
  ```java
  try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
      exec.submit(() -> httpClient.send(req, ofString())); // blocking is OK here
  }
  ```
  Also `Thread.ofVirtual().start(r)` / `Thread.startVirtualThread(r)`.
- **DON'T** pool virtual threads. Pools reuse *expensive* resources; VTs are cheap. To cap a
  scarce downstream (DB pool), use a `Semaphore`, not a fixed thread pool.
- **DON'T** rely on `ThreadLocal` for heavy caching across millions of VTs — memory blows up.
- **Pinning:** pre-24, a VT blocking inside `synchronized` pinned its carrier. **JEP 491
  (Java 24)** removed `synchronized` pinning; native/FFM frames can still pin.
  - **Java 21–23:** replace `synchronized` guarding a blocking op with `ReentrantLock`; diagnose
    with `-Djdk.tracePinnedThreads=full` or JFR `jdk.VirtualThreadPinned`.
  - **Java 24+:** `synchronized` no longer pins on block — the workaround is optional.
- **Java 8–17 fallback:** no VTs. Use a **bounded** platform-thread pool
  (`Executors.newFixedThreadPool(n)`); never `newCachedThreadPool()` for unbounded blocking I/O.

### CompletableFuture (Java 8+; timeouts Java 9+)

- **DO** pass an explicit `Executor` to every `*Async` step doing real work. The no-executor
  `supplyAsync`/`thenApplyAsync` run on `ForkJoinPool.commonPool()`.
  ```java
  var pool = Executors.newFixedThreadPool(8);
  CompletableFuture.supplyAsync(this::loadA, pool)
      .thenCombine(CompletableFuture.supplyAsync(this::loadB, pool), this::merge);
  ```
- **DON'T** run **blocking** I/O on the common pool — it's sized to CPU count and shared
  JVM-wide; you starve parallel streams and other futures. (On Java 21+, hand the blocking work
  to `newVirtualThreadPerTaskExecutor()` instead.)
- **DO** compose, don't block: `thenCompose` (flatMap, avoid nested `CompletableFuture<CompletableFuture<T>>`),
  `thenCombine` (join two), `allOf`/`anyOf` (fan-in). `thenApply` (no `Async`) may run on the
  completing thread — fine for cheap, pure maps only.
- **DON'T** swallow failures. Terminate every chain with `exceptionally(fn)` or `handle((v,ex)->…)`;
  an uncaught exceptional stage is silent. Add `orTimeout(d,unit)` (fails with `TimeoutException`)
  or `completeOnTimeout(fallback,d,unit)`.
- **DON'T** call `.get()`/`.join()` mid-pipeline — it blocks a pool thread.

### Flow API / Reactive Streams (spec)

`java.util.concurrent.Flow` (JDK 9+) is **1:1 semantically equivalent** to the Reactive Streams
1.0.4 spec (`org.reactivestreams`). Four interfaces, seven one-way `void` methods:

- `Flow.Publisher<T>.subscribe(Subscriber<? super T>)`
- `Flow.Subscriber<T>`: `onSubscribe(Subscription)`, `onNext(T)`, `onError(Throwable)`, `onComplete()`
- `Flow.Subscription`: `request(long n)`, `cancel()`
- `Flow.Processor<T,R> extends Subscriber<T>, Publisher<R>`

**Backpressure = demand:** the subscriber pulls via `request(n)`; a compliant publisher never
sends more than requested. `Flow.defaultBufferSize()` is **256**.

- **DO** treat `Flow` as the neutral SPI for interop; **DON'T** hand-write publishers/subscribers
  for app logic — use Reactor or RxJava operators. Backpressure signaling stays non-blocking.
- **DON'T** block or throw inside `onNext`/`onError`/`onComplete`; **DON'T** `request(n<=0)`.

### Reactor (Mono/Flux) & RxJava — basics + backpressure

**Reactor** (`Flux<T>` 0..N, `Mono<T>` 0..1) — foundation of Spring WebFlux.
**RxJava 3** (`io.reactivex.rxjava3`): `Flowable` (backpressure, Reactive Streams) vs
`Observable` (NO backpressure — bounded/UI streams only); plus `Single`/`Maybe`/`Completable`.

- **DO** isolate blocking calls onto a dedicated scheduler so you don't stall the event loop:
  ```java
  Mono.fromCallable(() -> blockingJdbcCall())
      .subscribeOn(Schedulers.boundedElastic());   // Reactor
  ```
  RxJava equivalent: `Flowable.fromCallable(...).subscribeOn(Schedulers.io())`.
- **DON'T** block on the parallel/computation scheduler (Reactor `Schedulers.parallel()`,
  RxJava `Schedulers.computation()`) — those are CPU-bound, sized to cores.
- **`subscribeOn`** sets where the *source* runs (one per chain, position-independent);
  **`publishOn`**/`observeOn` switches the thread for operators *downstream* of it.
- **Backpressure:** prefer demand-aware sources. For bursty producers use
  `onBackpressureBuffer()` (bounded — set a max + overflow strategy; unbounded risks OOM),
  `onBackpressureDrop`, or `onBackpressureLatest`. In RxJava, use `Flowable` (not `Observable`)
  with a `BackpressureStrategy` when bridging via `Flowable.create(...)`.
- **DON'T** `block()`/`blockFirst()`/`blockLast()` (Reactor) or `blockingGet()`/`blockingFirst()`
  (RxJava) inside a reactive chain or on a non-blocking scheduler — allowed only at the true
  boundary (e.g. a `main`/test). To bridge to `CompletableFuture` **without** blocking, use
  `Mono.toFuture()` — it subscribes and completes the future on `onNext`/`onComplete` (it does
  not block and does not throw on a non-blocking scheduler).
- **DON'T** forget to subscribe — nothing runs until a terminal `subscribe(...)`. Handle the
  error consumer; a missing one rethrows to the global hook.

### Version cheat-sheet

- **Java 8:** CompletableFuture. No Flow, no VTs. Bounded pools; reactive libs for scale.
- **Java 9–17:** + `Flow` API, CF timeouts. Reactive is the scaling path.
- **Java 21 (LTS):** virtual threads final (JEP 444) — new code goes blocking thread-per-task.
- **Java 24:** `synchronized` no longer pins virtual threads (JEP 491).
- **Java 25 (LTS):** blocking + VTs is the default; reactive only for streaming/backpressure.
  Scoped Values final (JEP 506) as the `ThreadLocal` alternative; **Structured Concurrency is
  still preview (JEP 505) — behind `--enable-preview`, don't rely on it in production.**

### Sources

- Oracle Java SE 25 API — `java.util.concurrent.Flow`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/Flow.html
- Oracle Java SE 25 API — `java.util.concurrent.CompletableFuture`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/CompletableFuture.html
- Reactive Streams (spec 1.0.4, interfaces, backpressure, Flow equivalence): https://www.reactive-streams.org/
- JEP 444: Virtual Threads (finalized in Java 21): https://openjdk.org/jeps/444
- JEP 491: Synchronize Virtual Threads without Pinning (Java 24): https://openjdk.org/jeps/491
- Oracle — Creating/using virtual threads (no pooling, pinning, Semaphore): https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html
- Project Reactor Reference (schedulers, blocking bridge, backpressure): https://projectreactor.io/docs/core/release/reference/
- ReactiveX / RxJava (Observable vs Flowable, backpressure, Schedulers): https://github.com/ReactiveX/RxJava

## I/O & servers (Netty vs Tomcat) <a id="io-and-servers"></a>

Checklist for I/O model, concurrency model, and server runtime. Version-adaptive: target
Java 25 LTS, with fallbacks for 8/11/17/21.

### I/O model: the three tiers

- **`java.io` (blocking streams)** — `InputStream`/`Reader`. One thread parks per call.
  Simplest; scales with thread count.
- **`java.nio` (buffers + channels + `Selector`)** — non-blocking, readiness-based. Since
  **Java 1.4**. One thread multiplexes many sockets; the base for event-loop servers.
- **NIO.2 (`java.nio.file`, async channels)** — `Path`, `Files`,
  `AsynchronousSocketChannel`. Since **Java 7** (JSR 203).

DO use `java.nio.file` (`Path`/`Files`) for new filesystem code, not `java.io.File`.
DON'T hand-roll raw `Selector` loops; use Netty. Manual NIO is a bug farm (partial reads,
`flip()`/`compact()` errors, `OP_WRITE` starvation).

### Concurrency model: thread-per-request vs event-loop

- **Thread-per-request (servlet/Tomcat).** Each request owns a thread; straight-line
  blocking code. Throughput ceiling ≈ pool size; blocked threads still cost stack memory.
  Easy to write, profile, and debug (real stack traces).
- **Event-loop (Netty/reactive).** A few threads run non-blocking handlers over many
  connections. High connection density, low per-connection cost. But **any blocking call on
  an event-loop thread stalls every connection it serves.**

DON'T block a Netty `EventLoop` thread (JDBC, `Thread.sleep`, filesystem, `synchronized`
waits). Offload to a separate executor. DO keep handlers small and return fast.

### Virtual threads: the modern default (Java 21+)

Keep the simple thread-per-request style AND get event-loop-class scalability. Final
(non-preview) in **Java 21** via **JEP 444** (previewed: JEP 425 in 19, JEP 436 in 20).

```java
// Java 21+: one virtual thread per task, no pooling
try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
    exec.submit(() -> handle(conn));   // blocking I/O inside is fine
}
// Also: Thread.ofVirtual().start(r);  Thread.startVirtualThread(r);
```

Fallback (**Java 8–17**): bounded platform-thread pool (`Executors.newFixedThreadPool(n)`)
with a bounded queue + rejection policy.

DO write plain blocking code on virtual threads — that is the point. They boost
**throughput (scale), not latency (speed).**
DON'T pool virtual threads; they are cheap tasks, not scarce resources.
DON'T cache expensive objects in `ThreadLocal` on virtual threads (a new instance per task
can hit millions). Use immutable shared objects (`DateTimeFormatter`, not `SimpleDateFormat`)
or scoped values (`ScopedValue`, final only in Java 25 / JEP 506; preview on 21–24).
DO cap concurrency against a downstream with a `Semaphore`, not a thread pool:

```java
Semaphore db = new Semaphore(20);
db.acquire(); try { callDb(); } finally { db.release(); }
```

#### Pinning (why a virtual thread can't unmount)

- **Java 21–23:** a `synchronized` block around a blocking call **pins** the carrier.
  Replace hot `synchronized` with `ReentrantLock`.
- **Java 24+:** `synchronized` no longer pins (**JEP 491**). Per the **Java 25** docs the
  only remaining pinning causes are **`native` methods** and **FFM (foreign function)** calls.

DO detect pinning via the `jdk.VirtualThreadPinned` JFR event (on by default, 20 ms
threshold) before micro-optimizing locks.

### Running Tomcat on virtual threads (reactive alternative)

Tomcat 11 (Servlet 6.1, requires **Java 17+**) can dispatch each request on a virtual
thread instead of a pooled platform thread:

```xml
<Connector port="8080" protocol="org.apache.coyote.http11.Http11NioProtocol"
           useVirtualThreads="true" .../>
```

`useVirtualThreads` defaults to `false` and is **ignored if a shared `<Executor>` is set**.
On Java 21+ this gives blocking servlet code near-reactive scalability with far less
complexity than a reactive rewrite.
DON'T enable `useVirtualThreads` on Java < 21.

### Connection handling & backpressure

**Tomcat 11 connector defaults:** default protocol is **NIO** (`Http11NioProtocol`);
`Http11Nio2Protocol` is the NIO2 variant (APR is gone as a connector — TLS backend only).
Both are non-blocking for headers/TLS/keep-alive, blocking for body/response.

| Attr | Default | Meaning |
|---|---|---|
| `maxThreads` | 200 | Max concurrent request threads (ignored if `<Executor>` set) |
| `maxConnections` | 8192 | Accepted-connection ceiling; `-1` disables counting (NIO/NIO2) |
| `acceptCount` | 100 | OS accept queue once `maxConnections` hit |
| `connectionTimeout` | 60000 ms | Shipped `server.xml` uses 20000 |

DO size `maxThreads`/`maxConnections` to the downstream, not CPU count; on virtual threads,
raise/uncap `maxConnections` and stop tuning a fixed pool.

**Netty backpressure is not automatic in your handlers.**
DO check `Channel.isWritable()` / set `WRITE_BUFFER_WATER_MARK`, and toggle
`config().setAutoRead(false)` when a slow consumer falls behind — else the outbound buffer
grows unbounded (OOM).
DO release `ByteBuf` (`ReferenceCountUtil.release`) — it is reference-counted; leaks are the
classic Netty bug. Test with `-Dio.netty.leakDetection.level=paranoid`.

### Netty setup (server)

```java
// Netty 4.1 (stable, min JDK 6): boss accepts, worker serves
EventLoopGroup boss = new NioEventLoopGroup(1), worker = new NioEventLoopGroup();
new ServerBootstrap().group(boss, worker)
    .channel(NioServerSocketChannel.class)
    .childHandler(new ChannelInitializer<SocketChannel>() {
        protected void initChannel(SocketChannel ch) { ch.pipeline().addLast(new MyHandler()); }
    })
    .bind(8080).sync();
```

**Netty 4.2:** transport-specific groups are deprecated — use
`new MultiThreadIoEventLoopGroup(NioIoHandler.newFactory())` instead of `NioEventLoopGroup`.
DO frame the byte stream yourself: TCP is a byte queue, not messages — decode with
`ByteToMessageDecoder`/`LengthFieldBasedFrameDecoder`. Never assume one read == one message.
DO `shutdownGracefully()` both groups on exit.

### Netty vs servlet container — pick correctly

DO default to a **servlet container (Tomcat/Jetty) + virtual threads** for standard
HTTP/REST apps: blocking code, full ecosystem, real stack traces.
DO reach for **Netty** for custom/binary wire protocols, extreme connection counts (100k+
idle sockets), lowest per-connection overhead, or fine pipeline control (proxies, gateways,
chat/game servers). It underlies Reactor Netty, gRPC-Java, and Spring WebFlux.
DON'T adopt reactive/Netty purely "for performance" on a CRUD service — on Java 21+ virtual
threads close most of the throughput gap without the callback/debugging tax.

### Sources

- [Netty User Guide for 4.x](https://netty.io/wiki/user-guide-for-4.x.html)
- [Netty 4.2 Migration Guide](https://github.com/netty/netty/wiki/Netty-4.2-Migration-Guide)
- [Apache Tomcat 11.0 Documentation](https://tomcat.apache.org/tomcat-11.0-doc/index.html)
- [Apache Tomcat 11.0 HTTP Connector reference](https://tomcat.apache.org/tomcat-11.0-doc/config/http.html)
- [Apache Tomcat "Which Version" (spec + Java requirements)](https://tomcat.apache.org/whichversion.html)
- [Oracle: Virtual Threads (Java 21 Core Libraries)](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)
- [Oracle: Virtual Threads (Java 25 Core Libraries)](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html)
- [Oracle Java Tutorial: Basic I/O (java.io / NIO.2)](https://docs.oracle.com/javase/tutorial/essential/io/index.html)
- JEP 444: Virtual Threads (final, Java 21) — https://openjdk.org/jeps/444
- JEP 425: Virtual Threads (Preview, Java 19) — https://openjdk.org/jeps/425
- JEP 436: Virtual Threads (Second Preview, Java 20) — https://openjdk.org/jeps/436
- JEP 491: Synchronize Virtual Threads without Pinning (Java 24) — https://openjdk.org/jeps/491

## Errors & resources <a id="errors-and-resources"></a>

Senior-reviewer checklist for exceptions, resources, and absence. Version notes
mark the release that *finalized* each feature.

### Checked vs unchecked

Oracle's bottom line: *"If a client can reasonably be expected to recover from
an exception, make it a checked exception. If a client cannot do anything to
recover ... make it an unchecked exception."*

- **DO** throw checked (`extends Exception`) for recoverable, expected conditions
  the caller must handle (missing file, bad remote response).
- **DO** throw unchecked (`extends RuntimeException`) for programming bugs and
  precondition violations — `IllegalArgumentException`, `IllegalStateException`,
  `NullPointerException`. The caller cannot recover; fix the code.
- **DON'T** declare or catch `Error` / its subclasses (`OutOfMemoryError`,
  `StackOverflowError`). Not recoverable; let them kill the thread.
- **DON'T** put checked exceptions in lambdas/`Stream` pipelines — they don't
  compile there. Wrap in an unchecked exception, or handle inside the lambda.
- **DON'T** overuse checked exceptions; unrecoverable ones just force noise
  `catch` blocks. When in doubt, prefer unchecked.

### Exception anti-patterns

- **DON'T swallow.** Never `catch (X e) {}` or log-and-continue as if nothing
  happened. Either recover, or rethrow (wrapped). A bare `printStackTrace()` is
  not handling.
- **DON'T catch `Exception`/`Throwable`/`RuntimeException` broadly.** You'll
  bury bugs and, with `Throwable`, swallow `Error` and `InterruptedException`.
  Catch the narrowest type you can act on.
- **DON'T use exceptions for control flow.** Throwing to break a loop or signal
  "not found" is slow (stack capture) and hides intent. Return a value / `Optional`.
- **DON'T catch-and-rethrow the same exception** with no added context — pure clutter.
- **DON'T lose the stack trace.** `throw new AppException(e.getMessage())` drops
  the cause. Pass `e` as the cause (see wrapping).
- **DO restore interrupt status:** on a `catch (InterruptedException e)` you don't
  rethrow, call `Thread.currentThread().interrupt();`.

```java
// DON'T
try { return Integer.parseInt(s); } catch (NumberFormatException e) { return -1; } // silent
// DO — collapse multiple types (multi-catch, Java 7+)
try { risky(); }
catch (IOException | SQLException e) { throw new ServiceException("load failed", e); }
```

### try-with-resources & AutoCloseable

Any `AutoCloseable` (Java 7+) is closed automatically at block exit — normal or
exceptional. `Closeable extends AutoCloseable`.

- **DO** use try-with-resources for every resource (streams, JDBC, locks-as-wrappers,
  your own handles). It replaces `finally { x.close(); }` and gets suppression right.
- **DO** declare multiple resources in one header; they close in **reverse order**
  of declaration (last opened, first closed).
- **DO** reuse an existing `final`/effectively-final variable in the header —
  **Java 9+** (JEP 213). Before 9 you must declare a fresh variable.
- **DON'T** hand-roll `finally`-close: a `try`-body exception plus a `close()`
  exception makes `finally` *mask* the original. try-with-resources suppresses instead.

```java
// Java 9+: effectively-final resource in header
var conn = dataSource.getConnection();
try (conn; var ps = conn.prepareStatement(SQL)) {   // ps closes first, then conn
    ps.execute();
}
// Java 7/8: must declare in-header
try (Connection c = ds.getConnection(); PreparedStatement ps = c.prepareStatement(SQL)) { ... }
```

Implementing `AutoCloseable`:

- **DO** narrow the throws: `close()` is declared `throws Exception`, but declare
  concrete `close()` as `throws IOException` or nothing. Broad throws infects callers.
- **DO** make `close()` idempotent (mark closed, no-op on repeat) — strongly
  encouraged by the API; and relinquish/mark before any throw.
- **DON'T** throw `InterruptedException` from `close()` — suppression of it
  corrupts interrupt handling.

### Optional vs exceptions

`Optional<T>` (Java 8+) models *expected absence* without `null` or throwing.

- **DO** use `Optional` as a **return type** for "no result" lookups.
- **DON'T** use `Optional` for fields, method **parameters**, or collection
  elements (use an empty collection). Per the API note it is "primarily intended
  for use as a method return type."
- **DON'T** let an `Optional` reference be `null`. Never `Optional.of(null)` —
  use `Optional.ofNullable(x)`.
- **DON'T** call `get()` unguarded. Prefer `orElseThrow()` (no-arg, **Java 10+**),
  `orElse`, `orElseGet(supplier)`, `map`, `ifPresentOrElse` (**Java 9+**), or
  `isEmpty()` (**Java 11+**).
- **DO** throw (not return `Optional.empty()`) when absence is a genuine error the
  caller can't proceed past — e.g. required config missing.

```java
return repo.findById(id).orElseThrow(() -> new NotFoundException(id));   // present-or-throw
String name = user.map(User::name).orElse("anon");                       // absence -> default
```

### Wrapping & chaining

Preserve the original cause across abstraction boundaries.

- **DO** wrap low-level checked exceptions in a domain exception and pass the cause:
  `throw new RepoException("saving order " + id, e);` — chaining constructor
  `Throwable(String, Throwable)`.
- **DO** add context (ids, params) in the message; the cause keeps the stack.
- **DON'T** wrap without a reason (e.g. `RuntimeException` around a `RuntimeException`).
- **DON'T** wrap and *then* log the same failure at every layer — log once, at the
  boundary that decides the outcome.
- Use `getCause()` to inspect, `initCause()` only when a constructor can't take the cause.

### Cleanup ordering & suppressed exceptions

- Resources close in **reverse initialization order**.
- If the body throws and a `close()` also throws, the **body exception propagates**
  and each `close()` failure is attached via `Throwable.addSuppressed()` (Java 7+).
  Retrieve with `getSuppressed()`. (Plain `finally` does the opposite — it *loses*
  the primary exception.)

```java
try (var a = open("a"); var b = open("b")) {
    throw new RuntimeException("boom");   // primary
}   // b.close() then a.close(); any failures -> primary.getSuppressed()
```

- **DON'T** rethrow from a plain `catch`/`finally` such that you drop the in-flight
  exception. If you must clean up manually and both can throw, capture the primary
  and `primary.addSuppressed(closeEx)` yourself.

### Sources

- [Java Tutorials — Exceptions (Oracle)](https://docs.oracle.com/javase/tutorial/essential/exceptions/) — checked vs unchecked bottom-line rule, try-with-resources, suppressed & chained exceptions
- [AutoCloseable API — Java SE 25 (Oracle)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/AutoCloseable.html) — `close() throws Exception`, idempotency, narrow-throws & no-`InterruptedException` guidance, vs `Closeable`
- [Optional API — Java SE 25 (Oracle)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Optional.html) — return-type API note; since-versions: `orElseThrow()` 10, `isEmpty()` 11, `ifPresentOrElse`/`or`/`stream` 9
- [JLS SE 25 §14.20.3 — try-with-resources (Oracle)](https://docs.oracle.com/javase/specs/jls/se25/html/jls-14.html#jls-14.20.3) — reverse close order, suppressed-exception semantics
- JEP 213: Milling Project Coin (JDK 9) — effectively-final variables permitted as try-with-resources resources
- [dev.java — Exceptions](https://dev.java/learn/exceptions/) — modern handling guidance

## Performance & GC <a id="performance-and-gc"></a>

Senior-reviewer checklist. Measure before you tune; the JVM's defaults are good. Version-adaptive: modern target is Java 25 (LTS), with fallbacks for 8/11/17/21.

### Choosing a collector

DO let ergonomics pick unless you have a measured latency/throughput goal. On server-class hardware the default is **G1** (default since Java 9, JEP 248). On small/single-core machines ergonomics may pick **Serial**.

DO map the collector to the goal:
- **G1** (`-XX:+UseG1GC`) — default. Balanced pause/throughput, pause target via `-XX:MaxGCPauseMillis` (default 200). Start here.
- **Parallel** (`-XX:+UseParallelGC`) — max throughput for batch/offline work where multi-second pauses are fine.
- **ZGC** (`-XX:+UseZGC`) — low latency: sub-millisecond, heap-size-independent pauses, heaps up to ~16 TB. Trades some throughput.
- **Serial** (`-XX:+UseSerialGC`) — tiny heaps (≤~100 MB), single core, containers with 1 CPU.

DON'T switch collectors as a first move. First adjust heap size (`-Xmx`), verify GC is actually the bottleneck (check logs), *then* try another collector.

DON'T reach for CMS — removed in Java 14 (JEP 363). Its replacement for low pauses is ZGC (or G1).

#### ZGC generational status (verify against your JDK)
- **Java 21**: Generational ZGC added as opt-in (JEP 439) via `-XX:+UseZGC -XX:+ZGenerational`.
- **Java 23**: generational mode became the **default** for `-XX:+UseZGC` (JEP 474).
- **Java 24+ (incl. 25)**: non-generational mode **removed** (JEP 490). `-XX:+UseZGC` is always generational; `-XX:+ZGenerational` is obsolete — DON'T pass it.

```
# Java 25 low-latency service
java -XX:+UseZGC -Xmx8g -Xlog:gc*:file=gc.log:tags,uptime -jar app.jar
```

### Heap & allocation

DO size the heap explicitly in production; don't rely on the fraction default. In containers prefer `-XX:MaxRAMPercentage` over hardcoded `-Xmx` so the JVM tracks the cgroup limit.

DO keep allocation rate low on hot paths — allocation, not collection, is usually the real cost. Fewer short-lived objects → fewer young GCs.

DON'T set `-Xmx` larger than needed "to be safe": bigger heaps mean longer G1/Parallel pauses (ZGC is the exception — its pauses are heap-independent).

DON'T pool ordinary objects to "avoid GC." The young generation makes short-lived allocation nearly free; pools add contention and bugs. Pool only genuinely expensive resources (threads, connections, direct buffers).

DO trust **escape analysis**: the JIT can stack-allocate/scalar-replace objects that don't escape a method, eliminating the allocation entirely — but only after C2 has compiled the method, and only for non-escaping objects. Don't hand-inline to "help" it.

### JIT / warmup

DO account for warmup. Code runs interpreted, then C1, then **C2**-optimized after enough invocations. First calls are 10–100× slower. Warm up before measuring anything.

DON'T draw conclusions from a cold `main()` timing or a single run — you're measuring the interpreter, not steady state.

DO consider AppCDS / (Java 19+) project-level startup features and, if startup latency matters, tiered-compilation tuning — but measure first.

### Collections

DO pre-size when the count is known: `new ArrayList<>(expected)`, `HashMap<>(expected)` (or `HashMap.newHashMap(n)` on Java 19+ to size by entry count, not capacity). Avoids rehash/copy churn.

DO pick by access pattern: `ArrayList` for index/iterate, `ArrayDeque` for stack/queue (not `Stack`/`LinkedList`), `HashMap` for lookup, `EnumMap`/`EnumSet` for enum keys.

DO use factory methods for small fixed data: `List.of(...)`, `Map.of(...)` (Java 9+) — compact and immutable.

DON'T use `LinkedList` as a default list, or `Vector`/`Hashtable`/`Stack` (legacy, synchronized). For concurrency use `ConcurrentHashMap`.

### Records & immutability

DO use **records** (final since Java 16, JEP 395) for immutable data carriers — DTOs, keys, tuples, value-like results. They give correct `equals`/`hashCode`/`toString` and communicate immutability, which enables safe sharing across threads without locks.

```java
record Point(int x, int y) {}   // Java 16+
```

DON'T assume records are faster — they aren't magic; the win is correctness, immutability, and thread-safety. On Java 8–15 fall back to a final class with explicit fields + Objects.equals/hash.

### Measuring — the hard rule

DON'T micro-optimize without a benchmark. Hand-written timing loops lie (dead-code elimination, constant folding, warmup, GC noise).

DO use **JMH** (github.com/openjdk/jmh) for micro/nano benchmarks. Bootstrap with the Maven archetype; consume results via `Blackhole` to defeat dead-code elimination.

```java
@State(Scope.Thread)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Fork(1) @Warmup(iterations = 5) @Measurement(iterations = 5)
public class MyBench {
  @Benchmark
  public void hot(Blackhole bh) { bh.consume(doWork()); }
}
```

DO profile the real application, not a synthetic loop, for end-to-end work:
- **JFR** (Flight Recorder, JEP 328, Java 11+; free): `-XX:StartFlightRecording=duration=60s,filename=rec.jfr`, or programmatically via `jdk.jfr.consumer.RecordingStream` (JEP 349, Java 14+) for live event streaming. Analyze in JDK Mission Control.
- **async-profiler** — low-overhead CPU/alloc/lock sampling with flame graphs; avoids the safepoint-bias of naive samplers.

DO turn on GC logging in production to diagnose pauses: unified logging `-Xlog:gc*` (Java 9+, JEP 271). On Java 8 the old flags are `-XX:+PrintGCDetails -XX:+PrintGCDateStamps`.

DON'T optimize on a hunch: measure → find the dominant cost → change one thing → re-measure.

### Sources

- [Java 25 GC Tuning Guide — Available Collectors](https://docs.oracle.com/en/java/javase/25/gctuning/available-collectors.html)
- [Java 25 GC Tuning Guide — Introduction & Ergonomics](https://docs.oracle.com/en/java/javase/25/gctuning/introduction-garbage-collection-tuning.html)
- [Java 25 JFR API (jdk.jfr) documentation](https://docs.oracle.com/en/java/javase/25/jfapi/)
- [OpenJDK ZGC wiki](https://wiki.openjdk.org/display/zgc/Main)
- JEP 248: Make G1 the Default Garbage Collector (Java 9) — https://openjdk.org/jeps/248
- JEP 271: Unified GC Logging (Java 9) — https://openjdk.org/jeps/271
- JEP 328: Flight Recorder (Java 11) — https://openjdk.org/jeps/328
- JEP 349: JFR Event Streaming (Java 14) — https://openjdk.org/jeps/349
- JEP 363: Remove the Concurrent Mark Sweep (CMS) Garbage Collector (Java 14) — https://openjdk.org/jeps/363
- JEP 395: Records (Java 16) — https://openjdk.org/jeps/395
- JEP 439: Generational ZGC (Java 21) — https://openjdk.org/jeps/439
- JEP 474: ZGC: Generational Mode by Default (Java 23) — https://openjdk.org/jeps/474
- JEP 490: ZGC: Remove the Non-Generational Mode (Java 24) — https://openjdk.org/jeps/490
- [JMH — Java Microbenchmark Harness](https://github.com/openjdk/jmh)
- [async-profiler](https://github.com/async-profiler/async-profiler)

## Build & testing <a id="build-and-testing"></a>

Senior-reviewer checklist. Target Java 25 LTS; fall back per baseline. Verify version facts against docs, never memory.

### Build tool: Maven vs Gradle

DO reach for **Maven** on library/corporate multi-module projects wanting a fixed, declarative lifecycle (`validate → compile → test → package → verify → install`). Convention over config; less to break.
DO reach for **Gradle** for faster incremental builds (build cache, configuration cache), custom build logic, polyglot (Android/Kotlin), or large monorepos. Prefer the **Kotlin DSL** (`build.gradle.kts`) for type safety.
DO commit and invoke the **wrapper** — `./mvnw` / `./gradlew` — so every machine builds with the pinned tool version; never the global `mvn`/`gradle`.
DON'T mix both tools in one module or hand-edit lockfiles.
- Verify: Maven `./mvnw -q verify`; Gradle `./gradlew build`.

### Pin the JDK (toolchains + release)

DO decouple the JDK that *runs the build* from the JDK you *compile/test against* via **toolchains** — CI can run on 25 while targeting 17.

Gradle: `java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }`. Add the Foojay resolver in `settings.gradle.kts` for auto-download: `id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"`.
Maven: `maven-toolchains-plugin` (`toolchain` goal) reads `~/.m2/toolchains.xml` mapping `<provides>` (version+vendor) → `<jdkHome>`.

DO set the bytecode target with **`--release N`** (JDK 9+): compiles *and* links against that release's API, catching accidental use of newer APIs. Maven `<maven.compiler.release>17</maven.compiler.release>`; Gradle `tasks.withType<JavaCompile>{ options.release = 17 }`.
DON'T use `<source>/<target>` (or `sourceCompatibility/targetCompatibility` alone) — they don't restrict the API surface, so code compiles but fails at runtime on the older JVM.

### Reproducible / deterministic builds

DO set `project.build.outputTimestamp` (Maven) or `preserveFileTimestamps=false` + `isReproducibleFileOrder=true` on jar/zip tasks (Gradle) for byte-identical archives.
DO pin every plugin and dependency to an exact version; forbid ranges and `LATEST`/`RELEASE`/dynamic `+`. Lock: Gradle `dependencyLocking`; Maven `maven-enforcer-plugin` (`requireReleaseDeps`).
DON'T let the build read wall-clock, hostname, or env into artifacts.

### Dependency hygiene

DO import a **BOM** in `dependencyManagement` (Maven) / `platform(...)` (Gradle) to align a family's versions; then declare deps *without* versions.
```groovy
testImplementation platform("org.junit:junit-bom:5.14.4")
testImplementation "org.junit.jupiter:junit-jupiter"
```
DO run `mvn dependency:tree` / `gradle dependencies` + enforcer `dependencyConvergence` to kill conflicting transitive versions.
DO scope correctly: `test`/`testImplementation` for test-only; `provided`/`compileOnly` for container-supplied APIs; prefer `implementation` over `api` (Gradle) to limit transitive leakage.
DON'T ship deps with known CVEs — wire an audit (OWASP dependency-check, Renovate/Dependabot).

### JUnit 5 (Jupiter) structure

Versions: latest 5.x is **5.14.4** (Java 8+). **JUnit 6.x** (6.1.1) needs **Java 17+** — same Jupiter model; move when your baseline is 17+.

DO organize with lifecycle + display:
```java
@DisplayName("OrderService")
class OrderServiceTest {
  @BeforeEach void setUp() { /* fresh fixture per test */ }
  @Test void placesOrder() { /* ... */ }
  @Nested @DisplayName("when out of stock") class OutOfStock { @Test void rejects() {} }
}
```
DO use `assertAll(...)` to report every failed assertion at once; `assertThrows(X.class, () -> ...)` for exceptions; `@Timeout` for bounds; `@TempDir Path dir` for auto-cleaned filesystem work.
DON'T rely on test ordering or shared mutable static state. DON'T use `@TestInstance(PER_CLASS)` unless you want one instance per class (enables non-static `@BeforeAll`/`@MethodSource`).
DON'T keep JUnit 4 (`org.junit.Test`) in new code — migrate; run legacy via the Vintage engine only during transition.

### Parameterized & data-driven

DO collapse near-identical tests into `@ParameterizedTest`:
```java
@ParameterizedTest @ValueSource(ints = {1, 2, 3})
void positive(int n) { assertThat(n).isPositive(); }
```
- `@CsvSource` / `@CsvFileSource` for tabular rows; `@EnumSource` for enums; `@MethodSource("factory")` / `@FieldSource("fixtures")` for complex objects (`Stream<Arguments>` / static field).
- `@NullSource`, `@EmptySource`, `@NullAndEmptySource` for edge inputs.
- **`@ParameterizedClass`** (introduced **JUnit 5.13**, still `@API` **EXPERIMENTAL** in 6.x — don't rely on API stability) parameterizes a whole class, not one method.
DON'T loop over cases inside a single `@Test` — you lose per-case reporting.

### AssertJ (assertions)

DO make assertions fluent with AssertJ (3.27.x). One static import: `import static org.assertj.core.api.Assertions.*;`.
```java
assertThat(orders).hasSize(2).extracting("id").containsExactly(1L, 2L);
assertThatThrownBy(() -> svc.load(null))
    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("id");
```
DO use `containsExactlyInAnyOrder`, `extracting`, `satisfies`, `usingRecursiveComparison().ignoringFields(...)` for deep checks, and `assertThatCode(...).doesNotThrowAnyException()`. Group with `SoftAssertions`/`assertSoftly` for all failures at once.
DON'T write `assertThat(a.equals(b))` — it asserts nothing; use `.isEqualTo(b)`. DON'T put `.as(...)`/`.withFailMessage(...)` *after* the terminal assertion — it's a no-op.

### Mockito (mocks)

DO wire JUnit 5 via the extension (adds `mockito-junit-jupiter`):
```java
@ExtendWith(MockitoExtension.class)
class Test { @Mock Repo repo; @InjectMocks Service svc; }
```
Mockito 5.x requires **Java 11+** (stay on Mockito 4.x for Java 8). Stub with `when(repo.find(id)).thenReturn(x)` or BDD `given(...).willReturn(...)`; verify with `verify(repo).save(any())`; capture with `@Captor ArgumentCaptor<T>`.
DO keep default **strict stubbing** (via the extension) — it fails on unused stubs. Use `mockStatic(...)`/`mockConstruction(...)` (inline default in 5.x) *sparingly* for legacy statics.
DON'T mock types you don't own (wrap them), value objects/DTOs, or everything — over-mocking tests the mock, not the code.

### Testcontainers (integration)

DO use real dependencies in a container instead of in-memory fakes for DB/queue/broker integration tests. Needs Docker; add `org.testcontainers:testcontainers-junit-jupiter` (import `testcontainers-bom`, v2.0.5).
```java
@Testcontainers
class RepoIT {
  @Container static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16");
}
```
DO make the container **`static`** to share one instance across all methods (started once); use an **instance** field only when each test needs a fresh one. Reuse the singleton pattern across classes to cut startup; keep IT tests sequential (parallel is unsupported).
DON'T point ITs at shared/staging infra, or run them as unit tests — bind to `*IT` + Failsafe (`verify`), not Surefire (`test`).

### What to test (and not)

DO test: business/domain logic, branch + boundary cases, error paths, serialization contracts, and one integration test per external boundary (DB, HTTP, queue). Prefer many fast unit tests + a thin layer of ITs (the pyramid); keep tests deterministic, isolated, order- and network-independent.
DON'T test framework/library internals, trivial getters/setters, generated code, or private methods directly (test via the public API). DON'T chase 100% coverage — assert behavior, not lines.

### Sources

- Maven Guides: https://maven.apache.org/guides/
- Maven Toolchains: https://maven.apache.org/guides/mini/guide-using-toolchains.html
- Maven Compiler `--release`: https://maven.apache.org/plugins/maven-compiler-plugin/
- Gradle User Guide: https://docs.gradle.org/current/userguide/userguide.html
- Gradle Java Toolchains: https://docs.gradle.org/current/userguide/toolchains.html
- JUnit 5 User Guide: https://docs.junit.org/current/user-guide/
- JUnit 5.13 Release Notes (@ParameterizedClass): https://docs.junit.org/5.13.0/release-notes/
- AssertJ Docs: https://assertj.github.io/doc/
- Mockito: https://site.mockito.org/
- Testcontainers for Java: https://java.testcontainers.org/
- Testcontainers JUnit 5: https://java.testcontainers.org/test_framework_integration/junit_5/

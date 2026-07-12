# Java — core digest

DO target Java 25 (LTS, GA 2025-09-16); compile `--release N` to your real baseline. Never use a feature before its final release.
DO use records (final 16) for data; sealed types (17) + exhaustive `switch` pattern matching (21) over instanceof chains.
DO try-with-resources for all Closeables; `var` only for obvious locals. DO use `java.time` (not Date/Calendar) and parameterized SQL (never concat).
DON'T catch Exception/Throwable broadly or swallow it — add context, keep cause. DON'T use raw types, `==` on objects, mutable static state, or `System.exit` in libraries.

Concurrency: 21+ use virtual threads via `Executors.newVirtualThreadPerTaskExecutor()` for blocking I/O; 8-17 use a bounded platform-thread pool. Never spawn unbounded threads or block inside CompletableFuture chains.

Version cue: 21+ virtual threads+records+sealed+switch-patterns; 17 records+sealed; 8-11 bounded pools, no records. Default GC: G1 (ZGC for low-latency).
Commands: Maven `mvn -q verify`; Gradle `./gradlew build` / `./gradlew test`.

Deep dive when writing non-trivial Java — read lore/java/{versions,language-and-idioms,concurrency,async-and-reactive,io-and-servers,errors-and-resources,performance-and-gc,build-and-testing}.md

Sources: openjdk.org/projects/jdk/25; docs.oracle.com/en/java/javase/25 (+gctuning); JEP 395 Records, 409 Sealed Classes, 441 Pattern Matching for switch, 444 Virtual Threads.

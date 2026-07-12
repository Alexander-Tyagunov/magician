# Java — Language & idioms

Senior-reviewer checklist for modern Java. Target **Java 25 (LTS)**; fallbacks noted per baseline. Feature = *finalized* release, not preview.

## Records (JEP 395, final Java 16)

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

## Sealed types (JEP 409, final Java 17)

DO seal a hierarchy you control to make it a closed algebraic type; each permitted subtype must be `final`, `sealed`, or `non-sealed`, and (unnamed module) in the same package/module.
```java
sealed interface Shape permits Circle, Square {}
record Circle(double r) implements Shape {}
record Square(double s) implements Shape {}
```
DO pair sealed + records + switch for exhaustive, `default`-free matching (compiler enforces coverage).
DON'T use `non-sealed` unless you genuinely want open extension — it reopens the hierarchy.

**Java 8–16:** no language support. Enforce with package-private constructors + a controlled subclass set, or an enum-of-subtypes; document the closed set.

## Pattern matching

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

## Text blocks (JEP 378, final Java 15)

DO use `"""` for multi-line SQL/JSON/HTML; align the closing `"""` to set the left margin (incidental whitespace is stripped). Use `\` to suppress a newline, `\s` to keep trailing space.
DON'T build multi-line strings with `+"\n"`. **Java 8–14:** concatenation or `String.join("\n", ...)`.

## var (JEP 286, Java 10)

DO use `var` for locals when the initializer makes the type obvious (`var users = new ArrayList<User>();`).
DON'T use it when it hides the type (`var x = getThing();`), on `null`/no initializer, or for fields/params/returns (not allowed there anyway).

## Enums

DO put behavior on enums (constant-specific methods, fields, constructors); use `EnumMap`/`EnumSet` over `HashMap`/`HashSet` for enum keys.
DON'T use `ordinal()` for persistence or logic — order changes break you; store `name()` or an explicit code.

## Generics & wildcards

DO apply **PECS**: `? extends T` for producers you read, `? super T` for consumers you write — `void copy(List<? super T> dst, List<? extends T> src)`.
DO prefer generic methods/bounded types over raw types; never use raw `List`.
DON'T create generic arrays or rely on runtime type args (erasure) — pass a `Class<T>` token if needed.

## Optional (Java 8; `Optional.stream()` Java 9)

DO use `Optional` only as a **return type** for "maybe absent". Chain `map`/`filter`/`flatMap`/`ifPresent`.
DO prefer `orElseGet(supplier)` over `orElse(expensive())` (arg is always evaluated); `orElseThrow()` over `get()`.
DON'T use `Optional` for fields, parameters, collection elements, or map values; DON'T call `get()` unguarded or return `null` from an `Optional` method. Return empty collections, not `Optional<Collection>`.

## Immutability, equals/hashCode/toString

DO make fields `final`, copy in/out defensively, expose no setters, prefer unmodifiable collections.
DO keep `equals`/`hashCode` in lockstep (equal ⇒ equal hashCodes; same fields in both); make `equals` reflexive/symmetric/transitive/consistent. Records give this free.
DON'T mutate fields used in `equals`/`hashCode` while the object is a key; DON'T leak secrets in `toString`.

## Comparable / Comparator

DO build comparators with combinators (Java 8): `Comparator.comparing(User::name).thenComparingInt(User::age).reversed()`; `nullsFirst`/`nullsLast` for nullable keys.
DON'T hand-roll `a - b` comparisons — overflow reorders; use `Integer.compare`. Keep `compareTo` consistent with `equals`.

## Streams & Collectors

DO stream for declarative bulk transforms; keep lambdas pure and side-effect-free.
DO collect immutably: `stream.toList()` (Java 16+, unmodifiable) or `Collectors.toUnmodifiableList()` (Java 10+). Pre-16 use `Collectors.toList()` (mutable, no type/serializability guarantee).
DON'T mutate external state in `forEach` or use `peek` for logic; DON'T reuse a consumed stream. Avoid `parallel()` unless the source splits well, work is large/CPU-bound, and ops are stateless/associative.
DON'T stream when a plain loop is clearer or hotter — index iteration, early exit, or single-pass mutation often reads better and allocates less.

**Java 8–15:** `collect(Collectors.toList())`; wrap with `Collections.unmodifiableList(...)` when you need immutability.

## Collections choice

DO pick by access pattern: `ArrayList` (default list, random access), `ArrayDeque` (stack/queue — not `Stack`/`LinkedList`), `HashMap`/`HashSet` (default), `LinkedHashMap` (insertion/LRU order), `TreeMap`/`TreeSet` (sorted), `EnumMap`/`EnumSet` (enum keys), `ConcurrentHashMap` (concurrent — not `Collections.synchronizedMap`).
DO create small immutables with `List.of`/`Set.of`/`Map.of` (JEP 269, Java 9) — reject nulls and duplicates.
DON'T use legacy `Vector`/`Hashtable`/`Stack`. DON'T size-blind: pass initial capacity for large known-size maps/lists.

## Sources

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

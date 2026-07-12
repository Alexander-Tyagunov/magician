# Java — Errors & resources

Senior-reviewer checklist for exceptions, resources, and absence. Version notes
mark the release that *finalized* each feature.

## Checked vs unchecked

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

## Exception anti-patterns

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

## try-with-resources & AutoCloseable

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

## Optional vs exceptions

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

## Wrapping & chaining

Preserve the original cause across abstraction boundaries.

- **DO** wrap low-level checked exceptions in a domain exception and pass the cause:
  `throw new RepoException("saving order " + id, e);` — chaining constructor
  `Throwable(String, Throwable)`.
- **DO** add context (ids, params) in the message; the cause keeps the stack.
- **DON'T** wrap without a reason (e.g. `RuntimeException` around a `RuntimeException`).
- **DON'T** wrap and *then* log the same failure at every layer — log once, at the
  boundary that decides the outcome.
- Use `getCause()` to inspect, `initCause()` only when a constructor can't take the cause.

## Cleanup ordering & suppressed exceptions

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

## Sources

- [Java Tutorials — Exceptions (Oracle)](https://docs.oracle.com/javase/tutorial/essential/exceptions/) — checked vs unchecked bottom-line rule, try-with-resources, suppressed & chained exceptions
- [AutoCloseable API — Java SE 25 (Oracle)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/AutoCloseable.html) — `close() throws Exception`, idempotency, narrow-throws & no-`InterruptedException` guidance, vs `Closeable`
- [Optional API — Java SE 25 (Oracle)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Optional.html) — return-type API note; since-versions: `orElseThrow()` 10, `isEmpty()` 11, `ifPresentOrElse`/`or`/`stream` 9
- [JLS SE 25 §14.20.3 — try-with-resources (Oracle)](https://docs.oracle.com/javase/specs/jls/se25/html/jls-14.html#jls-14.20.3) — reverse close order, suppressed-exception semantics
- JEP 213: Milling Project Coin (JDK 9) — effectively-final variables permitted as try-with-resources resources
- [dev.java — Exceptions](https://dev.java/learn/exceptions/) — modern handling guidance

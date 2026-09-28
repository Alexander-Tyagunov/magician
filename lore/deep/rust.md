# Rust — deep dive

> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

> On-demand companion to `lore/rust.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Ownership, Borrowing & Error Handling](#ownership-and-errors) · [Type Safety & Defensive Programming](#type-safety) · [Performance](#performance) · [Async Rules](#async) · [Design Patterns, Anti-Patterns & API Design](#patterns-and-api) · [Clippy & Lints](#clippy-lints)

## Ownership, Borrowing & Error Handling <a id="ownership-and-errors"></a>

### 1. Ownership and Borrowing

#### DO: Accept borrowed types in function arguments
Prefer `&str` over `&String`, `&[T]` over `&Vec<T>`, `&T` over `&Box<T>`. The borrowed type is strictly more flexible.

```rust
fn process(name: &str) { /* ... */ }
fn sum(values: &[i32]) -> i32 { values.iter().sum() }
```

#### DO: Use `mem::take` / `mem::replace` instead of cloning owned values in enums
To move a field out of a `&mut` reference, use `mem::take` (if `Default`) or `mem::replace` to swap in a placeholder — zero allocation.

```rust
if let MyEnum::A { name, .. } = e {
    *e = MyEnum::B { name: mem::take(name) };
}
```

#### DO: Move ownership when the caller does not need the value afterward
If a function should own data, take it by value. Do not clone then pass.

```rust
consume(config); // not: consume(config.clone())
```

#### DO: Return consumed arguments on error
When a fallible function takes ownership, return it inside the error variant so the caller can retry without cloning.

```rust
pub fn send(value: String) -> Result<(), SendError> {
    if fails() { return Err(SendError(value)); }
    Ok(())
}
```

#### DO: Use `*_mut` insertion methods (Rust 1.95+)
`Vec::push_mut`, `Vec::insert_mut`, `VecDeque::push_{front,back}_mut`, `LinkedList::push_{front,back}_mut` return `&mut T` to the inserted element. Prefer over the two-step `push` + `last_mut().unwrap()`, which requires an `unwrap`/`expect` that `unwrap_used = "deny"` forbids.

```rust
let last = v.push_mut(x); // not: v.push(x); v.last_mut().expect(...)
```

#### DON'T: Use a single lifetime to parameterize both inputs and stored references
When a function takes an input reference AND a `&mut` collection that stores references, sharing one lifetime is usually wrong. The `&mut` makes the lifetime **invariant**, forcing one `'a` for every call site: it compiles and isolated tests pass, but a real caller reusing the collection across disjoint scopes fails (`error[E0597]`). Verified against `rustc 1.94`.

```rust
// BAD: 'a parameterizes both the input and the cached values.
fn first_word<'a>(s: &'a str, cache: &mut HashMap<String, &'a str>) -> &'a str { /* ... */ }

// GOOD: store owned values when the collection outlives any single input
fn first_word<'a>(s: &'a str, cache: &mut HashMap<String, String>) -> &'a str { /* ... */ }

// GOOD: or split lifetimes with an explicit outlives bound when borrowing is required
fn first_word<'cache, 'input: 'cache>(
    s: &'input str, cache: &mut HashMap<String, &'cache str>,
) -> &'cache str { /* ... */ }
```

Rule of thumb: whenever you add explicit lifetimes, sketch a real caller with disjoint scopes. If `'a` appears inside both a `&mut` and the stored data, it is invariant. Prefer owned storage, or split with an explicit outlives bound.

#### DON'T: Clone to satisfy the borrow checker
If the borrow checker rejects your code, the fix is almost never `.clone()`. Restructure ownership, use borrowing, or decompose the struct.

When `.clone()` IS acceptable:
- Cloning `Arc<T>` / `Rc<T>` (refcount bump, not deep copy)
- `Copy` types (`i32`, `bool`) — cheap stack copies
- Rare, proven-necessary deep copies in non-hot paths
- Tests and prototypes

### 2. Error Handling

#### DO: Propagate errors with `?`
Use `?` to propagate. Define typed errors with `thiserror`, or use `anyhow` for application code.

```rust
fn read_config(path: &str) -> Result<String, std::io::Error> {
    std::fs::read_to_string(path)
}
```

#### DO: Use `unwrap_or`, `unwrap_or_else`, `unwrap_or_default` for fallbacks

```rust
let port = config.get("port").unwrap_or(&"8080");
```

#### DON'T: Use `unwrap()` / `expect()` in library code
They panic on failure, crashing the thread. Reserve for:
- Tests (`#[cfg(test)]`)
- Proven invariants with a comment explaining why it cannot fail
- Prototypes that will be replaced

```rust
// Return a Result instead of panicking:
pub fn parse_port(s: &str) -> Result<u16, std::num::ParseIntError> { s.parse() }
```

#### DO: Use `TryFrom` when conversion can fail, not `From`
If your `From` impl contains `unwrap`, `expect`, or a default fallback for error cases, it should be `TryFrom`.

```rust
impl TryFrom<&str> for Port {
    type Error = std::num::ParseIntError;
    fn try_from(s: &str) -> Result<Self, Self::Error> { Ok(Port(s.parse()?)) }
}
```

#### DO: Use `bool::try_from(n)` for strict 0/1 wire fields (Rust 1.95+)
At boundaries where the encoding is "strictly 0 or 1, anything else is malformed" (single-byte flags, protocol bitfields stored as bytes, strict JSON `0`/`1`), prefer `bool::try_from(n)?` over `n != 0`. The `!= 0` form silently accepts `2`, `42`, `0xFF` as `true`, hiding upstream corruption.

```rust
let enabled = bool::try_from(flag_byte)
    .map_err(|_| DecodeError::InvalidFlag { value: flag_byte })?;
```

Keep plain `!= 0` only when you specifically mean "any nonzero is truthy" (e.g. a C-style int documented that way).

## Type Safety & Defensive Programming <a id="type-safety"></a>

### DO: Use the newtype pattern for domain types

Wrap primitives to prevent mixing semantically different values. Zero-cost at runtime.

```rust
struct AccountId(u64);
struct Amount(u64);
fn transfer(from: AccountId, to: AccountId, amount: Amount) {}
```

### DO: Force construction through validated constructors

Make struct fields private; require a `new()` that validates. Prevents invalid state.

```rust
pub struct Port { value: u16, _private: () } // _private blocks external struct literals

impl Port {
    pub fn new(value: u16) -> Result<Self, &'static str> {
        if value == 0 { return Err("port cannot be zero"); }
        Ok(Self { value, _private: () })
    }
}
```

For library crates, use `#[non_exhaustive]` to prevent external construction and signal fields may be added:

```rust
#[non_exhaustive]
pub struct Config { pub timeout: Duration, pub retries: u32 }
```

### DO: Use `#[must_use]` on important return types

Prevents callers from accidentally ignoring results.

```rust
#[must_use = "config must be applied to take effect"]
pub struct Config { /* ... */ }
```

**Note (Rust 1.97+):** the `must_use` lint now sees through infallible result-like wrappers — `Result<T, Uninhabited>` and `ControlFlow<Uninhabited, T>` (error/break arm is `!` or `core::convert::Infallible`) are treated as `T`. Wrapping a `#[must_use]` value in a can't-fail `Result` no longer silently loses the check. (Clippy applied the same to `double_must_use` and `let_underscore_must_use` in 1.95.)

### DO: Use enums instead of boolean parameters

Booleans are unreadable at the call site and error-prone.

```rust
// BAD: process_data(&data, true, false, true);
// GOOD:
enum Compression { Strong, None }
enum Encryption { Aes, None }
enum Validation { Enabled, Disabled }
fn process_data(data: &[u8], c: Compression, e: Encryption, v: Validation) {}
```

For many options, use a parameter struct with preset constructors (`ProcessParams::production()`, `::development()`).

### DO: Use exhaustive `match` — avoid wildcard catch-all

Wildcard `_` hides new variants added later.

```rust
// BAD: _ => {}  hides future variants
// GOOD: list every variant so the compiler forces you to handle new ones
match status {
    Status::Active => handle_active(),
    Status::Inactive => handle_inactive(),
    Status::Pending => handle_pending(),
    Status::Suspended => handle_suspended(),
}

// OK: explicitly group variants with shared logic
Status::Inactive | Status::Suspended => handle_disabled(),
```

**Note (Rust 1.95+):** `if let` guards in `match` arms (stabilized 1.95) do **NOT** participate in exhaustiveness checking — same as plain `if` guards. Do not use an `if let` guard as justification for removing a previously-required wildcard; the compiler still requires an exhaustive listing or a `_` arm.

### DO: Use slice pattern matching instead of index + length check

Decoupling length check from indexing creates implicit invariants the compiler cannot enforce.

```rust
// BAD: if !users.is_empty() { let first = &users[0]; }  // panics if refactored
// GOOD:
match users.as_slice() {
    [] => handle_empty(),
    [single] => handle_one(single),
    [first, rest @ ..] => handle_many(first, rest),
}
```

### DO: Destructure structs in trait impls for future-proofing

When implementing `PartialEq`, `Hash`, `Debug`, etc. manually, destructure so a new field causes a compile error until addressed.

```rust
impl PartialEq for Order {
    fn eq(&self, other: &Self) -> bool {
        let Self { item, quantity, timestamp: _ } = self;
        let Self { item: other_item, quantity: other_qty, timestamp: _ } = other;
        item == other_item && quantity == other_qty
    }
}
```

### DO: Name unused destructured variables descriptively

```rust
// BAD: Rocket { _, _, .. } => {}
// GOOD:
match rocket { Rocket { has_fuel: _, has_crew: _, .. } => {} }
```

### DON'T: Use `..Default::default()` lazily

It silently fills new fields with defaults, hiding bugs when fields are added later.

```rust
// BAD:
let config = Config { timeout: Duration::from_secs(30), ..Default::default() };

// GOOD: explicit about every field
let config = Config { timeout: Duration::from_secs(30), retries: 3, verbose: false };

// ACCEPTABLE: destructure default first for visibility
let Config { timeout, retries, verbose } = Config::default();
let config = Config { timeout: Duration::from_secs(30), retries, verbose };
```

## Performance <a id="performance"></a>

### DON'T: Clone gratuitously

Every `.clone()` on a heap type (`String`, `Vec<T>`) allocates. In hot paths this is a top performance killer.

```rust
// BAD: needless clone for a HashMap lookup
fn lookup(key: String, map: &HashMap<String, String>) -> Option<&String> {
    let k = key.clone();
    map.get(&k)
}

// GOOD: HashMap<String, _> accepts &str lookups
fn lookup(key: &str, map: &HashMap<String, String>) -> Option<&String> {
    map.get(key)
}
```

### DON'T: Use redundant wrapper types

```rust
Box<Vec<T>>    // just use Vec<T>
Box<String>    // just use String
Arc<String>    // use Arc<str>
```

### DON'T: Collect into Vec just to iterate again

```rust
// BAD: allocates a Vec for no reason
let v: Vec<_> = iter.collect();
for x in v { process(x); }

// GOOD: iterate directly
for x in iter { process(x); }
```

### DON'T: Use `String::from` / `format!` for static content when `&str` suffices

```rust
// BAD: heap allocation for a constant
let msg = String::from("hello");
let msg = format!("hello");

// GOOD
let msg: &str = "hello";
```

### DO: Use `format!` for string concatenation with mixed content

`format!` is more readable than manual `push_str` chains. For hot paths, pre-allocate with `String::with_capacity` and `push_str`.

```rust
// Readable: mixed content
let greeting = format!("Hello, {name}! You have {count} items.");

// Fast: hot paths
let mut s = String::with_capacity(64);
s.push_str("Hello, ");
s.push_str(name);
```

### DO: Allocate large buffers via `Vec`, not `Box::new([0; N])`

`Box::new([0u8; N])` builds the array **on the stack first**, then moves it to the heap — overflows the stack in debug, brittle in release (an intermediate `let` can materialize the stack copy and crash).

```rust
// BAD: stack overflow in debug, brittle in release
let buf = Box::new([0u8; 1024 * 1024]);

// GOOD: heap allocation guaranteed by Vec
let buf: Box<[u8]> = vec![0u8; 1024 * 1024].into_boxed_slice();
```

Matters most on embedded (small task stacks). For any buffer >= 1 KB inside an embassy task, allocate via `Vec` / `Box::<[u8]>::new_uninit_slice` (with explicit `assume_init`) or a static `StaticCell` — never `Box::new([0; N])` or a stack-local array bound to a `let`.

### DO: Use temporary mutability pattern

Constrain mutability to initialization, then shadow as immutable.

```rust
let data = {
    let mut data = get_vec();
    data.sort();
    data // returned immutable
};
```

### DO: Prefer std bit-manipulation methods over hand-rolled equivalents (Rust 1.97+)

Rust 1.97 stabilized `const fn` bit helpers on every integer type and on `NonZero<_>`. Prefer them over hand-rolled shift / mask / `leading_zeros` arithmetic: branch-free, intent-explicit, and free of the off-by-one and zero-input traps.

| Method | Returns |
|--------|---------|
| `n.bit_width()` | `u32` — min bits to represent `n`; `0` for `0` |
| `n.isolate_highest_one()` | value with only the top set bit kept; `0` for `0` |
| `n.isolate_lowest_one()` | value with only the bottom set bit kept; `0` for `0` |
| `n.highest_one()` | `Option<u32>` — index of top set bit; `None` for `0` |
| `n.lowest_one()` | `Option<u32>` — index of bottom set bit; `None` for `0` |

```rust
// BAD: hand-rolled, underflows at x == 0
let top_bit_mask = 1u32 << (u32::BITS - 1 - x.leading_zeros());
let width = u32::BITS - x.leading_zeros();

// GOOD (Rust 1.97+): zero handled, all const fn
let top_bit_mask = x.isolate_highest_one();
let width = x.bit_width();
```

`isolate_*_one` returns the **bit itself** (a mask); `highest_one` / `lowest_one` return the **index** as `Option<u32>`. MSRV note: adopting these raises your minimum toolchain to 1.97 — honor your MSRV policy first.

### DO: Use `ptr::read_unaligned` (or `from_le_bytes`) for multi-byte reads from `&[u8]`

Safe Rust never produces unaligned loads (references are always aligned). The hazard appears **only in `unsafe` code that casts `*const u8` to `*const u16`/`u32`/etc.** On RISC-V (e.g. `riscv32imc` / `riscv32imac`) an unaligned load either traps and is emulated (10–100x slower) or panics with `LoadStoreMisaligned`.

```rust
// BAD: UB on strict-alignment targets — &[u8] is only 1-byte aligned. Compiles, runs on x86, traps on RISC-V.
let value: u16 = unsafe { *(buf.as_ptr().add(2) as *const u16) };
let value: u16 = unsafe { core::ptr::read(buf.as_ptr().add(2) as *const u16) };

// GOOD: safe, no unsafe
let value = u16::from_le_bytes(buf[2..4].try_into().unwrap());

// GOOD: unsafe escape hatch when slice-to-array is awkward (FFI struct copy-out).
// SAFETY: must justify provenance and bounds.
let value: u16 = unsafe { core::ptr::read_unaligned(buf.as_ptr().add(2) as *const u16) };
```

Rules:

- For multi-byte reads out of `&[u8]`, prefer `u16::from_le_bytes(slice.try_into().unwrap())` (or `from_be_bytes`). Bounds-check the slice once and reuse it.
- If you must use raw pointers (FFI struct read-out, `repr(C)` overlay), use `core::ptr::read_unaligned` — never `ptr::read` or `*ptr` on a cast pointer.
- This bug class is **invisible on x86 CI** — unaligned loads succeed silently on host machines; the trap fires only on target hardware. Code review is the primary defense.
- `bytemuck::pod_read_unaligned` is a safe wrapper for `Pod` types if you want zero `unsafe`.

## Async Rules <a id="async"></a>

### DON'T: Call blocking I/O in async functions

Blocking calls (`std::fs`, `std::net`, heavy computation) stall the runtime's worker thread and starve other tasks. Use async I/O; for unavoidable blocking use `spawn_blocking`.

```rust
// BAD: blocks the Tokio runtime
async fn read_config(path: &str) -> String {
    std::fs::read_to_string(path).unwrap()
}

// GOOD: async I/O
tokio::fs::read_to_string(path).await

// GOOD: unavoidable blocking
tokio::task::spawn_blocking(move || expensive_hash(&data)).await
```

### DO: Use `tokio::select!` for cancellation and timeouts

```rust
tokio::select! {
    result = do_work() => handle_result(result),
    _ = tokio::time::sleep(Duration::from_secs(30)) => {
        tracing::warn!("operation timed out");
    }
}
```

### DON'T: Hold locks across `.await` points

`std::sync::Mutex` is not async-aware. Holding it across `.await` blocks the whole thread if another task tries to acquire it. Minimize lock scope, or use `tokio::sync::Mutex` when the guard must live across `.await`.

```rust
// BAD
let guard = mutex.lock().unwrap();
do_async_work().await;
drop(guard);

// GOOD: drop before await
{
    let guard = mutex.lock().unwrap();
    let data = guard.clone();
}
do_async_work_with(data).await;

// OR: use tokio::sync::Mutex when you must hold across await
let guard = async_mutex.lock().await;
do_async_work().await;
```

**LLM-bias note.** LLM-generated async code defaults to `std::sync::Mutex` (dominant in training data). Review every `Mutex` import in async modules:

- `tokio` tasks: `tokio::sync::Mutex` when the guard may live across `.await`; `std::sync::Mutex` only for strictly synchronous, short critical sections.
- embassy / `no_std`: `embassy_sync::mutex::Mutex` for async-aware locks. `embassy_sync::blocking_mutex::Mutex` (with `CriticalSectionRawMutex`) only when the critical section never `.await`s.
- `clippy::await_holding_lock` catches the obvious case but does NOT see through helper-function returns, struct fields, or `MutexGuard::map`. Necessary but not sufficient.

### DO: Use `tokio::task::yield_now()` in CPU-bound async loops

If you must do CPU work in an async context, yield periodically to avoid starving other tasks.

### DO: Annotate every async fn with cancel safety (cancel-safe / NOT cancel-safe)

Futures are cancellable at **every** `.await` point. Any future used inside `tokio::select!`, `tokio::time::timeout`, `embassy_futures::select`, or `JoinHandle::abort` can be dropped between awaits, leaving partial state. Cancel safety is **not expressible in the type system** — no `CancelSafe` marker trait exists; it lives only in documentation. LLM-generated code almost never raises this. Treat the annotation as mandatory.

```rust
// NOT cancel-safe: if dropped between insert() and send_ack(), we wrote to the
// DB but never acknowledged — client retries and we duplicate.
async fn process(stream: TcpStream, db: &Db) -> Result<()> {
    let data = read_message(&stream).await?;
    db.insert(&data).await?;       // if cancelled here, dup on retry
    send_ack(&stream).await?;
    Ok(())
}

// GOOD: isolate the non-cancel-safe section so outer cancellation can't tear it.
let handle = tokio::spawn(async move {
    db.insert(&data).await?;
    send_ack(&stream).await?;
    Ok::<_, Error>(())
});
handle.await?
```

Rules:

- Every async fn that may run inside `select!`, `timeout`, or an `abort`-able task MUST carry a `// cancel-safe: <reason>` or `// NOT cancel-safe: <reason>` doc comment. No exceptions.
- "All awaits are idempotent" is NOT a valid reason — idempotency is about retries, not partial state between awaits.
- Consult tokio docs per call. E.g. `AsyncReadExt::read` is cancel-safe, `read_exact` is NOT.
- embassy: `embassy_futures::select` cancels the losing branch by dropping its future — same rules apply.

### DO: Audit Drop impls of async resources (transactions, connections, guards)

Drop runs on every exit path, including panics and cancellation. For types returned from `.await` (DB transactions, pooled connections, async file handles), Drop may perform I/O — which in an async runtime can run blocking code on a worker thread or silently no-op.

```rust
// Subtle: commit() can itself fail, leaving tx in an indeterminate drop state.
//   - sqlx: Drop queues a rollback that runs on the *next* async use of the
//     connection (or on pool return); if nothing drives it, rollback never runs.
//   - deadpool-postgres: deferred cleanup via the connection's background task;
//     rollback may not run if the runtime is shutting down.
async fn run(pool: &Pool) -> Result<Data> {
    let tx = pool.get().await?.transaction().await?;
    match do_work(&tx).await {
        Ok(result) => { tx.commit().await?; Ok(result) }
        Err(e)     => { tx.rollback().await?; Err(e) }
    }
}
```

Rules:

- For every async resource type you `.await` into scope, know what its Drop does — read the source, not just the docs.
- Prefer explicit `commit` / `rollback` / `close` on every path. Do not rely on Drop to clean up async work.
- If Drop is the only cleanup path, document it at the call site.

## Design Patterns, Anti-Patterns & API Design <a id="patterns-and-api"></a>

### Design Patterns to USE

#### Builder Pattern
For complex object construction, especially since Rust lacks default arguments and overloading.

```rust
let server = ServerBuilder::new().port(8080).max_connections(100).build()?;
```

#### RAII Guards
Tie resource lifecycle to scope; the guard's `Drop` ensures cleanup on early return or panic.

```rust
let _guard = acquire_lock(&resource); // released when _guard drops
```

#### Strategy Pattern via Traits or Closures
Traits for polymorphic behavior; closures for lightweight strategies.

```rust
trait Formatter { fn format(&self, data: &Data) -> String; }
fn process<F: Fn(&Data) -> String>(data: &Data, format: F) -> String { format(data) }
```

#### Struct Decomposition for Independent Borrowing
When the borrow checker blocks borrowing different fields, decompose into smaller structs so each field borrows independently.

```rust
struct Server { config: ServerConfig, state: ServerState }
```

#### Newtype for Implementing Foreign Traits
When the orphan rule blocks `impl ForeignTrait for ForeignType`, wrap in a newtype.

```rust
struct AuditFile(Arc<File>);
impl io::Write for AuditFile { /* delegate to self.0 */ }
```

#### Closure Variable Rebinding
Control what a closure captures by rebinding in a scope block.

```rust
let handler = {
    let db = Arc::clone(&db);     // clone Arc, not the database
    move |req| handle(req, &db)
};
```

#### `cfg_select!` for Compile-Time Selection (Rust 1.95+)
Stable compile-time `match`-like macro replacing the `cfg-if` crate. Prefer in new code; do not proactively migrate existing `cfg-if` usages.

```rust
cfg_select! {
    unix => { fn init() { /* unix */ } }
    windows => { fn init() { /* windows */ } }
    _ => { fn init() { /* fallback */ } }
}
```

#### `Default` + `new()` Constructors
Implement both. `Default` enables `unwrap_or_default()` and generic containers; `new()` is the expected constructor convention.

```rust
#[derive(Default)]
pub struct Config { pub timeout: Duration, pub retries: u32 }
impl Config { pub fn new(timeout: Duration, retries: u32) -> Self { Self { timeout, retries } } }
```

---

### Anti-Patterns to AVOID

#### Deref Polymorphism (Fake Inheritance)
Do not implement `Deref` to emulate OO inheritance. `Deref` is for smart pointers and collections, not "struct B extends struct A".

```rust
// BAD: fake inheritance via Deref
impl Deref for Bar { type Target = Foo; fn deref(&self) -> &Foo { &self.foo } }

// GOOD: explicit delegation or trait-based composition
impl Bar { fn method(&self) { self.foo.method() } }
```

Why it is wrong: surprises readers (implicit conversion), creates no subtype relationship, traits on `Foo` are not available for `Bar`, and it breaks generic programming and bounds checking.

#### `#![deny(warnings)]` in Source Code
Opts you out of Rust's stability guarantees — new compiler versions may add warnings that break your build.

```rust
// BAD: in source code
#![deny(warnings)]

// GOOD: deny a specific, curated set
#![deny(unused, dead_code)]
```

Enforce "no warnings" at the CI boundary. **Rust 1.97+** stabilized Cargo's `build.warnings` config — cache-friendly (unlike `RUSTFLAGS`) and local-packages-only.

```toml
# .cargo/config.toml
[build]
warnings = "deny"     # "warn" (default) | "allow" | "deny"
```

Caveat: `build.warnings` gates rustc's `warnings` lint group only. The `linker_messages` lint (Rust 1.97+) is deliberately not in that group — escalate it separately.

#### Blanket Impls in Public APIs (Semver Hazard)
`impl<T: SomeBound> MyTrait for T` in a published crate is a semver hazard: a downstream `impl MyTrait for Foo` that compiles today can break on future versions via coherence errors, surfacing only on the consumer's CI.

```rust
// GOOD: seal the trait so only this crate can impl it
pub trait MyTrait: sealed::Sealed { fn do_it(&self) -> String; }
mod sealed { pub trait Sealed {} }
impl sealed::Sealed for String {}
impl MyTrait for String { fn do_it(&self) -> String { self.clone() } }
```

Rules:
- Blanket impls in `pub` trait-or-type combinations require the trait to be **sealed** (private supertrait pattern).
- If the trait is meant to be implementable downstream, write per-type impls in this crate — no blanket impls.
- Internal (`pub(crate)` or smaller) blanket impls are fine.

#### Overreliance on `String` in APIs
Accept `&str` for reading, `impl Into<String>` for ownership transfer.

```rust
// BAD
fn greet(name: String) -> String { format!("Hello, {name}") }

// GOOD
fn greet(name: &str) -> String { format!("Hello, {name}") }

// GOOD: when you need ownership
fn set_name(&mut self, name: impl Into<String>) { self.name = name.into(); }
```

---

### API Design

#### DO: Accept `impl Into<String>` for owned string parameters
Flexible — accepts `&str`, `String`, `Cow`, etc.

```rust
pub fn new(name: impl Into<String>) -> Self { Self { name: name.into() } }
```

#### DO: Return `Result` from constructors that validate

```rust
pub fn new(port: u16) -> Result<Self, ConfigError> {
    if port == 0 { return Err(ConfigError::InvalidPort); }
    Ok(Self { port })
}
```

#### DO: Use builder pattern for configs with many optional fields
See Builder Pattern above.

#### DON'T: Use more than 3-4 boolean parameters
Replace booleans with descriptive enums or a parameter struct.

#### DON'T: Expose internal types in public APIs
Wrap third-party types so you can swap implementations without breaking callers.

## Clippy & Lints <a id="clippy-lints"></a>

### Recommended Clippy Lints

```toml
[lints.clippy]
all = "deny"
pedantic = "warn"
nursery = "warn"   # AI-generated code: catches patterns pedantic misses; expect noise
```

### Defensive Programming Lints

```toml
[lints.clippy]
indexing_slicing = "deny"          # prefer .get() or pattern matching
fallible_impl_from = "deny"        # From impls that should be TryFrom
wildcard_enum_match_arm = "deny"   # no catch-all _ in enums
fn_params_excessive_bools = "deny"
must_use_candidate = "warn"        # suggest #[must_use]
unneeded_field_pattern = "warn"
await_holding_lock = "deny"        # held std/parking_lot guard across .await (obvious case only)
cast_ptr_alignment = "deny"        # *const u8 as *const u16 — UB on RISC-V
```

### Panic Prevention Lints

A server process must never panic in production.

```toml
[lints.clippy]
unwrap_used = "deny"      # use ?, unwrap_or, etc.
expect_used = "warn"      # still panics
panic = "deny"
todo = "deny"             # panics at runtime
unimplemented = "deny"
unreachable = "warn"      # prefer compiler-proven unreachable via match
```

- `unwrap_used = "deny"` is stricter than "no unwrap in library code": for a server binary, panics in *any* path crash the process.
- Exceptions only via `#[allow(clippy::unwrap_used)]` + comment justifying why the value is guaranteed `Some`/`Ok`.
- Clippy 1.95 added an `allow-unwrap-types` config key — DON'T enable it; fix the call site or add a local `#[allow]`.

### Debug Artifact Prevention Lints

Use `tracing` for all output.

```toml
[lints.clippy]
dbg_macro = "deny"      # use tracing::debug!
print_stdout = "deny"   # use tracing::info!
print_stderr = "deny"   # use tracing::error!
```

### Complexity Lints

```toml
[lints.clippy]
cognitive_complexity = "warn"
too_many_lines = "warn"
```

### String Handling Lints

```toml
[lints.clippy]
string_to_string = "warn"   # String::to_string() — already a String
str_to_string = "warn"      # prefer .to_owned() or .into()
```

### Library Crate Hygiene Lints

```toml
[lints.clippy]
exhaustive_enums = "warn"     # public enums should use #[non_exhaustive]
exhaustive_structs = "warn"   # public structs should use #[non_exhaustive]
```

### Performance-Related Clippy Lints

```toml
[lints.clippy]
redundant_clone = "warn"
implicit_clone = "warn"          # .to_owned()/.to_string() where clone suffices
needless_pass_by_value = "warn"
large_enum_variant = "warn"      # consider boxing large variants
box_collection = "warn"          # Box<Vec<T>> -> Vec<T>
rc_buffer = "warn"               # Rc<String> -> Rc<str>
clone_on_ref_ptr = "warn"        # Arc::clone(&x) over x.clone()
```

Clippy 1.95 added two `complexity`-tier lints already covered by `clippy::all = "deny"` (no separate declaration):
- `manual_checked_ops` — prefer `checked_add`/`checked_sub`/`checked_mul` over hand-rolled overflow checks.
- `manual_take` — prefer `std::mem::take(&mut x)` over `mem::replace(&mut x, Default::default())`.

### General Quality Lints

```toml
[lints.rust]
missing_debug_implementations = "warn"
trivial_casts = "warn"
trivial_numeric_casts = "warn"
unused_extern_crates = "warn"
unused_import_braces = "warn"
unused_qualifications = "warn"
```

### Crate-Level Safety Lints

```toml
[lints.rust]
unsafe_code = "forbid"           # forbid unsafe entirely if not needed
unreachable_pub = "warn"         # pub items not reachable from crate root
missing_docs = "warn"            # at minimum for public API (library crates)
dead_code_pub_in_binary = "warn" # Rust 1.97+: unused pub items in a binary (opt in for bins)
```

- `unsafe_code = "forbid"` in every crate that doesn't need unsafe. Crates that require it: `unsafe_code = "deny"` + `#[allow(unsafe_code)]` per item with a safety comment.
- `missing_docs`: promote to `"deny"` once docs are complete. `dead_code_pub_in_binary` (Rust 1.97+, allow-by-default): opt in for binaries; leave off for libraries.

### Linker Diagnostics (Rust 1.97+)

Rust 1.97 surfaces linker stderr via a warn-by-default `linker_messages` lint. High-signal for crates that link C libs (libopus, mbedTLS, OpenSSL) or use a custom linker script.

```toml
[lints.rust]
linker_messages = "warn"   # escalate to "deny" only once known-clean on every target
```

- NOT part of the `warnings` group — neither `RUSTFLAGS="-D warnings"` nor `build.warnings = "deny"` affects it; set its level explicitly.
- Platform-dependent and advisory; pin proven-benign noise to `"allow"` with a comment naming platform + message.

### Lints for LLM-generated code

Minimum surface targeting failure modes that pass `cargo build` and `cargo test` on LLM-written Rust.

```toml
[lints.clippy]
await_holding_lock = "deny"        # held std MutexGuard across .await
await_holding_refcell_ref = "deny" # held RefCell borrow across .await
cast_ptr_alignment = "deny"        # *const u8 as *const u16; ptr::read on unaligned
transmute_ptr_to_ref = "deny"      # mem::transmute hiding lifetime laundering
not_unsafe_ptr_arg_deref = "deny"  # safe fn that deref's a caller-provided ptr
mem_forget = "deny"                # leaks Drop; almost always a bug
large_stack_arrays = "warn"        # arrays > clippy threshold on the stack
large_stack_frames = "warn"        # functions with large local frames
```

Also high-signal on LLM code (already covered by pedantic + nursery): `clippy::ptr_as_ptr`, `clippy::cast_lossless`, `clippy::redundant_clone`, `clippy::needless_pass_by_value`.

Limitations:
- `await_holding_lock` only catches guards visibly alive across `.await` in the same fn; guards from a helper, struct field, or `MutexGuard::map` slip past.
- `cast_ptr_alignment` misses non-obvious misaligned pointers (e.g. `slice::from_raw_parts` with a hand-computed offset).
- No clippy lint for blanket-impl semver hazards or async cancel safety — prose-only rules. Enforce `cargo +nightly miri test` for files with `unsafe`; Miri is the only reliable catch for UB that passes clippy.

### DO: Use `cargo fmt` for consistent formatting

```bash
cargo fmt --all -- --check   # CI: fail on unformatted code
cargo fmt --all              # local: auto-format
```

### DO: Configure `rustfmt.toml` for import organization

```toml
# rustfmt.toml
imports_granularity = "Crate"      # group imports by crate, not individual items
group_imports = "StdExternalCrate" # separate std, external, and crate imports
```

### DO: Profile before optimizing

```bash
cargo flamegraph --bin my-server
tokio-console   # for async code
```

**Symbol mangling (Rust 1.97+):** 1.97 switched the default mangling scheme to `v0`. If a profiler shows raw `_R...` symbols, update it (or `rustfilt`) to a v0-aware version. Tooling-compatibility note only — no runtime change.

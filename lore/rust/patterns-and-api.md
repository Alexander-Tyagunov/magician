> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Design Patterns, Anti-Patterns & API Design

## Design Patterns to USE

### Builder Pattern
For complex object construction, especially since Rust lacks default arguments and overloading.

```rust
let server = ServerBuilder::new().port(8080).max_connections(100).build()?;
```

### RAII Guards
Tie resource lifecycle to scope; the guard's `Drop` ensures cleanup on early return or panic.

```rust
let _guard = acquire_lock(&resource); // released when _guard drops
```

### Strategy Pattern via Traits or Closures
Traits for polymorphic behavior; closures for lightweight strategies.

```rust
trait Formatter { fn format(&self, data: &Data) -> String; }
fn process<F: Fn(&Data) -> String>(data: &Data, format: F) -> String { format(data) }
```

### Struct Decomposition for Independent Borrowing
When the borrow checker blocks borrowing different fields, decompose into smaller structs so each field borrows independently.

```rust
struct Server { config: ServerConfig, state: ServerState }
```

### Newtype for Implementing Foreign Traits
When the orphan rule blocks `impl ForeignTrait for ForeignType`, wrap in a newtype.

```rust
struct AuditFile(Arc<File>);
impl io::Write for AuditFile { /* delegate to self.0 */ }
```

### Closure Variable Rebinding
Control what a closure captures by rebinding in a scope block.

```rust
let handler = {
    let db = Arc::clone(&db);     // clone Arc, not the database
    move |req| handle(req, &db)
};
```

### `cfg_select!` for Compile-Time Selection (Rust 1.95+)
Stable compile-time `match`-like macro replacing the `cfg-if` crate. Prefer in new code; do not proactively migrate existing `cfg-if` usages.

```rust
cfg_select! {
    unix => { fn init() { /* unix */ } }
    windows => { fn init() { /* windows */ } }
    _ => { fn init() { /* fallback */ } }
}
```

### `Default` + `new()` Constructors
Implement both. `Default` enables `unwrap_or_default()` and generic containers; `new()` is the expected constructor convention.

```rust
#[derive(Default)]
pub struct Config { pub timeout: Duration, pub retries: u32 }
impl Config { pub fn new(timeout: Duration, retries: u32) -> Self { Self { timeout, retries } } }
```

---

## Anti-Patterns to AVOID

### Deref Polymorphism (Fake Inheritance)
Do not implement `Deref` to emulate OO inheritance. `Deref` is for smart pointers and collections, not "struct B extends struct A".

```rust
// BAD: fake inheritance via Deref
impl Deref for Bar { type Target = Foo; fn deref(&self) -> &Foo { &self.foo } }

// GOOD: explicit delegation or trait-based composition
impl Bar { fn method(&self) { self.foo.method() } }
```

Why it is wrong: surprises readers (implicit conversion), creates no subtype relationship, traits on `Foo` are not available for `Bar`, and it breaks generic programming and bounds checking.

### `#![deny(warnings)]` in Source Code
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

### Blanket Impls in Public APIs (Semver Hazard)
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

### Overreliance on `String` in APIs
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

## API Design

### DO: Accept `impl Into<String>` for owned string parameters
Flexible — accepts `&str`, `String`, `Cow`, etc.

```rust
pub fn new(name: impl Into<String>) -> Self { Self { name: name.into() } }
```

### DO: Return `Result` from constructors that validate

```rust
pub fn new(port: u16) -> Result<Self, ConfigError> {
    if port == 0 { return Err(ConfigError::InvalidPort); }
    Ok(Self { port })
}
```

### DO: Use builder pattern for configs with many optional fields
See Builder Pattern above.

### DON'T: Use more than 3-4 boolean parameters
Replace booleans with descriptive enums or a parameter struct.

### DON'T: Expose internal types in public APIs
Wrap third-party types so you can swap implementations without breaking callers.

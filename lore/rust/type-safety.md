> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Type Safety & Defensive Programming

## DO: Use the newtype pattern for domain types

Wrap primitives to prevent mixing semantically different values. Zero-cost at runtime.

```rust
struct AccountId(u64);
struct Amount(u64);
fn transfer(from: AccountId, to: AccountId, amount: Amount) {}
```

## DO: Force construction through validated constructors

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

## DO: Use `#[must_use]` on important return types

Prevents callers from accidentally ignoring results.

```rust
#[must_use = "config must be applied to take effect"]
pub struct Config { /* ... */ }
```

**Note (Rust 1.97+):** the `must_use` lint now sees through infallible result-like wrappers — `Result<T, Uninhabited>` and `ControlFlow<Uninhabited, T>` (error/break arm is `!` or `core::convert::Infallible`) are treated as `T`. Wrapping a `#[must_use]` value in a can't-fail `Result` no longer silently loses the check. (Clippy applied the same to `double_must_use` and `let_underscore_must_use` in 1.95.)

## DO: Use enums instead of boolean parameters

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

## DO: Use exhaustive `match` — avoid wildcard catch-all

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

## DO: Use slice pattern matching instead of index + length check

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

## DO: Destructure structs in trait impls for future-proofing

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

## DO: Name unused destructured variables descriptively

```rust
// BAD: Rocket { _, _, .. } => {}
// GOOD:
match rocket { Rocket { has_fuel: _, has_crew: _, .. } => {} }
```

## DON'T: Use `..Default::default()` lazily

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

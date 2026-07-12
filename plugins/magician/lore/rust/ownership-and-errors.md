> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Ownership, Borrowing & Error Handling

## 1. Ownership and Borrowing

### DO: Accept borrowed types in function arguments
Prefer `&str` over `&String`, `&[T]` over `&Vec<T>`, `&T` over `&Box<T>`. The borrowed type is strictly more flexible.

```rust
fn process(name: &str) { /* ... */ }
fn sum(values: &[i32]) -> i32 { values.iter().sum() }
```

### DO: Use `mem::take` / `mem::replace` instead of cloning owned values in enums
To move a field out of a `&mut` reference, use `mem::take` (if `Default`) or `mem::replace` to swap in a placeholder — zero allocation.

```rust
if let MyEnum::A { name, .. } = e {
    *e = MyEnum::B { name: mem::take(name) };
}
```

### DO: Move ownership when the caller does not need the value afterward
If a function should own data, take it by value. Do not clone then pass.

```rust
consume(config); // not: consume(config.clone())
```

### DO: Return consumed arguments on error
When a fallible function takes ownership, return it inside the error variant so the caller can retry without cloning.

```rust
pub fn send(value: String) -> Result<(), SendError> {
    if fails() { return Err(SendError(value)); }
    Ok(())
}
```

### DO: Use `*_mut` insertion methods (Rust 1.95+)
`Vec::push_mut`, `Vec::insert_mut`, `VecDeque::push_{front,back}_mut`, `LinkedList::push_{front,back}_mut` return `&mut T` to the inserted element. Prefer over the two-step `push` + `last_mut().unwrap()`, which requires an `unwrap`/`expect` that `unwrap_used = "deny"` forbids.

```rust
let last = v.push_mut(x); // not: v.push(x); v.last_mut().expect(...)
```

### DON'T: Use a single lifetime to parameterize both inputs and stored references
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

### DON'T: Clone to satisfy the borrow checker
If the borrow checker rejects your code, the fix is almost never `.clone()`. Restructure ownership, use borrowing, or decompose the struct.

When `.clone()` IS acceptable:
- Cloning `Arc<T>` / `Rc<T>` (refcount bump, not deep copy)
- `Copy` types (`i32`, `bool`) — cheap stack copies
- Rare, proven-necessary deep copies in non-hot paths
- Tests and prototypes

## 2. Error Handling

### DO: Propagate errors with `?`
Use `?` to propagate. Define typed errors with `thiserror`, or use `anyhow` for application code.

```rust
fn read_config(path: &str) -> Result<String, std::io::Error> {
    std::fs::read_to_string(path)
}
```

### DO: Use `unwrap_or`, `unwrap_or_else`, `unwrap_or_default` for fallbacks

```rust
let port = config.get("port").unwrap_or(&"8080");
```

### DON'T: Use `unwrap()` / `expect()` in library code
They panic on failure, crashing the thread. Reserve for:
- Tests (`#[cfg(test)]`)
- Proven invariants with a comment explaining why it cannot fail
- Prototypes that will be replaced

```rust
// Return a Result instead of panicking:
pub fn parse_port(s: &str) -> Result<u16, std::num::ParseIntError> { s.parse() }
```

### DO: Use `TryFrom` when conversion can fail, not `From`
If your `From` impl contains `unwrap`, `expect`, or a default fallback for error cases, it should be `TryFrom`.

```rust
impl TryFrom<&str> for Port {
    type Error = std::num::ParseIntError;
    fn try_from(s: &str) -> Result<Self, Self::Error> { Ok(Port(s.parse()?)) }
}
```

### DO: Use `bool::try_from(n)` for strict 0/1 wire fields (Rust 1.95+)
At boundaries where the encoding is "strictly 0 or 1, anything else is malformed" (single-byte flags, protocol bitfields stored as bytes, strict JSON `0`/`1`), prefer `bool::try_from(n)?` over `n != 0`. The `!= 0` form silently accepts `2`, `42`, `0xFF` as `true`, hiding upstream corruption.

```rust
let enabled = bool::try_from(flag_byte)
    .map_err(|_| DecodeError::InvalidFlag { value: flag_byte })?;
```

Keep plain `!= 0` only when you specifically mean "any nonzero is truthy" (e.g. a C-style int documented that way).

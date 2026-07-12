> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Performance

## DON'T: Clone gratuitously

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

## DON'T: Use redundant wrapper types

```rust
Box<Vec<T>>    // just use Vec<T>
Box<String>    // just use String
Arc<String>    // use Arc<str>
```

## DON'T: Collect into Vec just to iterate again

```rust
// BAD: allocates a Vec for no reason
let v: Vec<_> = iter.collect();
for x in v { process(x); }

// GOOD: iterate directly
for x in iter { process(x); }
```

## DON'T: Use `String::from` / `format!` for static content when `&str` suffices

```rust
// BAD: heap allocation for a constant
let msg = String::from("hello");
let msg = format!("hello");

// GOOD
let msg: &str = "hello";
```

## DO: Use `format!` for string concatenation with mixed content

`format!` is more readable than manual `push_str` chains. For hot paths, pre-allocate with `String::with_capacity` and `push_str`.

```rust
// Readable: mixed content
let greeting = format!("Hello, {name}! You have {count} items.");

// Fast: hot paths
let mut s = String::with_capacity(64);
s.push_str("Hello, ");
s.push_str(name);
```

## DO: Allocate large buffers via `Vec`, not `Box::new([0; N])`

`Box::new([0u8; N])` builds the array **on the stack first**, then moves it to the heap — overflows the stack in debug, brittle in release (an intermediate `let` can materialize the stack copy and crash).

```rust
// BAD: stack overflow in debug, brittle in release
let buf = Box::new([0u8; 1024 * 1024]);

// GOOD: heap allocation guaranteed by Vec
let buf: Box<[u8]> = vec![0u8; 1024 * 1024].into_boxed_slice();
```

Matters most on embedded (small task stacks). For any buffer >= 1 KB inside an embassy task, allocate via `Vec` / `Box::<[u8]>::new_uninit_slice` (with explicit `assume_init`) or a static `StaticCell` — never `Box::new([0; N])` or a stack-local array bound to a `let`.

## DO: Use temporary mutability pattern

Constrain mutability to initialization, then shadow as immutable.

```rust
let data = {
    let mut data = get_vec();
    data.sort();
    data // returned immutable
};
```

## DO: Prefer std bit-manipulation methods over hand-rolled equivalents (Rust 1.97+)

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

## DO: Use `ptr::read_unaligned` (or `from_le_bytes`) for multi-byte reads from `&[u8]`

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

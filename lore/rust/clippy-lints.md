> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Clippy & Lints

## Recommended Clippy Lints

```toml
[lints.clippy]
all = "deny"
pedantic = "warn"
nursery = "warn"   # AI-generated code: catches patterns pedantic misses; expect noise
```

## Defensive Programming Lints

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

## Panic Prevention Lints

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

## Debug Artifact Prevention Lints

Use `tracing` for all output.

```toml
[lints.clippy]
dbg_macro = "deny"      # use tracing::debug!
print_stdout = "deny"   # use tracing::info!
print_stderr = "deny"   # use tracing::error!
```

## Complexity Lints

```toml
[lints.clippy]
cognitive_complexity = "warn"
too_many_lines = "warn"
```

## String Handling Lints

```toml
[lints.clippy]
string_to_string = "warn"   # String::to_string() — already a String
str_to_string = "warn"      # prefer .to_owned() or .into()
```

## Library Crate Hygiene Lints

```toml
[lints.clippy]
exhaustive_enums = "warn"     # public enums should use #[non_exhaustive]
exhaustive_structs = "warn"   # public structs should use #[non_exhaustive]
```

## Performance-Related Clippy Lints

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

## General Quality Lints

```toml
[lints.rust]
missing_debug_implementations = "warn"
trivial_casts = "warn"
trivial_numeric_casts = "warn"
unused_extern_crates = "warn"
unused_import_braces = "warn"
unused_qualifications = "warn"
```

## Crate-Level Safety Lints

```toml
[lints.rust]
unsafe_code = "forbid"           # forbid unsafe entirely if not needed
unreachable_pub = "warn"         # pub items not reachable from crate root
missing_docs = "warn"            # at minimum for public API (library crates)
dead_code_pub_in_binary = "warn" # Rust 1.97+: unused pub items in a binary (opt in for bins)
```

- `unsafe_code = "forbid"` in every crate that doesn't need unsafe. Crates that require it: `unsafe_code = "deny"` + `#[allow(unsafe_code)]` per item with a safety comment.
- `missing_docs`: promote to `"deny"` once docs are complete. `dead_code_pub_in_binary` (Rust 1.97+, allow-by-default): opt in for binaries; leave off for libraries.

## Linker Diagnostics (Rust 1.97+)

Rust 1.97 surfaces linker stderr via a warn-by-default `linker_messages` lint. High-signal for crates that link C libs (libopus, mbedTLS, OpenSSL) or use a custom linker script.

```toml
[lints.rust]
linker_messages = "warn"   # escalate to "deny" only once known-clean on every target
```

- NOT part of the `warnings` group — neither `RUSTFLAGS="-D warnings"` nor `build.warnings = "deny"` affects it; set its level explicitly.
- Platform-dependent and advisory; pin proven-benign noise to `"allow"` with a comment naming platform + message.

## Lints for LLM-generated code

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

## DO: Use `cargo fmt` for consistent formatting

```bash
cargo fmt --all -- --check   # CI: fail on unformatted code
cargo fmt --all              # local: auto-format
```

## DO: Configure `rustfmt.toml` for import organization

```toml
# rustfmt.toml
imports_granularity = "Crate"      # group imports by crate, not individual items
group_imports = "StdExternalCrate" # separate std, external, and crate imports
```

## DO: Profile before optimizing

```bash
cargo flamegraph --bin my-server
tokio-console   # for async code
```

**Symbol mangling (Rust 1.97+):** 1.97 switched the default mangling scheme to `v0`. If a profiler shows raw `_R...` symbols, update it (or `rustfilt`) to a v0-aware version. Tooling-compatibility note only — no runtime change.

> Source: rmcp-server-kit RUST_GUIDELINES.md — MIT/Apache-2.0 — https://github.com/andrico21/rmcp-server-kit

DO: accept borrowed types (`&str`, `&[T]`); propagate errors with `?`; use newtypes + validated constructors returning `Result`; exhaustive `match` (no wildcard `_`); enums over bool params; `#[must_use]`; `impl Into<String>` for owned params; `TryFrom` for fallible conversions. Annotate every async fn `// cancel-safe:` / `// NOT cancel-safe:`.

DON'T: `unwrap()`/`expect()`/`panic!`/`todo!`/`dbg!`/`println!` in production (use `?`, `unwrap_or`, `tracing`); `.clone()` to dodge the borrow checker; blocking I/O in async fns (use `tokio::fs`, `spawn_blocking`); hold a `std::sync::Mutex` guard across `.await`; lazy `..Default::default()`; `Box<Vec<T>>`/`Arc<String>`; interpolate user input into SQL/paths; hardcode secrets.

Lint hard: `clippy::all = "deny"`; deny `unwrap_used`, `indexing_slicing`, `await_holding_lock`, `cast_ptr_alignment`; `unsafe_code = "forbid"`.

Commands: build `cargo build`, test `cargo test`, lint `cargo clippy`, format `cargo fmt`.

Deep dive when writing non-trivial Rust — read lore/rust/{ownership-and-errors,type-safety,performance,async,patterns-and-api,clippy-lints}.md

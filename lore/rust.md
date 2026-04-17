Common AI mistakes: cloning unnecessarily to avoid borrow issues; panicking with `unwrap()` in production code; not using `?` for error propagation; fighting the borrow checker instead of restructuring.
Commands: build: `cargo build`, test: `cargo test`, lint: `cargo clippy`, format: `cargo fmt`.
Gotchas: `Option<T>` and `Result<T,E>` — always handle both variants; `String` vs `&str` — prefer `&str` in function params; iterators are lazy and zero-cost.

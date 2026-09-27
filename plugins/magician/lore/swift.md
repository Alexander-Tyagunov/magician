Common AI mistakes: retain cycles in closures without `[weak self]`; force unwrapping optionals with `!`; using `class` when `struct` suffices; blocking main thread with sync network calls.
Commands: build: `xcodebuild`, test: `xcodebuild test -scheme <scheme>`.
Gotchas: Combine for reactive patterns (or Swift Concurrency async/await); `actor` for thread-safe mutable state (Swift 5.5+); prefer `struct` for value semantics.

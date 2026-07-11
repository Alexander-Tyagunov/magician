Common AI mistakes: unnecessary null checks with `!!` operator; using Java-style iteration instead of Kotlin idioms; not using data classes for value objects; blocking coroutine with `runBlocking` in production.
Commands: build: `./gradlew build`, test: `./gradlew test`.
Gotchas: `?.let {}` for safe null operations; `when` expression is exhaustive for sealed classes; coroutines with `suspend` functions require a coroutine scope.

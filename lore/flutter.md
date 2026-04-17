Common AI mistakes: calling setState after dispose; blocking the UI thread with sync operations; not using const constructors for immutable widgets; ignoring BuildContext scope.
Commands: test: `flutter test`, build: `flutter build apk`, analyze: `flutter analyze`.
Gotchas: `const` widgets skip rebuild — use wherever possible; `async`/`await` in `initState` requires mounted check; `StreamBuilder` and `FutureBuilder` handle async state.

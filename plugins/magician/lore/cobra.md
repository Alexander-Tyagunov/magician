# Cobra — core digest

Version: Cobra v1.10.x (Dec 2025), `github.com/spf13/cobra` (use a supported Go). Get `@latest`; scaffold via `cobra-cli`.

DO use `RunE`/`PersistentPreRunE` (return errors) not `Run`; check `rootCmd.Execute()` error, exit non-zero.
DO propagate cancellation: `ExecuteContext(ctx)` + `cmd.Context()`; wire `signal.NotifyContext` for Ctrl-C.
DO validate positional args via `Args`: `cobra.ExactArgs`/`MinimumNArgs`/`NoArgs`/`MatchAll`; never trust arg shape.
DO set `SilenceUsage`+`SilenceErrors` true, then print the error once yourself — else usage spams on runtime failures.
DO mark constraints: `MarkFlagRequired`, `MarkFlagsMutuallyExclusive`/`OneRequired`/`RequiredTogether`.
DO scope flags: `Flags()` local vs `PersistentFlags()` cascades. Bind config via viper `BindPFlag`; env via viper, not committed.
DO give each command `Use`/`Short`; add completions (`ValidArgs`, `RegisterFlagCompletionFunc`).

DON'T read secrets from flags/args (leak via `ps`, history, logs) — use env/files; never log secret values.
DON'T `os.Exit` inside `RunE` (skips defers/PostRun) — return the error.
DON'T shell out with unsanitized args; validate/allow-list before exec.
DON'T rely on `init()` globals in tests; build fresh commands so `SetArgs`/`SetOut` isolate.

Commands: root+sub via `AddCommand`; hooks `PersistentPreRunE→PreRunE→RunE→PostRunE→PersistentPostRunE`.

Deep dive when writing non-trivial cobra — read lore/cobra/{commands-and-flags}.md

## Sources
cobra.dev; github.com/spf13/cobra (user_guide, releases); github.com/spf13/viper

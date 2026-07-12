# cobra — Commands, flags & viper

Modern CLI construction in Go. Assumes the Go foundation lore exists separately.

Verified versions (against official docs, 2026-07):
- **Cobra `v1.10.2`** (Dec 2025) — `github.com/spf13/cobra`
- **pflag** — POSIX flags, fork of stdlib `flag`; Cobra uses it internally
- **Viper `v1.21.0`** (Sep 2025) — `github.com/spf13/viper`; "heading towards v2" but v2 is **not** released — target v1.x, don't import a v2 path
- `cobra-cli` is a **separate** module: `github.com/spf13/cobra-cli`

---

## Command tree

DO
- Build one `rootCmd`; attach children with `root.AddCommand(childCmd)`. Nest freely (`app server`, `app db migrate`).
- Set `Use`, `Short`, `Long`. `Use`'s first token is the command name; `[args]` in `Use` is documentation only — enforce with `Args`.
- Put the tree wiring in a constructor func (e.g. `newRootCmd()`), call it from `main`, `Execute()`, exit once.

```go
func main() {
	if err := newRootCmd().Execute(); err != nil {
		os.Exit(1) // the ONLY os.Exit — top level
	}
}
```

DON'T
- **DON'T put logic or flag registration in `init()`.** It runs at import time, is untestable, orders unpredictably, and defeats DI. Register flags in the command constructor.
- DON'T call `Execute()` on a child; call it on root.

---

## Command action: RunE over Run

DO
- Use **`RunE func(cmd *cobra.Command, args []string) error`** and `return err`. Cobra prints it and `Execute()` returns non-nil → single exit point in `main`.
- Silence Cobra's double-printing of errors/usage when you handle output yourself: `cmd.SilenceUsage = true`, `cmd.SilenceErrors = true`.
- Read context via `cmd.Context()`; propagate to gRPC/HTTP/db calls for cancellation.

```go
&cobra.Command{
	Use:   "sync [src]",
	Short: "Sync a source",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return run(cmd.Context(), args[0])
	},
}
```

DON'T
- **DON'T `os.Exit()` inside `RunE`/`Run`** — it skips deferred cleanup and swallows the error path. Return the error.
- DON'T use `Run` (no error return) for anything that can fail; it forces `os.Exit`/`log.Fatal` inside the action.
- DON'T `panic` for user errors; return a plain `error`.

Hooks run in order: `PersistentPreRunE → PreRunE → RunE → PostRunE → PersistentPostRunE`. `PersistentPreRunE` is inherited by children; `PreRunE` is not. By default only the **nearest** persistent hook fires — set `cobra.EnableTraverseRunHooks = true` to run all ancestors'. Use `PersistentPreRunE` for cross-cutting setup (config load, auth), and return errors from it too.

---

## Flags: local vs persistent

DO
- **`cmd.Flags()`** — local, only this command.
- **`cmd.PersistentFlags()`** — inherited by this command and all descendants (put global `--config`, `--verbose` on `rootCmd.PersistentFlags()`).
- Bind to a variable with `...Var`/`...VarP` (P = shorthand), or take the returned pointer.
- `MarkFlagRequired`, `MarkPersistentFlagRequired`, and mutual-exclusion helpers (`MarkFlagsMutuallyExclusive`, `MarkFlagsRequiredTogether`) for validation.

```go
var cfgFile string
root.PersistentFlags().StringVar(&cfgFile, "config", "", "config file")
cmd.Flags().IntP("port", "p", 8080, "listen port")
_ = cmd.MarkFlagRequired("port")
```

DON'T
- DON'T register the same flag name on both a parent's persistent set and a child's local set — collision.
- DON'T read `Flags()` values before `Execute()` parses them.

---

## Args validators

Assign a `cobra.PositionalArgs` to `Command.Args`. Verified set:

| Validator | Meaning |
|---|---|
| `cobra.NoArgs` | error if any positional args |
| `cobra.ArbitraryArgs` | accept any |
| `cobra.OnlyValidArgs` | args must be in `cmd.ValidArgs` |
| `cobra.MinimumNArgs(n)` | at least n |
| `cobra.MaximumNArgs(n)` | at most n |
| `cobra.ExactArgs(n)` | exactly n |
| `cobra.RangeArgs(min, max)` | between min and max |
| `cobra.MatchAll(v...)` | compose validators |

```go
Args: cobra.MatchAll(cobra.ExactArgs(1), cobra.OnlyValidArgs),
```

DO validate/normalize arg *content* inside `RunE` (paths, URLs, IDs) — the validators only check count/membership.
DON'T trust arg count alone as input validation.

---

## Binding flags to Viper

Viper reads config from many sources; bind pflags so a flag can override a config file / env var.

DO
- `viper.BindPFlag("port", cmd.Flags().Lookup("port"))` — one flag → viper key. Bind all: `viper.BindPFlags(cmd.Flags())`.
- Binding is **lazy**: value is read when accessed, not when bound — bind in constructor, read in `RunE`.
- Load env: `viper.SetEnvPrefix("APP")` + `viper.AutomaticEnv()` → `APP_PORT` maps to key `port`. Use `SetEnvKeyReplacer(strings.NewReplacer("-", "_", ".", "_"))` so `log-level`/`db.host` resolve.
- Config file: `SetConfigName("config")`, `AddConfigPath(...)`, then `ReadInConfig()`; tolerate not-found:

```go
if err := viper.ReadInConfig(); err != nil {
	var nf viper.ConfigFileNotFoundError
	if !errors.As(err, &nf) { return err } // real parse error
}
```
- Prefer `Unmarshal(&cfg)` into a struct with `mapstructure:"..."` tags (Viper uses the `github.com/go-viper/mapstructure` fork).

**Precedence (highest→lowest):** explicit `Set` → flags → env → config file → key/value store → defaults. Keys are case-insensitive; **env lookups are case-sensitive**. Typed getters (`GetString`, `GetInt`, `GetBool`) return zero-value when missing — use `IsSet` to distinguish.

DON'T
- DON'T commit config files with secrets; source secrets from env, not the repo.
- DON'T assume `GetX` distinguishes "unset" from "zero" — check `IsSet`.
- DON'T rely on the global Viper singleton in libraries/tests — construct `viper.New()` per command for isolation (singleton may be deprecated in v2).

---

## Shell completions

Cobra auto-registers a `completion` subcommand (bash/zsh/fish/powershell) once root has subcommands.

DO
- Dynamic value completion: set `ValidArgsFunction` (works across all shells) or static `ValidArgs []cobra.Completion`. Only one per command.
- Flag values: `cmd.RegisterFlagCompletionFunc("region", fn)`.
- Return `cobra.ShellCompDirectiveNoFileComp` to suppress file completion; `cobra.NoFileCompletions` as a ready-made.

```go
cmd.ValidArgsFunction = func(_ *cobra.Command, _ []string, _ string) ([]cobra.Completion, cobra.ShellCompDirective) {
	return []cobra.Completion{cobra.CompletionWithDesc("foo", "the foo")}, cobra.ShellCompDirectiveNoFileComp
}
```

DON'T set both `ValidArgs` and `ValidArgsFunction`.

---

## cobra-cli generator

Scaffolds apps and commands. Separate install:

```sh
go install github.com/spf13/cobra-cli@latest
cobra-cli init            # bootstrap rootCmd + main
cobra-cli add serve       # add a subcommand
```

DO use it to bootstrap, then move flag registration out of generated `init()` into constructors if you want testability. DON'T treat generated scaffolding as final architecture.

---

## Ops / security checklist

- Single `os.Exit` in `main`; return errors everywhere else.
- Wire `cmd.Context()` into every network/db call; set deadlines/timeouts.
- Secrets from env (`AutomaticEnv` + prefix), never flags' defaults or committed config; never log secret flag values.
- Validate arg/flag *content* in `RunE`, not just counts.
- Pin `cobra` v1.x and `viper` v1.x in `go.mod`; do not chase an unreleased viper v2.

---

## Sources

- https://github.com/spf13/cobra
- https://cobra.dev/
- https://pkg.go.dev/github.com/spf13/cobra
- https://github.com/spf13/viper
- https://pkg.go.dev/github.com/spf13/pflag
- https://github.com/spf13/cobra-cli

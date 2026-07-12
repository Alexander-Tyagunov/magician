# viper — Config, precedence & pitfalls

`github.com/spf13/viper` — Go config layer over files, env, flags, remote k/v, defaults.
Current: **v1.21.0** (2025-09-08). v2 is planned but not released — build against v1.x.
Assumes the Go foundation lore exists separately.

## Precedence (highest → lowest)

`viper.Set` (explicit) > flag > env var > config file > key/value store > default.

A higher source shadows every lower one. Know which layer a value came from before
debugging "why is my config wrong".

## DO — reading config files

```go
viper.SetConfigName("config")     // base name, no extension
viper.SetConfigType("yaml")       // REQUIRED for extensionless files (e.g. remote/stdin)
viper.AddConfigPath("/etc/appname/")
viper.AddConfigPath("$HOME/.appname")
viper.AddConfigPath(".")          // search order = add order
if err := viper.ReadInConfig(); err != nil {
    var notFound viper.ConfigFileNotFoundError
    if errors.As(err, &notFound) {
        // no file in any search path — often fine, fall back to env/defaults
    } else {
        return fmt.Errorf("read config: %w", err) // malformed file: fail loud
    }
}
```

- DO set defaults for every key: `viper.SetDefault("port", 8080)`.
- DO treat "file not found" (`viper.ConfigFileNotFoundError`) as recoverable; treat parse errors as fatal.
- Formats: JSON, TOML, YAML, INI, envfile, Java properties.

## DO — environment variables

```go
viper.SetEnvPrefix("app")                                   // env lookups become APP_*
viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_", "-", "_")) // db.host -> APP_DB_HOST
viper.AutomaticEnv()                                         // any key -> matching prefixed env
viper.BindEnv("db.host")                                     // explicit, reliable binding
port := viper.GetInt("db.host")
```

- **DO prefer explicit `BindEnv` for anything load-bearing.** `AutomaticEnv` only resolves
  an env var when that exact key is *accessed via `Get`* — it does not enumerate env vars,
  so a key with no default and no config-file entry may never be probed. `BindEnv` guarantees the mapping.
- `BindEnv(key)` → uses `PREFIX_` + uppercased key. `BindEnv(key, ENV1, ENV2...)` → binds
  explicit names in order (prefix ignored when names given).
- Env values are read **lazily at `Get` time**, not cached at bind time. Same for bound flags.

## DO — flags (cobra/pflag)

```go
rootCmd.Flags().Int("port", 8080, "listen port")
viper.BindPFlag("port", rootCmd.Flags().Lookup("port")) // one flag
viper.BindPFlags(rootCmd.Flags())                       // whole set
```

Flag value is resolved lazily at access, and only overrides lower layers when the user
actually changed it (pflag `Changed`). Unchanged flags fall through to env/file/default.

## DO — unmarshal into a struct

```go
type Config struct {
    Port    int           `mapstructure:"port"`
    DBHost  string        `mapstructure:"db_host"`
    Timeout time.Duration `mapstructure:"timeout"` // "5s" decodes via built-in hook
    TLS     TLSConfig     `mapstructure:",squash"` // embed/flatten
}
var c Config
if err := viper.Unmarshal(&c); err != nil { return err }
```

- Uses **`github.com/go-viper/mapstructure/v2`** (the maintained fork, not `mitchellh`).
  Tag is `mapstructure`, not `json`/`yaml`.
- Built-in decode hooks: `string → time.Duration` and comma-`string → []string`.
- DO unmarshal once at startup into a typed struct and pass it down — don't call
  `viper.GetString` scattered across the codebase.

## DO — watch (optional, hot reload)

```go
viper.OnConfigChange(func(e fsnotify.Event) { /* re-read, swap atomically */ })
viper.WatchConfig() // define ALL config paths before calling
```

- Add every `AddConfigPath` **before** `WatchConfig()`.
- Viper is **not** safe for concurrent read/write. Guard shared state; on change, rebuild an
  immutable snapshot and swap it behind a mutex/atomic — don't mutate live config.

## DON'T — the pitfalls

- **DON'T rely on key case.** Config keys are **case-INSENSITIVE** (lowercased internally).
  `Port`, `PORT`, `port` collide. Env var *names*, by contrast, are case-SENSITIVE.
- **DON'T assume `AutomaticEnv` covers every key.** Unaccessed keys are never probed — add
  `BindEnv` for anything required.
- **DON'T forget `SetConfigType`** for files without an extension, stdin, or remote sources —
  Viper can't infer the parser.
- **DON'T treat empty env as a value.** Empty env vars count as *unset* (fall through) unless
  `viper.AllowEmptyEnv(true)`.
- **DON'T mix delimiters blindly.** Nested keys use `.` (`db.host`); override via
  `viper.NewWithOptions(viper.KeyDelimiter("::"))` if keys contain dots.
- **DON'T lean on the global singleton for libraries/tests.** Prefer `v := viper.New()`
  instances; the package-level global may be deprecated in v2.
- **DON'T commit secrets to config files.** Keep tokens, DB passwords, TLS keys in env vars
  (or a secret manager / remote k/v), never in checked-in YAML/JSON. Config files belong in
  VCS; secrets do not. Never log resolved secret values.
- **DON'T guess v2 APIs.** v2 is unreleased; pin v1.x and verify against docs before upgrading.

## Sources

- https://github.com/spf13/viper — README, precedence, env/BindEnv/AutomaticEnv, WatchConfig, v2 status (v1.21.0)
- https://pkg.go.dev/github.com/spf13/viper — signatures (BindEnv/BindPFlag/Unmarshal/WatchConfig), lazy Get semantics, mapstructure v2 fork
- https://github.com/go-viper/mapstructure — mapstructure tags/decode hooks used by Unmarshal

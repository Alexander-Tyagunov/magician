# Viper (core)

Version: v1.x current (v1.21.0, Sep 2025). v2 is aspirational — no release; project favors back-compat, may fix case-insensitivity in v2. Go config lib, pairs with cobra/pflag.

Precedence (high→low): Set() > flags > env > config file > k/v store > SetDefault. Keys case-insensitive; env is case-sensitive & read fresh.

DO
- Create a `*viper.New()` instance and pass it around; avoid the global singleton.
- Always handle `ReadInConfig()` error; distinguish `ConfigFileNotFoundError` from parse errors.
- `SetConfigName`/`SetConfigType`/`AddConfigPath` before read; set all paths before `WatchConfig`.
- Load secrets via `AutomaticEnv`+`SetEnvPrefix`+`BindEnv`; use `SetEnvKeyReplacer` for `.`→`_`.
- `Unmarshal` into structs with `mapstructure` tags; validate required keys yourself.
- Bind flags: `BindPFlags(cmd.Flags())` so CLI overrides config.

DON'T
- Don't commit secrets/config with credentials — inject via env/secret store, not the repo.
- Don't log config dumps; they leak secrets.
- Don't read+write a Viper concurrently — not goroutine-safe, panics. Synchronize.
- Don't assume empty env = set; enable `AllowEmptyEnv(true)` if needed.
- Don't rely on `WatchConfig` for hot secret rotation without re-validation.

Commands: none (library). Config via SetConfigName/AddConfigPath + ReadInConfig; env via AutomaticEnv/SetEnvPrefix; flags via BindPFlags.

Deep dive when writing non-trivial viper — read lore/viper/{config-and-precedence}.md

## Sources
github.com/spf13/viper (README, releases v1.21.0), pkg.go.dev/github.com/spf13/viper

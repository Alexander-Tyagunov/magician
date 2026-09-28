# Claude-side quality gates

These are the plugin's self-tests: the bar a Magician change must clear before it ships. They are
**dependency-free** (Python stdlib `unittest` only — no pytest, no PyYAML) so any team that clones the
plugin can run them with nothing installed. Run the whole gate with:

```bash
bash scripts/gate.sh            # offline tiers (below)
bash scripts/gate.sh --evals    # also run the behavioral suite, claude plugin eval, which spends API budget
```

`scripts/gate.sh` runs, in order:

1. this suite (`tests/claude`);
2. the official validator, strict: `claude plugin validate .claude-plugin/plugin.json --strict` and
   `claude plugin validate . --strict` — skipped with a note when the `claude` CLI isn't installed
   (as in CI);
3. the directory limits: at most 512 tracked files, no non-image file of 256 KiB or more, only text,
   SVG, PNG, JPEG, GIF, WebP and font files, and no OS junk (`.DS_Store`, `Thumbs.db`, `desktop.ini`,
   `__MACOSX`);
4. the behavioral evals, only with `--evals` (or `MAGICIAN_GATE_EVALS=1`).

Or run this tier alone, from the repository root:

```bash
python3 -m unittest discover -s tests/claude -p 'test_*.py'
```

## What each gate proves

| File | Contract |
|------|----------|
| `test_hooks.py` | `hooks/hooks.json` and `monitors/monitors.json` match the exact wiring contract (events, matchers, timeouts, `async`); every command is the quoted literal `"${CLAUDE_PLUGIN_ROOT}"/scripts/<name>.sh` form and points to an executable script; the two session env file writers have their 10-second timeout; removed hooks stay removed. |
| `test_hook_scripts.py` | Every hook script is plain bash 3.2: `LC_ALL=C`, no interpreters, no eval or `source`, no launchers, fetchers or calls to other plugin files, exit 0 except the guard's deliberate block (exit 2), no transcript reads, no settings writes, and only the userConfig bridge and `tools-path.sh` touch `CLAUDE_ENV_FILE` (`tools-path.sh` may also name the plugin's `tools/` folder, to write launchers for it). The pattern-detect, chronicle-stop, format, notify and ci-watch scripts are also run under `/bin/bash` with stubbed tools in an isolated environment; `notify.sh` writes only a terminal escape sequence and runs no notifier program. Every script under `scripts/`, comments included and `gate.sh` too, holds no text the plugin directory reads as a command whose program is computed at run time: no inline-code span with a command substitution or indirect expansion, or that starts with a variable expansion other than the plugin-root variable, no indirect expansion anywhere in a comment, and no ANSI-C string with an escaped quote or a backtick (with a self-check of that scan). |
| `test_session_start.py` | `session-start.sh` emits valid SessionStart JSON within its 9,500-character budget for every source, fails open on bad input, injects the detected stack's lore cores, shows the first-run and migration notices as a `systemMessage`, keeps its session stamps and knowledge-graph note bounded, and never writes settings or the session env file. |
| `test_compaction.py` | `compact-context.sh` (SessionStart, matcher `compact`) restates the branch, changed files, session commits and `.workspace/shared/` artifacts from git and the filesystem; transcript content never reaches its output; lists are bounded, output is JSON-escaped, and it writes nothing. |
| `test_userconfig.py` | The `userConfig` schema, and the `userconfig-env.sh` bridge that copies non-empty `CLAUDE_PLUGIN_OPTION_*` values into the session env file: quoting of hostile values, privacy (mode 0600, silent), idempotence; plus the `jira`/`confluence` CLIs' connection config, auth header shapes and refusal of plain HTTP to a remote host; and no hook script except the guard names a project dotenv file, bare, quoted or at the end of a path (with a self-check of that pattern). |
| `test_tools_path.py` | `tools-path.sh` writes one launcher per bundled command into a folder per plugin root under `CLAUDE_PLUGIN_DATA/tools`, each running the command from the plugin root with its arguments intact (a quote in the root path included), and appends one PATH line to the session env file that puts that folder first in bash and sh, never turns an empty PATH into the current folder, and is added once per root, so an update's line wins while sessions on two versions don't repoint each other. It removes folders of roots that no longer exist, every file and link in the folder that isn't a launcher (without touching link targets) and launchers that lost their exec bit; it skips odd names, notes a folder in the way, never writes through a link at the temporary name, refuses linked launcher folders, never runs a command, keeps stdout empty and an existing file's mode, writes quotes, `$` and backticks in paths literally, converts Windows paths with `cygpath`, and refuses paths PATH can't carry (a colon in the data folder path, a control character, a Windows path without `cygpath`). Every skill that pre-approves a bundled command has the one-line fallback to its full path. |
| `test_magician_ui.py` | `magician-ui` changes settings only on an explicit command: `reconcile` is an inert stub, `allow`/`automode` add nothing, `cleanup` removes only the rules on the fixed list older versions added, and only when cli-ui.json records that they were added (a user rule that is also on that list goes too, except `Bash(jira:*)` and `Bash(confluence:*)` under a 4.4-or-later record), `disable --purge` refuses while cleanup still needs that record unless `--force` is given, a cli-ui.json that exists but can't be read is never replaced (commands that save it stop first, `cleanup` and `disable` do the rest and say they left it, the status views note it, `disable --purge` refuses while settings has entries the record might cover, unless `--force`, and a folder in its place stops the purge), a subcommand given an argument it doesn't take, or `enable`/`set` given no known component, changes nothing, `enable` touches only `statusLine`, `disable --purge` removes only magician's files, and settings backups are mode 0600 with at most 3 kept. |
| `test_destructive_guard.py` | The `PreToolUse(Bash\|PowerShell)` hard gate exits 2 with a reason on stderr for catastrophic command shapes, including quoted home targets, wrapper flags that take a value, nested `sh -c` bodies with extra shell options, any PowerShell drive root, `C:\Windows` and home folder (project paths below them pass), and `git clean` with `--force`, `-X` or git options before it; blocks reads and dumps of the plugin's saved options, also behind wrappers and `( )`/`{ }` grouping and through quoted `/proc` paths; soft-blocks `.env`/`.env.*`, SSH, AWS, gcloud and Azure credential reads but not `.envrc` or `.env.example`-style templates, and doesn't flag a quoted mention of a download pipe; hard-blocks every case the 4.14 Python guard blocked (parity corpus); never expands globs; and lets benign and malformed events through. Every catastrophic sample is assembled at runtime, so no file holds a complete one. |
| `test_guardrails.py` | Plugin-wide security posture: no hardcoded secrets and no legacy credential variable names in any tracked text file outside `tests/` (the list comes from `git ls-files`, with a filesystem walk when git is unavailable), credentialed CLIs read only userConfig values (`CLAUDE_PLUGIN_OPTION_*`), secrets kept out of argv, no unbounded tool grants, the guard fails open, download-and-run pipes are caught (cases generated from the guard's own token lists), no tracked file, tests included, holds a complete download-and-run command (the regex is built from word lists at runtime and checked against samples), and no tracked file other than Markdown holds a package launcher followed by a package without an exact version, or `uv run` without `--locked`/`--frozen` (also checked against samples). |
| `test_magician_scan.py` | `magician-scan` reports a hardcoded credential and an AWS key by type with the value shown as `<redacted>`, never printed, and exits 0 on a clean folder. |
| `test_agents.py` | Every `agents/*.md` is a spawnable subagent: required frontmatter, name matches filename, least-privilege tools within a ceiling, review lenses are read-only, write-capable agents say why, and every `magician:<name>` a skill dispatches exists. |
| `test_skills.py` | Every `skills/*/SKILL.md` has a routable name and description, `allowed-tools` entries that are known and scoped (no bare Bash or WebFetch, no Write/Monitor/WebSearch, no interpreter or whole-CLI grants), Bash rules that match the commands each skill runs but not their fix, publish, force-push or extra-path variants, and relative links (including `#section` anchors) that resolve. |
| `test_skill_quality.py` | Authoring quality: lean SKILL.md bodies with detail in `references/`, descriptions under the hard cap, no time-sensitive prose, no subagent-blocked tool requests, router-safe agent names, valid `disable-model-invocation`, and no Monitor or `npx` steps. |
| `test_frontmatter_strict.py` | Every skill and agent frontmatter parses under a strict YAML subset (`_strict_frontmatter.py`): known keys, safe quoting, least-privilege tools, plugin-script grants that point to executable files, no dynamic context injection; a policy self-test, and an optional cross-check against full YAML parsers when one is installed. |
| `test_lore.py` | The lore corpus: `lore/<stack>.md` cores plus one `lore/deep/<stack>.md` each, with matching section anchors, resolving links, cores that fit the always-injected budget, and files under the validator's size and count limits. |
| `test_manifest.py` | `plugin.json` / `marketplace.json` are well-formed, the marketplace entry carries no `version` and the same description as the manifest, the version is semver and matches the CHANGELOG's top entry (the README carries no version badge or remote image), declared component dirs exist, the Codex marketplace points at the `codex-plugin` branch with no Codex build output on main, no tracked file anywhere in the repo is a scratch draft, local tool state or OS junk, and `.gitignore` keeps those out of a `git add -A`. |
| `test_readme.py` | The README and policy documents meet the plugin directory's rules: Markdown images only, bundled and script-free, no raw HTML; `PRIVACY.md` and `SECURITY.md` exist; and every skill, hook script and plugin option is documented. |
| `test_evals.py` | The `evals/` behavioral suite is well-formed and honest: valid grader types, compiling patterns, and every asserted skill, agent and tool actually exists. |

Shared helpers: `_frontmatter.py` (a small frontmatter reader used by several gates) and
`_strict_frontmatter.py` (the strict YAML-subset parser behind `test_frontmatter_strict.py`).

Every test that runs a hook script or a bundled CLI passes a fully specified environment built from
temp dirs (`HOME`, `CLAUDE_PLUGIN_DATA`, `MAGICIAN_HOME`, `MAGICIAN_SETTINGS`, `CLAUDE_ENV_FILE`), so
the real `~/.claude` is never read or written.

## Behavioral eval tier (`evals/`, opt-in)

`bash scripts/gate.sh --evals` runs the plugin end-to-end through
`claude plugin eval --trust-plugin` — a real model, in a sandbox, graded on what actually happened. It spends API budget and needs the network, so it is
opt-in and local-only: the maintainer runs it before a release, and CI (`.github/workflows/gate.yml`)
runs only the offline gate. The suite gates the behavior that is **reliably observable** in the eval
sandbox:

| Case | Proves |
|------|--------|
| `security-scan-routes-to-sentinel` | A "run a security scan" request invokes the `sentinel` **skill** (Skill tool) **and** the scan catches the planted SQL injection and XSS. |
| `code-review-routes-to-review-skill` | A code-review request invokes the `divine` review **skill** **and** the review catches the planted correctness defects in a money-transfer diff. |
| `destructive-command-is-blocked` | A prompt that asks to run a command that recursively wipes the filesystem root never gets it executed, and the model does not claim it did. Current models refuse before any tool call, so this does not exercise the guard **hook**; `test_destructive_guard.py` covers the hook. |

**Why agent-spawning is not in this tier.** Whether the model spins up a subagent for a small review
is model-discretionary — it (correctly) reviews a five-line diff inline rather than paying the
overhead of a subagent, even when told to delegate. That is not reproducible enough to hang a green
gate on. Agent *dispatchability* is therefore gated **structurally** in `test_agents.py`: every agent
is well-formed and least-privileged, and every `magician:<name>` dispatch target resolves to a real
agent. The eval tier proves the skill routing a model *does* exercise on every relevant turn, and that a
catastrophic request never runs; the guard hook itself is proven in `test_destructive_guard.py`.

## Design principle

Every gate reads declarative config and the filesystem, or invokes a script exactly as the hook does —
**none of them execute a catastrophic command or a real network call.** A guardrail without a test is
unverified; these tests are how the plugin verifies its own guardrails.

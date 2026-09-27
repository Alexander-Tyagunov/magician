# Installing Magician for Codex

Enable Magician in Codex through the native plugin system. The Codex package is a self-contained plugin committed on the repository's `codex-plugin` branch (at `plugins/magician`); it carries Codex-specific adapter skills so Codex can use the same SDLC workflows without modifying Claude Code setup. The repository's main branch only holds the marketplace entry that points Codex at that branch.

## Prerequisites

- Codex CLI or Codex app with plugin support
- Python 3.10 or newer (used by the Codex safety hook and bundled helpers)
- Git (Codex fetches the package from the repository's `codex-plugin` branch)

Preflight the required runtimes before installing:

```bash
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'
git --version
```

## Recommended Installation

Add the Magician marketplace (only its marketplace file is fetched) and install the plugin:

```bash
codex plugin marketplace add Alexander-Tyagunov/magician --sparse .agents/plugins
codex plugin add magician@magician
```

`codex plugin marketplace add Alexander-Tyagunov/magician` without `--sparse` also works; it just
snapshots more of the repository. The marketplace entry resolves the plugin from the `codex-plugin`
branch, path `plugins/magician`, so Codex installs only the package directory.

Restart Codex or start a new task after installation. Codex loads plugin skills and hooks at task startup, so an already-open task does not prove that the new package was picked up. Use `codex plugin list` to confirm `magician@magician` is both installed and enabled; an `enabled = true` config entry alone is not an installation.

## Local development (codex-plugin branch checkout)

Maintainers work in a checkout of the `codex-plugin` branch. Its own `.agents/plugins/marketplace.json`
points at the committed local package, and a helper installs it into a throwaway `CODEX_HOME` (your
`~/.codex` is never touched):

```bash
bash .codex-plugin/scripts/smoke-install.sh
```

Do not clone the repository into `~/.codex/magician`: that path is Magician's default Codex state
folder.

## Verify

Start a new Codex session and ask:

```text
Set up Magician in this workspace.
```

Codex should load the `$almanac` adapter from the installed plugin's `skills/almanac/SKILL.md`. The install command reports the exact cache directory; verify that cached package rather than assuming a checkout path:

```bash
codex plugin add magician@magician --json
# Inspect the returned installedPath: it must contain 26 skills/*/SKILL.md files,
# hooks/codex-hooks.json, scripts/codex-destructive-guard.sh, and bin/kg.
```

The twenty-sixth skill is Codex-only: `$project-context` detects root-level stack markers and
progressively loads relevant packaged lore cores and task-matched deep dives. It does not install or
emulate Claude's `SessionStart` hook.

## Model setup

Magician does not force a model or overwrite your Codex configuration. Current Codex defaults use
GPT-5.6 Sol with medium reasoning. A user-level default can be explicit:

```toml
model = "gpt-5.6"
model_reasoning_effort = "medium"
```

`gpt-5.6` aliases to `gpt-5.6-sol`. Use Sol for complex and high-value work, Terra for everyday
implementation, and Luna for clear repeatable tasks. Start with the lowest reasoning level that
meets the quality bar; raise it only when representative work shows a gain. The current Codex config
reference lists reasoning through `xhigh`; Max can be exposed separately in the app and should not be
written into `config.toml` unless the installed Codex version documents support for it. Ultra is
multi-agent execution, not another reasoning level.

The packaged Codex model guide lives at `lore/models.md`. It is overlaid only in the generated Codex
package, so Claude Code continues to use its existing model guide unchanged.

## Safety — trust the destructive-command hard gate

Magician ships a Codex `PreToolUse` hook that **denies catastrophic shell commands** (`rm -rf /` · `~` · `$HOME`, disk/device wipes, block-device/critical-file overwrites, fork bombs, recursive `chmod`/`chown` on system roots, download-piped-to-shell, `git clean -x`) before they run.

Codex does **not** auto-trust a plugin's hooks. After enabling magician, run:

```text
/hooks
```

Review and **trust** magician's `destructive-guard` hook — otherwise Codex skips it. Never test a safety hook by submitting a real catastrophic shell command to Codex. Test the hook implementation directly with a simulated event instead:

```bash
PLUGIN_ROOT="$(codex plugin add magician@magician --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["installedPath"])')"
set +e
printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' \
  | "$PLUGIN_ROOT/scripts/codex-destructive-guard.sh"
status=$?
set -e
test "$status" -eq 2
```

This sends text to the matcher; it does **not** execute the command. A passing simulation prints `[MAGICIAN CODEX HARD-GATE]` and exits `2`.

Independent of this hook, Codex's own **sandbox** (`workspace-write` / `read-only`) already blocks writes and deletes outside the workspace root, so `rm -rf ~` fails there regardless. The hook adds a deterministic layer that also covers `danger-full-access`. It's a guardrail, not a complete sandbox — keep Codex's sandbox + approvals on.

## Design Capabilities

Magician includes a free local design companion through `$conjure`. It starts a Node.js localhost server, writes design screens under `.workspace/shared/...`, opens them in Codex Browser Use, records click feedback, and iterates until the design is approved.

For this built-in path you need:

- Node.js available on `PATH`
- Codex Browser Use enabled

No Figma or external design SaaS is required for the Magician design loop.

Optional: install OpenAI's official Build Web Apps plugin from the Codex Plugins directory when you want extra frontend implementation or UI-review help. Use Figma only when the workflow starts from, or must write back to, Figma; it is not required for Magician parity.

## Updating

```bash
codex plugin marketplace upgrade magician
codex plugin add magician@magician
```

Codex does not auto-update plugins: `marketplace upgrade` refreshes the marketplace snapshot and
`plugin add` fetches the current `codex-plugin` package. `marketplace upgrade` works only for a
marketplace added from GitHub (a Git source). Start a new task afterwards and verify the version and
cache contents again.

After every upgrade, run `/hooks` and confirm magician's `destructive-guard` hook is trusted; re-trust
it if it is not. Codex skips an untrusted hook silently, so do not wait for a prompt.

**Upgrading from 4.14.0 or earlier.**

- *Added from GitHub* (`codex plugin marketplace add Alexander-Tyagunov/magician`): the two commands
  above move you to the `codex-plugin` branch package.
- *Added from a local checkout* (for example the old `git clone … ~/.codex/magician` +
  `codex plugin marketplace add ~/.codex/magician` method): `marketplace upgrade` refuses a local
  marketplace. Switch to the GitHub source instead:

  ```bash
  codex plugin marketplace remove magician
  codex plugin marketplace add Alexander-Tyagunov/magician --sparse .agents/plugins
  codex plugin add magician@magician
  ```

  `~/.codex/magician` is also where the Codex CLIs keep their state (Jira/Confluence caches and
  memory, the knowledge graph). Do not delete an old clone there blindly: move the state files you
  want to keep first, or simply leave the directory in place.

## Jira and Confluence credentials

In Codex the bundled `jira` and `confluence` CLIs read their connection settings only from the
environment Codex runs in (there is no plugin settings form):

- Jira: `JIRA_BASE_URL`, a token in `JIRA_API_TOKEN` (or `JIRA_PAT` / `JIRA_PROD_PAT`), and for Cloud
  `JIRA_EMAIL`.
- Confluence: `CONFLUENCE_BASE_URL`, a token in `CONFLUENCE_API_TOKEN` (or `CONFLUENCE_PAT` /
  `CONFLUENCE_PROD_PAT`), and for Cloud `CONFLUENCE_EMAIL`. On an Atlassian Cloud site shared with
  Jira, the Jira token and email are reused when Confluence has none.

Export them in your shell profile or in the shell that launches Codex, then restart Codex from that
shell: a running Codex does not see variables exported after it started. Never paste a token into the
conversation.

Both base URLs must use `https://` (a localhost URL is exempt), and redirects are not followed, so use
the final URL. A Confluence Cloud base URL ends in `/wiki` (for example
`https://example.atlassian.net/wiki`). The variable names are the same as in 4.14; the https and
no-redirect rules are new in 4.15.

Codex filters the environment passed to shell commands with `shell_environment_policy`. The variables
above survive only with `inherit = "all"` (the default) and `ignore_default_excludes = true` (the
default), and when no `exclude` pattern matches them. `inherit = "core"` or `"none"` drops them all,
URLs and emails included, and `ignore_default_excludes = false` drops the token variables. If you use
`include_only`, list the `JIRA_*` and `CONFLUENCE_*` variables there too, or they are filtered out.
Avoid `shell_environment_policy.set` for tokens: it stores the secret in `config.toml` in clear text.

## Adding the marketplace from the codex-plugin branch

The default marketplace entry already resolves the package from the `codex-plugin` branch, so this
gives the same package; it only changes where the marketplace file itself comes from. Remove the
existing `magician` marketplace first (Codex refuses a second marketplace with the same name; removing
it keeps the plugin enablement, cache and hook trust), and do **not** pass `--sparse`, because that
branch's marketplace entry is a local `./plugins/magician` source:

```bash
codex plugin marketplace remove magician
codex plugin marketplace add Alexander-Tyagunov/magician --ref codex-plugin
codex plugin add magician@magician
```

## Uninstalling

Remove the installed plugin, then remove the configured marketplace source if it is no longer needed:

```bash
codex plugin remove magician@magician
codex plugin marketplace remove magician
```

## Notes

- Do not symlink main's raw `skills/` directory into `~/.agents/skills/`. That bypasses Magician's Codex adapter layer.
- Codex loads adapter skills from the self-contained package's `skills/`; those adapters read immutable packaged copies under `source-skills/` and translate Claude Code-specific instructions to Codex behavior.
- Claude Code is unaffected by this installation path. Claude Code installs from the main branch (`.claude-plugin/`, `hooks/`, and the source `skills/` directory).

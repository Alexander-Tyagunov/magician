# Installing Magician for Codex

Enable Magician in Codex through the native plugin system. Magician ships Codex-specific adapter skills under `.codex-plugin/skills/` so Codex can use the same SDLC workflows without modifying Claude Code setup.

## Prerequisites

- Codex CLI or Codex app with plugin support
- Python 3.10 or newer (used by the Codex safety hook and bundled helpers)
- Git, if installing from GitHub or a cloned checkout

Preflight the required runtimes before installing:

```bash
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'
git --version
```

## Recommended Installation

Add the Magician plugin source:

```bash
codex plugin marketplace add Alexander-Tyagunov/magician
codex plugin add magician@magician
```

Restart Codex or start a new task after installation. Codex loads plugin skills and hooks at task startup, so an already-open task does not prove that the new package was picked up. Use `codex plugin list` to confirm `magician@magician` is both installed and enabled; an `enabled = true` config entry alone is not an installation.

## Local Checkout Installation

Use this while developing Magician or testing an unmerged branch:

```bash
git clone https://github.com/Alexander-Tyagunov/magician.git ~/.codex/magician
codex plugin marketplace add ~/.codex/magician
codex plugin add magician@magician
```

If you already have this repository checked out locally, add that directory instead:

```bash
codex plugin marketplace add /absolute/path/to/magician
codex plugin add magician@magician
```

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

If installed from GitHub:

```bash
codex plugin marketplace upgrade magician
codex plugin add magician@magician
```

If installed from a local checkout:

```bash
cd ~/.codex/magician
git pull
codex plugin add magician@magician
```

Start a new task after reinstalling and verify the version and cache contents again.

## Uninstalling

Remove the installed plugin, then remove the configured marketplace source if it is no longer needed:

```bash
codex plugin remove magician@magician
codex plugin marketplace remove magician
```

If you cloned Magician only for Codex, you can also remove the checkout:

```bash
rm -rf ~/.codex/magician
```

## Notes

- Do not symlink the raw `skills/` directory into `~/.agents/skills/`. That bypasses Magician's Codex adapter layer.
- Codex loads adapter skills from the self-contained package's `skills/`; those adapters read immutable packaged copies under `source-skills/` and translate Claude Code-specific instructions to Codex behavior.
- Claude Code is unaffected by this installation path. Claude continues to use `.claude-plugin/`, `hooks/`, `settings.json`, and the source `skills/` directory.

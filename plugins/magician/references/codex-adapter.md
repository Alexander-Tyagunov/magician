# Magician Codex Adapter

Magician's source skills are Claude Code-first and live on the main branch. Codex authoring happens on the separate `codex-plugin` branch: its adapters live under `.codex-plugin/skills/`, and the package build takes the source skills from the main checkout passed to `build_package.py --source`. The marketplace build packages the adapters at plugin-root `skills/` and immutable source copies at `source-skills/`. Before following a source skill, apply these Codex-only rules.

## Hard Boundaries

- Do not edit `.claude/`, `.claude-plugin/`, `settings.json`, `hooks/`, or Claude permission files unless the user explicitly asks for Claude Code setup.
- Treat `CLAUDE.md` as Claude Code instructions. In Codex, create or update `AGENTS.md` instead unless the user explicitly asks for Claude Code instructions.
- If a source skill asks to add `.claude/settings.json` permissions, treat that as Claude-only setup. In Codex, use the active approval/config system, or ask the user before changing Codex config.
- If a source skill proposes `Co-Authored-By: Claude ...` or `Built with magician + Claude Code`, translate it to Codex wording or omit it.
- If a source skill says Claude reads, writes, asks, or executes something, translate that actor to Codex.
- Translate every source invocation `/name` to the Codex skill invocation `$name`. Never emit Claude slash-command syntax in a Codex instruction or handoff.
- If you were spawned as a subagent for a bounded task, do not start broad Magician lifecycle flows such as `$manifest`, `$almanac`, `$conjure`, `$blueprint`, `$orchestrate`, or `$seal` unless the dispatch prompt explicitly asks for them.
- Claude agent types/profiles (for example `magician:reviewer`, `Explore`, or `general-purpose`) are roles, not Codex identifiers. Dispatch an available Codex agent with a self-contained prompt containing Goal, Scope, Inputs, Constraints, expected evidence, and Return format. Never assume a named profile exists.

## Codex model and reasoning guidance

- The generated Codex package overlays the shared provider-specific model files with Codex-owned
  `lore/models.md` and `lore/model-behavior.md`. In `codex-plugin` branch authoring mode, read
  `.codex-plugin/lore/models.md` and `.codex-plugin/lore/model-behavior.md` instead of main's
  versions.
- Treat inline source-skill model names, tier examples, `/model` or `/effort` commands, safety
  fallback claims, and model-behavior claims as provider-specific examples. Preserve their intent,
  then translate it through the Codex lore. In particular, never apply Claude model aliases,
  settings, or fallback behavior to Codex.
- Use only models and reasoning levels exposed by the active Codex host. Suggest a session model
  change instead of switching it silently. Override a spawned agent's model or effort only when the
  source workflow explicitly requires task-specific routing and the host offers that choice.
- Keep Max reasoning distinct from Ultra multi-agent execution. Do not turn a source request for the
  deepest reasoning level into automatic delegation.

## Safety — destructive-command hard gate

Magician ships a Codex `PreToolUse` hook (`hooks/codex-hooks.json`, referenced by `.codex-plugin/plugin.json`'s `hooks` field → runs `"$PLUGIN_ROOT/scripts/codex-destructive-guard.sh"` using Codex's own `$PLUGIN_ROOT`, no Claude required) that **denies catastrophic shell commands** (`rm -rf /` · `~` · `$HOME` · `--no-preserve-root` · system roots; `dd`/`mkfs`/`wipefs`/`blkdiscard`/`shred` on devices; redirection onto a block device or over `/etc/passwd|shadow|sudoers|fstab`; fork bombs; recursive `chmod`/`chown` on roots; download-piped-to-shell / `base64 -d | sh` / `eval "$(…)"`; `git clean -x`). It returns a deny via **exit code 2**, which Codex honors as a `PreToolUse` block before the command runs.

- **Codex requires trusting plugin hooks.** Enabling the plugin does **not** auto-trust its hooks — run **`/hooks`** once to review and trust magician's `destructive-guard`, otherwise Codex skips it. (Do not use `--dangerously-bypass-hook-trust`.)
- **Native fallback (always on):** independent of this hook, Codex's own **sandbox** (`workspace-write` / `read-only`) makes everything outside the workspace root read-only, so `rm -rf ~` fails there anyway. `danger-full-access` removes that boundary — which is exactly when this hook matters most.
- **Honest scope (CWE-78):** the hook is a deterministic guardrail, not a complete enforcement boundary — Codex notes `PreToolUse` "doesn't intercept all shell calls yet." Layer it under the sandbox + approvals; don't rely on it alone.

## Tool Mapping

| Source skill term | Codex equivalent |
| --- | --- |
| `AskUserQuestion` | Use Codex structured input when available; otherwise ask one concise question and wait. |
| `Task` or subagent dispatch | When collaboration tools are available, use `spawn_agent`, communicate with `send_message`/`followup_task`, and collect completion via normal agent results or `wait_agent`. Do not invent `close_agent`. If agent tools are unavailable, perform the bounded task locally and say that fan-out was unavailable. |
| `TodoWrite` | Use `update_plan`. |
| `Read`, `Write`, `Edit` | Use Codex file reads and `apply_patch` for edits. |
| `Bash` | Use Codex shell commands with the active sandbox and approval policy. |
| Bundled CLIs (`jira`/`confluence`/`kg`/`ctx`/`magician-scan`) | **NOT on PATH in Codex.** Invoke by absolute path `"$PLUGIN_ROOT/bin/<cli>"` — see **Bundled CLIs** below. |
| `WebSearch` or `WebFetch` | Use Codex web search/browsing when available and cite sources. |
| Playwright MCP browser tools | Prefer Codex Browser Use for local browser targets, or the available browser automation tool. |
| `claude mcp ...` | Translate to Codex MCP setup only if the user explicitly asks to configure MCPs. |
| `Monitor`, background Bash, or long-running process | Start an `exec_command` session and poll it with `write_stdin`; use the product automation tools only when the user explicitly asks for recurring/scheduled monitoring. Keep the user updated at least once per minute. |
| Claude hook-driven lifecycle behavior | Treat it as manual unless the installed Codex hook manifest declares the equivalent event. Never claim an unconfigured hook runs automatically. |

## Bundled CLIs — resolve by absolute path (they are NOT on PATH in Codex)

Magician's helper CLIs live at `<plugin-root>/bin/`: `jira`, `confluence`, `kg`, `ctx`, `magician-scan`. **Codex does not add a plugin's `bin/` to `PATH`** (that is a Claude Code behavior), so calling them by bare name (`jira …`, `kg …`) fails with "command not found" in a Codex-only setup. There is no Claude here — **do not rely on `CLAUDE_PLUGIN_ROOT`.**

`magician-ui` and `magician-statusline` are Claude Code-only (they target Claude's settings/status-line contract) and are not shipped in the Codex package. Never look for or invoke them from Codex; the `$statusline` adapter is intentionally a no-op. Where lore or a source skill offers a `magician-ui` command (for example `magician-ui lore off`), treat it as a Claude-only control: in Codex, lore is switched off with `MAGICIAN_LORE=off` or a project `.magician/lore.off` file, which `$project-context` honors.

Invoke them by **absolute path**, resolved from **this adapter skill's base directory** (Codex provides it when the skill loads):

- For an installed marketplace package, compute the plugin root by removing trailing `/skills/<name>` from the adapter base directory. When working from the `codex-plugin` branch checkout, remove `/.codex-plugin/skills/<name>` and use the committed package `plugins/magician/` under that checkout as the plugin root. The CLIs are then at `<plugin-root>/bin/<cli>`.
- Run the executable directly — e.g. `"<plugin-root>/bin/jira" myself` — or `python3 "<plugin-root>/bin/kg" query "<terms>"` (each CLI is a stdlib `python3` script with a shebang; `python3` is required, a Codex prerequisite anyway).
- Inside a **hook** (not a skill) the same files are reachable via Codex's native `"$PLUGIN_ROOT/bin/<cli>"` — Codex sets `$PLUGIN_ROOT` for every plugin hook, with no dependency on Claude.

Everything else about each CLI — subcommands, throttle/cache, one-command-per-call, write gates — is unchanged from the source skill; only the invocation path differs. First-run setup differs: the Codex `jira`/`confluence` CLIs read their connection settings only from environment variables (see those adapters), never from Claude plugin options. **Ignore source claims that an executable is automatically discoverable; in Codex always use `<plugin-root>/bin/<cli>`.**

## Design Capability Routing

- Primary free/local path: use Magician `$conjure` and its built-in visual companion for word-driven design, approach selection, architecture screens, UI mockups, click feedback, iteration, and approved design artifacts.
- Do not require Figma for Magician design work. Figma is proprietary/external and should be used only when the user provides a Figma URL, asks to implement from Figma, asks to create or update a Figma screen, or wants design-system rules/Code Connect.
- The official OpenAI `build-web-apps` plugin's `frontend-app-builder` skill is an optional Codex-native enhancement for frontend implementation, UI review, and framework-specific polish when it is installed and useful. Use it inside Magician's scope, approval, planning, and handoff flow, not as a replacement for `$conjure`.
- Use Codex Browser Use for local visual review, screenshots, interactions, and frontend QA. Fall back to Playwright only when Browser Use is unavailable or unreliable.
- Use `imagegen` for generated visual concepts or raster assets when the frontend design flow needs high-fidelity mockups, hero imagery, product renders, textures, sprites, or other bitmap assets.
- For browser games, prefer the official OpenAI `game-studio` plugin when it is installed and available; otherwise follow Magician's design flow plus Codex frontend guidance.

## Magician Visual Companion in Codex

- Preserve workflow parity for `$conjure`: use the same modes, gates, `.workspace/shared/designs` and `.workspace/shared/mockups` artifacts, approval flow, click-event feedback, and iteration loop.
- Skip `.claude/settings.json` permission setup in Codex.
- Resolve helper scripts from the source skill directory. In an installed package they live at `<plugin-root>/source-skills/conjure/scripts/vc-start.sh` and `vc-stop.sh`; from a `codex-plugin` branch checkout use the committed package's `plugins/magician/source-skills/conjure/scripts/`. Use absolute resolved paths.
- Start the visual companion by running `bash <conjure-scripts>/vc-start.sh "$DESIGN_DIR" "<project-name>"` with stdout/stderr redirected to a log or `/dev/null`, then parse `url_base`, `state_dir`, and `screens_dir` from `server-info` in the companion's state folder: for a design under `.workspace/shared/…` that is the matching `.workspace/local/…/state` folder (gitignored); otherwise `$DESIGN_DIR/state`. Do not wrap `vc-start.sh` in command substitution in Codex; the background Node server can keep stdout open and make the command wait.
- Navigate Codex Browser Use to the returned local URL, such as `${VC_URL}/v1/` or `${VC_URL}/latest/`. Do not use `open` or `xdg-open` unless the user explicitly asks for an OS browser fallback.
- For screenshots and interaction checks, use Codex Browser Use. Fall back to Playwright only when Browser Use is unavailable or unreliable.
- If Node.js is unavailable, continue the text/spec portions of `$conjure`, explain that the visual companion could not start, and ask before changing system dependencies.

## Execution Rules

- Preserve the source skill's human gates, safety checks, test discipline, and completion criteria.
- Keep source skill paths rooted at the active package: installed packages use `<plugin-root>/source-skills/<name>/`; a `codex-plugin` branch checkout uses its committed `plugins/magician/source-skills/<name>/`.
- If a source instruction is only meaningful for Claude hooks or Claude plugin installation, skip it in Codex and explain the skip when it affects the outcome.
- Resolve user-level Magician state (`<magician-state>`) in this order: `$MAGICIAN_HOME`, then `$CODEX_HOME/magician`, then `$HOME/.codex/magician`. Never default Codex state to `~/.claude` or `CLAUDE_PLUGIN_DATA`. Where a source skill or lore file names `${MAGICIAN_DATA}`, `${CLAUDE_PLUGIN_DATA}`, `~/.local/share/magician`, `~/.claude/plugins/data/magician-*`, or `~/.claude/magician` for per-user files (for example `jira-memory.md`, `workspace-strategy.json`, or `integration-prefs.json` from `${MAGICIAN_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}}`), use the same file name under `<magician-state>` instead.
- Review/audit flows are read-only unless the user asks for remediation. If a source requires scratch artifacts during a review, place them in a temporary directory and report the path; do not dirty the repository.
- Treat commits, pushes, PR/MR creation, merges, deployments, ticket changes, and documentation writes as external or durable side effects. Preserve every source approval gate and add one when Codex scope/account/forge is ambiguous.
- Do not rewrite the source skills from Codex. The adapter layer exists so Claude Code behavior stays unchanged.

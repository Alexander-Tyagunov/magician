# Magician Codex Adapter

Magician's source skills are Claude Code-first. Codex loads the adapter skills from `.codex-plugin/skills/`; each adapter points back to the source skill under `skills/`. Before following a source skill, apply these Codex-only rules.

## Hard Boundaries

- Do not edit `.claude/`, `.claude-plugin/`, `settings.json`, `hooks/`, or Claude permission files unless the user explicitly asks for Claude Code setup.
- Treat `CLAUDE.md` as Claude Code instructions. In Codex, create or update `AGENTS.md` instead unless the user explicitly asks for Claude Code instructions.
- If a source skill asks to add `.claude/settings.json` permissions, treat that as Claude-only setup. In Codex, use the active approval/config system, or ask the user before changing Codex config.
- If a source skill proposes `Co-Authored-By: Claude ...` or `Built with magician + Claude Code`, translate it to Codex wording or omit it.
- If a source skill says Claude reads, writes, asks, or executes something, translate that actor to Codex.
- If you were spawned as a subagent for a bounded task, do not start broad Magician lifecycle flows such as `/manifest`, `/almanac`, `/conjure`, `/blueprint`, `/orchestrate`, or `/seal` unless the dispatch prompt explicitly asks for them.

## Tool Mapping

| Source skill term | Codex equivalent |
| --- | --- |
| `AskUserQuestion` | Use Codex structured input when available; otherwise ask one concise question and wait. |
| `Task` or subagent dispatch | Use `spawn_agent`; use `wait_agent` only when blocked; use `close_agent` when done. |
| `TodoWrite` | Use `update_plan`. |
| `Read`, `Write`, `Edit` | Use Codex file reads and `apply_patch` for edits. |
| `Bash` | Use Codex shell commands with the active sandbox and approval policy. |
| `WebSearch` or `WebFetch` | Use Codex web search/browsing when available and cite sources. |
| Playwright MCP browser tools | Prefer Codex Browser Use for local browser targets, or the available browser automation tool. |
| `claude mcp ...` | Translate to Codex MCP setup only if the user explicitly asks to configure MCPs. |

## Design Capability Routing

- Primary free/local path: use Magician `/conjure` and its built-in visual companion for word-driven design, approach selection, architecture screens, UI mockups, click feedback, iteration, and approved design artifacts.
- Do not require Figma for Magician design work. Figma is proprietary/external and should be used only when the user provides a Figma URL, asks to implement from Figma, asks to create or update a Figma screen, or wants design-system rules/Code Connect.
- The official OpenAI `build-web-apps` plugin's `frontend-app-builder` skill is an optional Codex-native enhancement for frontend implementation, UI review, and framework-specific polish when it is installed and useful. Use it inside Magician's scope, approval, planning, and handoff flow, not as a replacement for `/conjure`.
- Use Codex Browser Use for local visual review, screenshots, interactions, and frontend QA. Fall back to Playwright only when Browser Use is unavailable or unreliable.
- Use `imagegen` for generated visual concepts or raster assets when the frontend design flow needs high-fidelity mockups, hero imagery, product renders, textures, sprites, or other bitmap assets.
- For browser games, prefer the official OpenAI `game-studio` plugin when it is installed and available; otherwise follow Magician's design flow plus Codex frontend guidance.

## Magician Visual Companion in Codex

- Preserve Claude parity for `/conjure`: use the same modes, gates, `.workspace/shared/designs` and `.workspace/shared/mockups` artifacts, approval flow, click-event feedback, and iteration loop.
- Skip `.claude/settings.json` permission setup in Codex.
- Resolve helper scripts from the source skill directory. From `.codex-plugin/skills/conjure/SKILL.md`, the source scripts live at `../../../skills/conjure/scripts/vc-start.sh` and `../../../skills/conjure/scripts/vc-stop.sh`; equivalent plugin-root absolute paths are also fine.
- Start the visual companion by running `bash <conjure-scripts>/vc-start.sh "$DESIGN_DIR" "<project-name>"` with stdout/stderr redirected to a log or `/dev/null`, then parse `url_base`, `state_dir`, and `screens_dir` from `$DESIGN_DIR/state/server-info`. Do not wrap `vc-start.sh` in command substitution in Codex; the background Node server can keep stdout open and make the command wait.
- Navigate Codex Browser Use to the returned local URL, such as `${VC_URL}/v1/` or `${VC_URL}/latest/`. Do not use `open` or `xdg-open` unless the user explicitly asks for an OS browser fallback.
- For screenshots and interaction checks, use Codex Browser Use. Fall back to Playwright only when Browser Use is unavailable or unreliable.
- If Node.js is unavailable, continue the text/spec portions of `/conjure`, explain that the visual companion could not start, and ask before changing system dependencies.

## Execution Rules

- Preserve the source skill's human gates, safety checks, test discipline, and completion criteria.
- Keep source skill paths rooted at the plugin root. For example, the `conjure` source skill lives at `skills/conjure/SKILL.md`, and its helper scripts live under `skills/conjure/scripts/`.
- If a source instruction is only meaningful for Claude hooks or Claude plugin installation, skip it in Codex and explain the skip when it affects the outcome.
- Do not rewrite the source skills from Codex. The adapter layer exists so Claude Code behavior stays unchanged.

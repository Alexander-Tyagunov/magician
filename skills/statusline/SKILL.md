---
name: statusline
description: Enable, configure, or disable the Magician CLI status line ("Magician Claude CLI UI") — a lightweight, always-on bar showing live context %, a context-rot warning, a token-flow sparkline, model · git · cost, the active skill/workflow/loop, and the current reasoning effort/mode. Use when the user says "enable/turn on the magician UI / status line / status bar", "show my context/tokens/effort in the console", "configure/change what the bar shows", "what should the status line display", or "turn off / disable the status line".
allowed-tools: Bash(magician-ui:*), AskUserQuestion, Read
argument-hint: [enable · disable · status · set <components>]
---

# /statusline — Magician CLI status line

A native Claude Code **status line** rendered by magician. It runs **locally, consumes zero API tokens**, updates on each message (debounced), and helps you catch **context rot** before it bites. It's driven by the bundled **`magician-ui`** CLI, which edits `~/.claude/settings.json` **safely** (timestamped backup → validate → atomic write; it never leaves settings broken and only ever touches the `statusLine` key).

## Components (user-configurable)

| key | shows |
|---|---|
| `context` | color-coded usage bar + used% + used/size tokens (green <70 · yellow 70–89 · red ≥90) |
| `rot` | a ⚠ at ≥80% and 🔴 at ≥92% so you notice before compaction |
| `spark` | a `▁▂▃▅▇` sparkline of recent context% (the token-flow stream) |
| `meta` | model · git branch · session cost |
| `skill` | the active magician skill / workflow / running-agent count / loop round |
| `effort` | 🧠 the live reasoning **effort** (low/medium/high/xhigh/max) — the default shows on open and tracks `/effort` changes automatically (from Claude Code's `effort.level`) — or the magician **mode** you set, e.g. `ultracode` (which otherwise reports as `xhigh`); say "set mode to ultracode" / "exit ultracode" to change it |

## Actions

- **Enable** — first confirm which components the user wants (default: all). Use **AskUserQuestion** (multi-select) unless they already said (e.g. "just rot and context"). Then:
  ```bash
  magician-ui enable --all              # everything
  magician-ui enable --only context,rot # a chosen subset
  ```
- **Change what shows** (no re-enable needed):
  ```bash
  magician-ui set context,rot,spark
  ```
- **Status** — `magician-ui status` (state, components, whether it's wired into settings).
- **Disable** — `magician-ui disable` (removes only magician's `statusLine`; records the opt-out so it isn't suggested again; re-enable anytime on request).
- **Auto mode (real autonomy)** — `magician-ui automode` turns on Claude Code's **auto** permission mode (`defaultMode: auto` + `CLAUDE_CODE_ENABLE_AUTO_MODE=1`, required on Vertex/Bedrock/Foundry). Its classifier auto-approves reads + request-aligned work and **gates** writes/deploys/force-push/destructive ops — the true "reads proceed, writes gate." A plugin can't switch the mode of a live session, so **restart** to enter it; `automode --off` reverts. Falls back to Manual if the account/model doesn't support auto.
- **Read-only auto-approve (acceptEdits fallback)** — `magician-ui allow` merges a read-only allow-list (Read/Grep/Glob/LS + read-only git + kg/ctx + **jira/confluence reads** + test/lint/build runners + gh reads) into `settings.json` so non-auto sessions don't prompt per read; jira/confluence **writes**, commit/push/PR/delete still gate. Applied on install/upgrade; `magician-ui allow --off`. (Jira/Confluence use magician's MCP-free CLIs — magician nudges sessions off any ambient Atlassian MCP.) See [lore/autonomy.md](../../lore/autonomy.md).

## Rules

- The bar is **suggested once** on session start when never configured; after that magician stays quiet and only acts when the user asks (`reconcile` records the state). Respect a decline — don't re-nudge.
- Enabling/disabling changes `~/.claude/settings.json`; it hot-reloads, so the bar appears/updates within a message or two — **no restart needed**.
- Keep it lightweight: recommend a smaller component set if the user wants a minimal bar (e.g. `context,rot`).
- Never hand-edit `settings.json` for this — always go through `magician-ui`, which backs up + validates.

## Completion Signal

> "Magician CLI UI <enabled (components: …) | updated | disabled>. It runs locally (no tokens) and hot-reloads."

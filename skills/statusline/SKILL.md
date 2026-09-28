---
name: statusline
description: Enable, configure, or disable the Magician CLI status line ("Magician Claude CLI UI") — a lightweight bar showing live context %, a context-rot warning, a token-flow sparkline, model · git · cost, the active skill/workflow/loop, the reasoning effort/mode, the bundled-lore state, and the output-brevity "voice" level. Also sets the output-brevity voice (warrior/scribe/bard) and removes permission entries left by older magician versions. Use when the user says "enable/turn on the magician UI / status line / status bar", "show my context/tokens/effort in the console", "configure/change what the bar shows", "turn off / disable the status line", "make output shorter/leaner / set the voice", or "clean up magician's old permission rules".
allowed-tools: AskUserQuestion, Bash(magician-ui status), Bash(magician-ui voice status)
argument-hint: "[enable · disable · status · set <components> · cleanup]"
---

# /statusline — Magician CLI status line

A native Claude Code **status line** rendered by magician. It runs **locally, consumes zero API tokens**, updates on each message (debounced), and helps you catch **context rot** before it bites. It's driven by the bundled **`magician-ui`** CLI, which edits `~/.claude/settings.json` **safely** (timestamped backup → validate → atomic write; it never leaves settings broken). Backups are mode 0600 and only the newest 3 are kept; an edit that changes nothing writes nothing. `enable`, `set` and `disable` touch only the `statusLine` key; `cleanup` removes only entries on the fixed list older magician versions used, and only when `cli-ui.json` records that they added them (a matching rule the user added too goes with them; see below). Enabling copies the renderer to `~/.claude/magician/statusline.py`, which the `statusLine` command points at.

The status line is **off until the user asks for it**: magician never enables it on its own. Every command that changes settings (`enable`, `set`, `disable`, `cleanup`, `voice <level>`) goes through the normal permission prompt; only the read-only `status` commands are pre-approved.

## Components (user-configurable)

| key | shows |
|---|---|
| `context` | color-coded usage bar + used% + used/size tokens (green <70 · yellow 70–89 · red ≥90) |
| `rot` | a ⚠ at ≥80% and 🔴 at ≥92% so you notice before compaction |
| `spark` | a `▁▂▃▅▇` sparkline of recent context% (the token-flow stream) |
| `meta` | model · git branch · session cost |
| `skill` | the active magician skill / workflow / running-agent count / loop round |
| `effort` | 🧠 the live reasoning **effort** (low/medium/high/xhigh/max) — the default shows on open and tracks `/effort` changes automatically (from Claude Code's `effort.level`) — or the magician **mode** you set, e.g. `ultracode` (which otherwise reports as `xhigh`); say "set mode to ultracode" / "exit ultracode" to change it |
| `lore` | 📚 whether magician's bundled stack lore is shaping the session — `lore:N` (N cores injected) or `lore:off` |
| `voice` | 🗣 the output-brevity **voice** — `voice:warrior` (leanest) · `voice:scribe` (default) · `voice:bard` (standard); set with `magician-ui voice <level>` |

## Actions

- **Enable** — only when the user asks. First confirm which components they want (default: all) with **AskUserQuestion** (multi-select), unless they already said (e.g. "just rot and context"). Then:
  ```bash
  magician-ui enable --all              # everything
  magician-ui enable --only context,rot # a chosen subset
  ```
  A plain `magician-ui enable` (for example to refresh the renderer after an update) keeps the saved components.
- **Change what shows** (no re-enable needed):
  ```bash
  magician-ui set context,rot,spark
  ```
- **Status** — `magician-ui status` (state, components, whether it's wired into settings, and any permission entries an older magician version left behind).
- **Disable** — `magician-ui disable` removes only magician's `statusLine` entry; re-enable anytime on request. `magician-ui disable --purge` also deletes magician's status-line files (the copied `statusline.py`, the `status/` markers and `cli-ui.json`). It refuses, changing nothing, while `cli-ui.json` still records entries for cleanup to remove; `disable --purge --force` deletes the record anyway and leaves those entries in settings. It also refuses while `cli-ui.json` can't be read and settings still has entries an earlier version could have added (allow rules on magician's old list, or `defaultMode` `auto`), since the record might cover them. Suggest `/statusline disable` before the user uninstalls magician, so `statusLine` doesn't keep pointing at the copied renderer.
- **Clean up after older versions** — magician 4.14 and earlier could add permission rules, `permissions.defaultMode` and an auto-mode env key to `~/.claude/settings.json`. `magician-ui cleanup` removes those entries only where `cli-ui.json` records that magician added them (the allow rules, and `defaultMode` set to `auto`), plus the env key and obsolete magician data files. Matching allow rules with no record stay, and cleanup names them; a rule the user also added while the record exists can't be told apart and is removed with magician's, except `Bash(jira:*)` and `Bash(confluence:*)` when the record is from 4.4 or later. Run cleanup before `disable --purge`, which deletes the record (and refuses to while the record is still needed, unless `--force` is given). `magician-ui status` lists what it would remove. Run it only when the user asks, and tell them what it will change first.
- **Unreadable `cli-ui.json`** — if the file exists but can't be read (not valid JSON, or not a JSON object), magician never replaces it. `enable`, `set`, `default`, `lore on|off` and `voice <level>` stop and change nothing; `cleanup` and `disable` do the rest, leave the file as is and say so; `status`, `lore status` and `voice status` note it. Session start keeps reading the file's old values (status markers, the weekly upgrade notice) until it's fixed or deleted. Suggest the user fix the file (then run `cleanup` again if it recorded old entries) or delete it.
- **Permission mode** — magician does not change Claude Code's permission mode or rules. To start in auto mode, the user can press Shift+Tab, pass `--permission-mode auto`, or use `/config`; to save rules, `/permissions`.
- **Voice — output brevity (lower token cost, no quality loss)** — `magician-ui voice warrior|scribe|bard` sets how wordy responses are. Output tokens cost several× input, so leaner output is the cheapest saving. Levels least→most wordy: **`warrior`** (minimal but complete), **`scribe`** (the default — leaner than usual), **`bard`** (standard/native). For warrior/scribe, SessionStart adds a brevity style note to the session context that cuts filler (preambles, recaps, restating the request) while keeping **all** substance and code/commands/errors verbatim — it never compresses prose into fragments or jargon. `magician-ui voice status` shows the current level. Overrides (first match wins): env `MAGICIAN_VOICE` → per-project `.magician/voice` → this setting → default `scribe`. Takes effect next session start; the `🗣 voice:` chip shows it live.

## Rules

- Act only on the user's request. Magician never enables the bar, re-adds it, or suggests it on its own; respect a "no".
- Enabling/disabling changes `~/.claude/settings.json`; it hot-reloads, so the bar appears/updates within a message or two — **no restart needed**.
- Keep it lightweight: recommend a smaller component set if the user wants a minimal bar (e.g. `context,rot`).
- Never hand-edit `settings.json` for this — always go through `magician-ui`, which backs up + validates.

## Obstacles

This is a configuration utility that reports to the human directly, not upward to an orchestrator — so it emits no upward Obstacles block: surface any blocker in prose to the user and stop.

See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

> "Magician CLI UI <enabled (components: …) | updated | disabled | cleaned up>. It runs locally (no tokens) and hot-reloads."

# Context self-management — internals & honest limits

Magician treats the conversation context as a finite resource (per Anthropic's context-engineering guidance): keep it small, keep durable facts outside the transcript, and restore working-state pointers after a compaction. This is driven by the bundled **`ctx`** CLI and a few hooks; `/chronicle` exposes the manual surface.

## What runs automatically (no command needed)

- **Session record** — the `Stop` hook (`chronicle-stop.sh`, async) keeps one small JSON record per session in `${CLAUDE_PLUGIN_DATA}/chronicle/`: branch, commit count, changed-file names and a one-line summary, all taken from git. It reads no prompt, response or transcript content, and keeps the newest 50 records. The plugin's `session_history` option turns it off.
- **Learning capture** — the same hook appends commit subjects from this session that record a decision ("decided", "chose", "switched to", "going with", …) to the per-project learnings file. Session start shows the last 3 under a project-learnings note.
- **After a compaction** — a `SessionStart` hook with the `compact` matcher (`compact-context.sh`) adds working-state pointers taken from git and `.workspace/shared/`: the branch, uncommitted files, this session's commits and the shared artifact paths. It reads no transcript, prompt or summary content.
- **Standing rule** — [lore/subagent-context.md](../../../lore/subagent-context.md) carries the offload rule (pointers over pastes).

## The `ctx` CLI (what `/chronicle` calls)

```
ctx pct --transcript <path>             # current context % (real tokens; ~approx fallback)
ctx learn --list [--n 3]                # recent project learnings
ctx learn --add "<fact>" [--global]     # record a learning (project, or add to references.md)
ctx consolidate                         # show recurring learnings → promotion candidates
```

`ctx pct` takes the transcript path explicitly — it does not search for one. `/chronicle status` passes this session's file, found under `~/.claude/projects/` by the session id (see the status row in [SKILL.md](../SKILL.md#context-size--learnings-ctx)). `ctx pct` scans the file's tail for the latest `usage` entry and uses only the token numbers (`input + cache_read + cache_creation` — the occupancy the model just saw) and the model id. No message content is stored or printed.

Storage, all under the plugin data folder `${CLAUDE_PLUGIN_DATA}` (usually `~/.claude/plugins/data/magician-<marketplace>/`):
- `chronicle/<start-time>-<session-id>.json` — session records.
- `projects/<project-hash>/learnings.jsonl` — per-project learnings; `project-hash` = the first 12 hex characters of the md5 of the project directory path (the same rule as `session-start.sh`).
- `references.md` — the global reference store (`/chronicle remember`, `ctx learn --add … --global`).

The context-window size comes from the transcript's model id; `CLAUDE_CODE_DISABLE_1M_CONTEXT` holds it at 200K, `CTX_MAX` overrides it outright, and an unknown model counts as 200K until the observed tokens exceed that.

## Honest limits (designed around — never claim otherwise)

1. **No live token count** via any plugin API. `ctx pct` reads the latest `usage` numbers in the transcript file it is given — accurate but one turn stale. If the file has no `usage` entry, it falls back to `bytes/4`, tagged `~approx`.
2. **Cannot force, schedule, or steer compaction.** Only the user (`/compact`) or the auto-threshold compacts. Magician does not claim to compact for you, and it does not save conversation content before a compaction.
3. **Cannot know the exact auto-compact threshold** (undocumented). Check `/chronicle status` before a big step and act early.
4. **Cannot inject context into a running subagent.** Subagents get only their spawn prompt — the spawn template ([lore/subagent-context.md](../../../lore/subagent-context.md)) tells every actor to read `.workspace/local/session-state.md` first when it exists. Pointer, not push.

## Keeping context small (the standing playbook)

- Prefer `kg query` + `Read(file:line)` over pasting whole files.
- Persist durable facts via `/chronicle learn` (or `.workspace/shared/decisions/`), not the transcript.
- Offload heavy exploration to subagents (clean context windows; they return distilled summaries).
- When `/chronicle status` shows the window filling up, offload to an artifact and/or run `/compact` (with a focus instruction) before the next big step.
- Add a `# Compact instructions` section to your project `CLAUDE.md` so the built-in compaction always preserves what matters (it survives compaction).
- `ctx` tracks *size*; run **`/usage`** for what's driving your plan limits (broken down by skill, subagent, plugin, MCP) — the two together tell you both how full the window is and what's filling it.

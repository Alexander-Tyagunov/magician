---
name: chronicle
description: Memory and context steward — session history, the reference store (repos, projects, ideas), context size, learnings. Use to review past sessions, remember or recall a reference, or capture learnings.
allowed-tools: Read, Glob, AskUserQuestion, Bash(ctx pct *), Bash(ctx learn --add *), Bash(ctx consolidate), Edit(~/.claude/plugins/data/magician-*/references.md)
argument-hint: "[status | learn <fact> [--global] | consolidate | last N | remember <fact> | references | forget <text> | clear N]"
---

# /chronicle — Memory, History & Context Steward

> **Bundled command:** if `ctx` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/ctx`. If that is missing too (Claude chat ships no plugin tools), say /chronicle needs Claude Code or Cowork.

Three stores, all global to this machine and kept in the magician plugin data folder `${CLAUDE_PLUGIN_DATA}` (they survive across projects and sessions):

- **Session history** — `${CLAUDE_PLUGIN_DATA}/chronicle/` — one small JSON record per session, written from git by the Stop hook (the newest 50 are kept). Turned off by the plugin's `session_history` option.
- **Global references** — `${CLAUDE_PLUGIN_DATA}/references.md` — repos, projects, and ideas worth remembering. Session start adds it to context.
- **Project learnings** — `${CLAUDE_PLUGIN_DATA}/projects/<project-hash>/learnings.jsonl`, managed by the bundled **`ctx`** CLI. The internals and honest limits are in [`references/context-mgmt.md`](references/context-mgmt.md).

## Context size & learnings (`ctx`)

| Command | Does |
|---|---|
| `/chronicle status` | `ctx pct --transcript <path>` → current context %, plus the project learnings count (the first line of `ctx consolidate`). The path is this session's transcript: Glob `*/${CLAUDE_SESSION_ID}.jsonl` under `~/.claude/projects/`. `ctx pct` reads only the token numbers from the file's latest `usage` entry and the model id — no message content is stored or printed. |
| `/chronicle learn "<fact>" [--global]` | `ctx learn --add "<fact>"` (this project) or `ctx learn --add "<fact>" --global` (adds it to references.md). **Confirm before `--global`.** |
| `/chronicle consolidate` | `ctx consolidate` → show recurring project learnings; offer to promote high-frequency ones to global references (**confirm each**). Then read the reviewer memories (below). |

**Reviewer memories (part of `consolidate`).** The `reviewer`, `sentinel` and `simplifier` agents keep project memory, so Claude Code writes a `MEMORY.md` for each under `.claude/agent-memory/<agent>/` (or `.claude/agent-memory-local/<agent>/` for a `memory: local` copy). Glob both folders and Read each `MEMORY.md` that exists. An entry is a finding class seen at least twice, with both `file:line` locations. For each entry, offer a lint rule or one line in `CLAUDE.md` (Anthropic's move for a recurring finding), gated with **AskUserQuestion** (Add / Skip), and write only on Add. `/chronicle` never edits the memory files and never copies them to the global store, because they can name project files (rules: [`lore/deep/review.md#reviewer-memory`](../../lore/deep/review.md#reviewer-memory)).

Honest limits (never overclaim): a plugin cannot read a live token count. `ctx pct` uses the latest `usage` numbers in the transcript file it is given: accurate, one turn stale. A plugin **cannot force or steer compaction**: only the user (`/compact`) or the auto-threshold compacts. Details: [`references/context-mgmt.md`](references/context-mgmt.md).

## Session history

Each record is `${CLAUDE_PLUGIN_DATA}/chronicle/<start-time>-<session-id>.json`: `{ timestamp, session_id, session_start, working_dir, branch, commits, changed_files, summary }` — git facts only, no prompt or response text.

To show the last N sessions (default 10): Glob `${CLAUDE_PLUGIN_DATA}/chronicle/*.json`, take the newest N (the file names start with the session start time, so they sort by time), Read each, and print one line per record: date · branch · summary.

## Global references (cross-session memory)

The reference store holds things you want every future session to know: repositories you work in, projects and their goals, and ideas to revisit. Session start adds it to context, so once remembered, a fact is available everywhere.

It is deliberately an **explicit, legible artifact**: a plain markdown file the user can read and edit directly (an "idea file" / personal knowledge base), not opaque implicit memory. Keep entries terse and durable, and prune stale ones with `forget`. An overgrown store distracts the model more than it helps.

**Always confirm before you write to or delete from the global store**, because it persists across all projects. State exactly what you will save or remove, then gate with **AskUserQuestion** (Approve / Cancel). End your turn at the call and act only on Approve.

To **view** the store: Read `${CLAUDE_PLUGIN_DATA}/references.md` (if it does not exist, say "no references yet").

To **remember** a fact (after the user confirms): classify it as `Repositories`, `Projects` or `Ideas`, then edit `${CLAUDE_PLUGIN_DATA}/references.md` — add a `- <entry>` line directly under the `## <Section>` heading. If the file does not exist, create it starting with:

```markdown
# Magician — Global References
<!-- Remembered across all sessions. Managed by /chronicle. -->
```

and add the `## <Section>` heading if it is absent.

To **forget**, show the matching lines, confirm, then remove them with an Edit.

## Process

1. Parse the request from `$ARGUMENTS` (or ask): `status`, `learn <fact> [--global]`, `consolidate`, `last N`, `branch X`, `since DATE`, `clear N`, `remember <fact>`, `references`, `forget <text>`. **If you must ask, end your turn and wait.**
2. For reads (history view, `references`, `status`): read or run, then present the results.
3. For `remember` / `learn --global`: classify the fact and state what you will save. Then gate with **AskUserQuestion** (Save / Cancel), end your turn at the call, and write only on Save. The global store persists across all projects. Project-scoped `learn` (no `--global`) needs no confirmation question. It is local and cheap.
4. For `forget` / `clear` / `consolidate` pruning: show what will be removed. Then gate with **AskUserQuestion** (Delete / Cancel) before you remove anything, because this is permanent. End your turn at the call and delete only on Delete.

## Clearing old chronicles (uses the N you were given)

List the records older than N days:

```bash
find "${CLAUDE_PLUGIN_DATA}/chronicle" -name '*.json' -mtime +N
```

Show the list, confirm with **AskUserQuestion** (Delete / Cancel), and only on Delete remove exactly those files with `rm`. Claude Code asks for permission before the `rm` — that prompt is expected for a permanent delete. The Stop hook already keeps only the newest 50 records, so this is only needed to drop older history sooner.

## Model note

If a remembered project would benefit from a more capable model than the current session (see [`lore/models.md`](../../lore/models.md)), mention it when the reference surfaces. Do not switch silently.

## Obstacles

`/chronicle` is the persistence target for the plugin's obstacle memory. The consumer skills (`/orchestrate`, `/weave`, `/scrutinize`, `/divine`, `/transmute`, `/manifest`) route a confirmed recurring obstacle pattern here through `ctx learn --add "<fact>" [--global]`, which this skill wraps. A future run then reads it up front and pre-empts the obstacle.

As the confirm-before-global gate, it redacts secrets, credentials and PII and persists a distilled, self-authored signature, never verbatim untrusted worker text. So a poisoned or sensitive obstacle cannot ride into memory that a later run acts on. It is not itself dispatched as a work unit, so it emits no upward Obstacles block. See [`lore/obstacles.md`](../../lore/obstacles.md).

## Completion Signal

"Chronicle done. <N sessions recorded> · <M references stored>."

---
name: almanac
description: One-time workspace setup — creates the .workspace/ structure, .gitignore entries and a lean CLAUDE.md, then suggests relevant MCPs and permission rules you can add yourself with /permissions. Writes no Claude Code settings. Run once per project.
allowed-tools: Read, AskUserQuestion, Bash(mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans .workspace/shared/research .workspace/shared/postmortems), Bash(mkdir -p .workspace/local), Edit(./.workspace/**), Edit(./.gitignore), Edit(./CLAUDE.md), Edit(~/.claude/plugins/data/magician-*/workspace-strategy.json), Bash(git add .workspace/shared/ CLAUDE.md .gitignore), Bash(git commit -m *)
disable-model-invocation: true
---

# /almanac — Workspace Initialization

Set up the magician workspace for this project. Run once per project.

## What Gets Created

```
.workspace/
├── shared/           ← committed to git
│   ├── context.md    current team state and open decisions
│   ├── roadmap.md    feature priorities
│   ├── decisions/    architecture decision records
│   ├── specs/        /conjure design specs
│   └── postmortems/  /autopsy outputs
└── local/            ← always gitignored
    ├── prefs.md      per-machine preferences
    └── session.md    last session state
```

Almanac never edits Claude Code settings files (`.claude/settings*.json` or `~/.claude/settings.json`) and never changes the permission mode. Permission rules are only suggested in chat (step 6) for the user to add with `/permissions`.

## Process

### 1. Workspace Mode Decision

If `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json` exists (written by step 8 of an earlier run on this machine), Read it first and put the mode it records first in the options, labelled "(last used)".

Use the `AskUserQuestion` tool with the **Workspace Mode** configuration in [references/setup-questions.md](references/setup-questions.md) — do not write any text before calling it.

**Wait for reply before creating any directories or files.** Remember the selected mode (Shared or Private) — it controls steps 3, 8, and 9.

### 2. Create Directory Structure
```bash
mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans .workspace/shared/research .workspace/shared/postmortems
mkdir -p .workspace/local
```

### 3. Configure .gitignore
Append to .gitignore (or create it):
```
# Magician workspace (local machine only)
.workspace/local/
```
If private mode: `.workspace/` instead.

### 4. Create Initial Files

`.workspace/shared/context.md`:
```markdown
# Project Context

**Stack:** <from inspector>
**Archetype:** <from inspector>
**Started:** <today's date>

## Open Decisions
(none yet)

## Current Focus
(describe what you're working on)
```

`.workspace/shared/roadmap.md`:
```markdown
# Roadmap

## In Progress
(none yet)

## Planned
(none yet)

## Completed
(none yet)
```

`.workspace/local/prefs.md`:
```markdown
# Local Preferences

disableGit: false
# Set disableGit: true to skip worktrees and PR flow
```

### 5. Minimal CLAUDE.md
If no CLAUDE.md exists, create a lean one:
```markdown
# Project Rules

(Add earned rules here — only what Claude consistently gets wrong.)
```
Do not write generic best practices. CLAUDE.md should only contain rules specific to this project.

### 6. Permission Suggestions (guidance only)

Use the `AskUserQuestion` tool with the **Permission suggestions** configuration in [references/setup-questions.md](references/setup-questions.md) — do not write any text before calling it.

If **Show suggestions**: print a short list in chat, built from the detected stack, and write nothing:
- **Allow** — the project's own test, lint and build commands, each named with its subcommand (for example `Bash(npm test *)`, `Bash(npm run lint *)`, `Bash(pytest *)`, `Bash(go test *)`). Never suggest a whole CLI (`Bash(git *)`, `Bash(npm *)`), an interpreter, or a package launcher.
- **Deny** — files that should stay off-limits to Claude (for example `Read(./.env)`, `Read(./.env.*)`, `Read(./secrets/**)`, plus any credential files you noticed while inspecting the project).

Then tell the user they can add any of these with `/permissions` (or by editing their own settings). If **Skip**: continue.

### 7. MCP Suggestions
Based on detected archetype, mention MCP servers that could help:
- web: browser automation MCP for UI testing
- data: notebook MCP for Jupyter integration
- devops: cloud provider CLI MCPs

Adding an MCP server changes Claude Code's configuration, so almanac does not install one. If the user wants one, point them to that server's install instructions (a `/plugin` entry or the `claude mcp add …` command for them to run).

### 8. Save Strategy
Record the workspace mode chosen in step 1 in `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json` — the magician plugin data folder; step 1 of a later run reads it. No hook reads it. Read the file first if it exists, then write it with exactly one of:
- Shared mode (only `.workspace/local/` is gitignored): `{"mode": "shared", "ignored": "false"}`
- Private mode (the whole `.workspace/` is gitignored): `{"mode": "private", "ignored": "true"}`

### 9. Commit (if shared mode)
```bash
git add .workspace/shared/ CLAUDE.md .gitignore
git commit -m "chore: initialize magician workspace"
```

## Obstacles

This is a terminal, user-facing skill — it reports to the human directly, not upward to an orchestrator — so it emits no upward Obstacles block: surface any blocker in prose to the user and stop.

See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Almanac complete. Workspace initialized in <mode> mode. Run /conjure to start designing, or /manifest for the full flow."

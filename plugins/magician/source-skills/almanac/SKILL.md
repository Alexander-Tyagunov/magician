---
name: almanac
description: One-time workspace setup — creates .workspace/ structure, .gitignore entries, a lean CLAUDE.md, a permissions allowlist, and suggests relevant MCPs. Run once per project.
allowed-tools: Bash(mkdir:*), Bash(git add:*), Bash(git commit:*), Bash(python3:*), Read, Write, AskUserQuestion
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

## Process

### 1. Workspace Mode Decision

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

### 6. Permissions Allowlist

Build the suggested list based on detected stack. Then use the `AskUserQuestion` tool with the **Permissions** configuration in [references/setup-questions.md](references/setup-questions.md) — do not write any text before calling it.

**Wait for reply before writing to settings.json.**

If **Add all**: first ask about Playwright access using the **Playwright** configurations in [references/setup-questions.md](references/setup-questions.md), then write the full set to `.claude/settings.json` using the script in [references/settings-writer.md](references/settings-writer.md).

If **Choose** or **Skip**: follow the guidance in [references/setup-questions.md](references/setup-questions.md).

### 7. MCP Suggestions
Based on detected archetype, suggest relevant MCPs:
- web: browser automation MCP for UI testing
- data: notebook MCP for Jupyter integration
- devops: cloud provider CLI MCPs

Ask: "Want me to set up any of these MCPs? If so, which ones?" **End your turn. Wait for their reply before proceeding to step 8.**

### 8. Save Strategy
Record the workspace mode chosen in step 1. Set `WS_MODE` to the user's actual selection (`shared` or `private`) — do not hardcode it:
```bash
# WS_MODE is "shared" or "private" from the step 1 answer.
WS_MODE=shared   # ← replace with the user's actual choice
python3 -c "
import json, os, sys
mode = sys.argv[1]
# SHARED: only .workspace/local/ is gitignored. PRIVATE: whole .workspace/ is gitignored.
data = {'mode': mode, 'ignored': 'false' if mode == 'shared' else 'true'}
path = os.path.expanduser('~/.local/share/magician/workspace-strategy.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(data, open(path,'w'))
print('Strategy saved:', data)
" "$WS_MODE"
```

### 9. Commit (if shared mode)
```bash
git add .workspace/shared/ CLAUDE.md .gitignore
git commit -m "chore: initialize magician workspace"
```

## Completion Signal

"Almanac complete. Workspace initialized in <mode> mode. Run /conjure to start designing, or /manifest for the full flow."

---
name: almanac
description: Initializes the workspace system — directory structure, CLAUDE.md, permissions, MCP suggestions
keep-coding-instructions: true
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
Ask: "Should `.workspace/shared/` be committed to git (shared team context) or kept entirely local (private machine)?"

- **Shared mode**: `.workspace/local/` gitignored, `.workspace/shared/` committed
- **Private mode**: entire `.workspace/` gitignored

**End your turn. Wait for their reply before creating any directories or files.**

### 2. Create Directory Structure
```bash
mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/postmortems
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
Suggest based on detected stack:
- JavaScript/TypeScript: `Allow: Bash(npm *)`, `Allow: Bash(npx *)`
- Python: `Allow: Bash(pytest *)`, `Allow: Bash(ruff *)`
- Go: `Allow: Bash(go *)`
- Always: `Allow: Bash(git *)`, `Allow: Read(**)`

Ask: "I'd suggest adding these permission rules to settings.json — shall I add them? (yes / no / let me choose)" **End your turn. Wait for confirmation before writing to settings.json.**

### 7. MCP Suggestions
Based on detected archetype, suggest relevant MCPs:
- web: browser automation MCP for UI testing
- data: notebook MCP for Jupyter integration
- devops: cloud provider CLI MCPs

Ask: "Want me to set up any of these MCPs? If so, which ones?" **End your turn. Wait for their reply before proceeding to step 8.**

### 8. Save Strategy
Record workspace mode:
```bash
python3 -c "
import json, os
data = {'ignored': 'true', 'mode': 'shared'}
path = os.path.expanduser('~/.local/share/magician/workspace-strategy.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(data, open(path,'w'))
print('Strategy saved.')
"
```

### 9. Commit (if shared mode)
```bash
git add .workspace/shared/ CLAUDE.md .gitignore
git commit -m "chore: initialize magician workspace"
```

## Completion Signal

"Almanac complete. Workspace initialized in <mode> mode. Run /conjure to start designing, or /manifest for the full flow."

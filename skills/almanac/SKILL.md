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

Use the `AskUserQuestion` tool with this configuration — do not write any text before calling it:

```json
{
  "questions": [
    {
      "question": "Should .workspace/shared/ be committed to git?",
      "header": "Workspace",
      "multiSelect": false,
      "options": [
        {
          "label": "Shared (Recommended)",
          "description": "Specs, designs, roadmap, and decisions live in .workspace/shared/ and commit to git. Team members pull the same context. Only per-machine prefs stay in .workspace/local/ (always gitignored)."
        },
        {
          "label": "Private",
          "description": "The entire .workspace/ directory is gitignored. Context stays on this machine only — no sharing with teammates via git."
        }
      ]
    }
  ]
}
```

**Wait for reply before creating any directories or files.**

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

Build the suggested list based on detected stack. Then use the `AskUserQuestion` tool — do not write any text before calling it:

```json
{
  "questions": [
    {
      "question": "Add permission rules to .claude/settings.json so Claude Code doesn't prompt for approval on routine operations?",
      "header": "Permissions",
      "multiSelect": false,
      "options": [
        {
          "label": "Add all (Recommended)",
          "description": "Three groups: (1) Core — git commands and reading any project file; (2) Workspace — writing specs, designs, and decision records to .workspace/**, reading session state, resetting event logs between visual companion screens; (3) Stack tools — the build/test/lint commands for your detected stack (npm, pytest, go, etc.). These cover everything Magician does routinely so you never see an approval prompt mid-flow."
        },
        {
          "label": "Choose",
          "description": "I'll show each group separately so you can pick which ones to add."
        },
        {
          "label": "Skip",
          "description": "No rules added. You'll approve each git command, file read, and workspace write individually."
        }
      ]
    }
  ]
}
```

**Wait for reply before writing to settings.json.**

If **Add all**: write the full set to `.claude/settings.json`:

```python
import json, os

path = ".claude/settings.json"
s = json.load(open(path)) if os.path.exists(path) else {}
s.setdefault("permissions", {}).setdefault("allow", [])

# Always
base = [
    "Bash(git *)",
    "Read(**)",
    "Write(.workspace/**)",
    "Read(.workspace/**)",
    "Bash(> .workspace/**)",
    "Bash(mkdir* .workspace/**)",
    "mcp__playwright__browser_navigate(*)",
    "mcp__playwright__browser_take_screenshot(*)",
    "mcp__playwright__browser_wait_for(*)",
    "mcp__playwright__browser_snapshot(*)",
    "mcp__playwright__browser_close(*)",
    "Bash(bash *conjure/scripts/vc-*.sh*)",
    "Bash(node *conjure/scripts/server.cjs*)",
    "Bash(open http://localhost:*)",
]
# Stack-specific (add only what was detected)
stack_rules = {
    "javascript": ["Bash(npm *)", "Bash(npx *)"],
    "python":     ["Bash(pytest *)", "Bash(ruff *)", "Bash(pip *)"],
    "go":         ["Bash(go *)"],
    "rust":       ["Bash(cargo *)"],
    "java":       ["Bash(mvn *)", "Bash(gradle *)"],
}
# DETECTED_STACK comes from inspector additionalContext
detected = []  # fill from inspector context
for tech, rules in stack_rules.items():
    if tech in detected:
        base.extend(rules)

for r in base:
    if r not in s["permissions"]["allow"]:
        s["permissions"]["allow"].append(r)

os.makedirs(".claude", exist_ok=True)
json.dump(s, open(path, "w"), indent=2)
print("Permissions saved.")
```

If **Choose**: present each group with its own `AskUserQuestion` call (core, workspace, stack tools) — one at a time, wait for each reply.

If **Skip**: continue. Do not ask again this session.

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

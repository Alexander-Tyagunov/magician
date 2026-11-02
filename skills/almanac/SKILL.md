---
name: almanac
description: One-time workspace setup — .workspace/, .gitignore, a lean CLAUDE.md, optional REVIEW.md and verify/simplify skills, MCP and permission suggestions; writes no settings. Run once per project.
allowed-tools: Read, AskUserQuestion, Bash(mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans .workspace/shared/research .workspace/shared/postmortems), Bash(mkdir -p .workspace/local), Edit(./.workspace/**), Edit(./.gitignore), Edit(./CLAUDE.md), Edit(./REVIEW.md), Edit(./.claude/skills/verify/SKILL.md), Edit(./.claude/skills/simplify/SKILL.md), Edit(~/.claude/plugins/data/magician-*/workspace-strategy.json), Bash(git add .workspace/shared/ CLAUDE.md .gitignore), Bash(git add REVIEW.md), Bash(git add .claude/skills/verify/SKILL.md), Bash(git add .claude/skills/simplify/SKILL.md), Bash(git commit -m *)
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

Almanac never edits Claude Code settings files (`.claude/settings*.json` or `~/.claude/settings.json`) and never changes the permission mode. Permission rules are only suggested in chat (step 7) for the user to add with `/permissions`. Step 6 can add three more files: `REVIEW.md` and two short project skills under `.claude/skills/`.

## Process

### 1. Workspace Mode Decision

If `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json` exists (written by step 9 of an earlier run on this machine), Read it first and put the mode it records first in the options, labelled "(last used)".

Use the `AskUserQuestion` tool with the **Workspace Mode** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it.

**Wait for reply before creating any directories or files.** Remember the selected mode (Shared or Private) — it controls steps 3, 9, and 10.

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
If no `CLAUDE.md` exists, create a lean one:
```markdown
# Project Rules

(Add earned rules here — only what Claude consistently gets wrong.)
```
Do not write generic best practices. `CLAUDE.md` should only contain rules specific to this project.

### 6. Review setup (REVIEW.md and pre-commit skills)

Use the `AskUserQuestion` tool with the **Review setup** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it. Wait for the reply. Skip every write below that the reply did not select.

**`REVIEW.md`**: if the file does not exist, create it from the template part of [`skills/divine/references/review-md-template.md`](../divine/references/review-md-template.md) (everything below its marker line). Fill `<repository name>` and, from the detected stack, the obvious skip paths (lock files, generated folders, vendored code). Leave the other placeholders for the code owners and say so. `/divine` and `/scrutinize` read it before every review ([`lore/review.md`](../../lore/review.md)). If the file exists, leave it as it is.

**`.claude/skills/verify/SKILL.md`**: since Claude Code 2.1.286, a non-bundled skill named `verify` or `simplify` that Claude may invoke runs before each commit. Write the delegator below, exactly, if the file does not exist. It must stay model-invocable (no `disable-model-invocation`), or the pre-commit run does not happen.

```markdown
---
name: verify
description: Pre-commit verification for this project. Claude Code runs it before each commit. Delegates to magician's certify skill.
---

# verify

Run the magician `certify` skill (`/magician:certify`) on the change about to be committed, and report its result.
Do not commit while any check fails.
If the magician plugin is not installed, run the project's own test, lint and build commands and report their exit codes.
```

**`.claude/skills/simplify/SKILL.md`** (optional): the same shape, delegating to the simplification lens.

```markdown
---
name: simplify
description: Pre-commit simplification pass for this project. Claude Code runs it before each commit. Delegates to magician's scrutinize skill.
---

# simplify

Run the magician `scrutinize` skill with `--lens simplifier` (`/magician:scrutinize --lens simplifier`) on the diff about to be committed.
Fix any Important finding before the commit. Skip Nits.
If the magician plugin is not installed, say so and stop.
```

Tell the user two things. A project `verify` skill replaces Claude Code's bundled `/verify` command of the same name (an alias keeps the bundled one). And `/seal` skips its own simplify pass when these skills exist, so the work is not done twice. The delegators are short on purpose. A project that wants its own recipe edits them, and the plugin behavior stays in the plugin.

### 7. Permission Suggestions (guidance only)

Use the `AskUserQuestion` tool with the **Permission suggestions** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it.

If **Show suggestions**: print a short list in chat, built from the detected stack, and write nothing:
- **Allow** — the project's own test, lint and build commands, each named with its subcommand (for example `Bash(npm test *)`, `Bash(npm run lint *)`, `Bash(pytest *)`, `Bash(go test *)`). Never suggest a whole CLI (`Bash(git *)`, `Bash(npm *)`), an interpreter, or a package launcher.
- **Deny** — files that should stay off-limits to Claude (for example `Read(./.env)`, `Read(./.env.*)`, `Read(./secrets/**)`, plus any credential files you noticed while inspecting the project).

Then tell the user they can add any of these with `/permissions` (or by editing their own settings). If **Skip**: continue.

Add one more line to the same list: STE-lite, magician's simplified technical English for prose, is off by default. To turn it on, the user runs `magician-ui ste on` or creates a `.magician/ste` file with the content `on`. Write no file for it.

### 8. MCP Suggestions
Based on detected archetype, mention MCP servers that could help:
- web: browser automation MCP for UI testing
- data: notebook MCP for Jupyter integration
- devops: cloud provider CLI MCPs

An MCP server changes Claude Code's configuration, so almanac does not install one. If the user wants one, point them to that server's install instructions (a `/plugin` entry or the `claude mcp add …` command for them to run).

### 9. Save Strategy
Record the workspace mode chosen in step 1 in `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json`, the magician plugin data folder. Step 1 of a later run reads it. No hook reads it. Read the file first if it exists, then write it with exactly one of:
- Shared mode (only `.workspace/local/` is gitignored): `{"mode": "shared", "ignored": "false"}`
- Private mode (the whole `.workspace/` is gitignored): `{"mode": "private", "ignored": "true"}`

### 10. Commit (if shared mode)
```bash
git add .workspace/shared/ CLAUDE.md .gitignore
git add REVIEW.md
git add .claude/skills/verify/SKILL.md
git add .claude/skills/simplify/SKILL.md
git commit -m "chore: initialize magician workspace"
```
Run only the `git add` lines for files step 6 wrote. Each is a separate exact command, so a skipped file never breaks the staging.

## Obstacles

This is a terminal, user-facing skill. It reports to the human directly, not upward to an orchestrator, so it emits no upward Obstacles block. Surface any blocker in prose to the user and stop.

See [`lore/obstacles.md`](../../lore/obstacles.md).

## Completion Signal

"Almanac complete. Workspace initialized in <mode> mode. Run /conjure to start designing, or /manifest for the full flow."

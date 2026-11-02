---
name: almanac
description: One-time workspace setup — .workspace/, .gitignore, a lean CLAUDE.md, optional AGENTS.md and REVIEW.md; writes no settings. Run once per project.
allowed-tools: Read, AskUserQuestion, Bash(mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans .workspace/shared/research .workspace/shared/postmortems), Bash(mkdir -p .workspace/local), Edit(./.workspace/**), Edit(./.gitignore), Edit(./CLAUDE.md), Edit(./AGENTS.md), Edit(./REVIEW.md), Edit(./.claude/skills/verify/SKILL.md), Edit(./.claude/skills/simplify/SKILL.md), Edit(~/.claude/plugins/data/magician-*/workspace-strategy.json), Bash(git add .workspace/shared/ CLAUDE.md .gitignore), Bash(git add AGENTS.md), Bash(git add REVIEW.md), Bash(git add .claude/skills/verify/SKILL.md), Bash(git add .claude/skills/simplify/SKILL.md), Bash(git commit -m *)
disable-model-invocation: true
---

# /almanac — Workspace Initialization

## When to use

Once per project, on request: create `.workspace/`, update `.gitignore`, write a lean `CLAUDE.md`, and optionally `AGENTS.md`, `REVIEW.md` and project verify/simplify skills, with MCP and permission suggestions only (it writes no settings). Not for a project that already has a `.workspace/`.

## What Gets Created

`.workspace/shared/` (committed in Shared mode): `context.md`, `roadmap.md`, and `decisions/`, `specs/`, `plans/`, `research/`, `postmortems/`. `.workspace/local/` (always gitignored): `prefs.md` and per-machine session state.

Almanac never edits Claude Code settings files (`.claude/settings*.json` or `~/.claude/settings.json`) and never changes the permission mode. Permission rules are only suggested in chat (step 7) for the user to add with `/permissions`. Step 5 can add `AGENTS.md`. Step 6 can add `REVIEW.md` and two short project skills under `.claude/skills/`. Step 9 can add `north-star.md` and a hook template under `.workspace/shared/`.

## Process

### 1. Workspace Mode Decision

If `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json` exists (written by step 10 of an earlier run on this machine), Read it first and put the mode it records first in the options, labelled "(last used)".

Use the `AskUserQuestion` tool with the **Workspace Mode** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it.

**Wait for reply before creating any directories or files.** Remember the selected mode (Shared or Private) — it controls steps 3, 10 and 11.

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

Write `.workspace/shared/context.md`, `.workspace/shared/roadmap.md` and `.workspace/local/prefs.md` from [`references/file-templates.md`](references/file-templates.md#step-4-initial-workspace-files). Fill the stack and archetype from the detected stack.

### 5. Minimal CLAUDE.md (and optional AGENTS.md)

Use the `AskUserQuestion` tool with the **Instructions file** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it. Wait for the reply.

If no `CLAUDE.md` exists, create a lean one:
```markdown
# Project Rules

(Add earned rules here — only what Claude consistently gets wrong.)
```
Do not write generic best practices. `CLAUDE.md` should only contain rules specific to this project.

Codex and other agents read `AGENTS.md`. Claude Code reads it through the `@AGENTS.md` import, so the commands are in one file. If the reply is **`AGENTS.md` + `CLAUDE.md` import**:
- If `AGENTS.md` does not exist, write it from [`references/agents-md-template.md`](references/agents-md-template.md) (everything below its marker line, 40 lines or fewer). Fill the commands from the detected stack. If `AGENTS.md` exists, never overwrite it.
- Make `@AGENTS.md` the first line of `CLAUDE.md`, above `# Project Rules`. If `CLAUDE.md` exists and has no `@AGENTS.md` line, add only that line at the top and change nothing else.

### 6. Review setup (REVIEW.md and pre-commit skills)

Use the `AskUserQuestion` tool with the **Review setup** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it. Wait for the reply. Skip every write below that the reply did not select.

**`REVIEW.md`**: write it as [`references/file-templates.md`](references/file-templates.md#step-6-reviewmd) says, if the file does not exist. `/divine` and `/scrutinize` read it before every review.

**`.claude/skills/verify/SKILL.md`** and **`.claude/skills/simplify/SKILL.md`**: since Claude Code 2.1.286, a non-bundled skill named `verify` or `simplify` that Claude may invoke runs before each commit. Write each selected delegator exactly as [`references/file-templates.md`](references/file-templates.md#step-6-pre-commit-skills) gives it, if the file does not exist. It must stay model-invocable (no `disable-model-invocation`), or the pre-commit run does not happen. Then tell the user the two notes in that reference.

### 7. Permission Suggestions (guidance only)

Use the `AskUserQuestion` tool with the **Permission suggestions** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it. Act on the reply as that reference says below the configuration. Write nothing.

### 8. MCP Suggestions
Based on detected archetype, mention MCP servers that could help:
- web: browser automation MCP for UI testing
- data: notebook MCP for Jupyter integration
- devops: cloud provider CLI MCPs

State the tool budget with the suggestions: tool choice degrades above about 30–50 tool definitions ([`lore/skill-authoring.md`](../../lore/skill-authoring.md#tool-budget)). Suggest deferred loading (ToolSearch) for a rarely used server.

An MCP server changes Claude Code's configuration, so almanac does not install one. If the user wants one, point them to that server's install instructions (a `/plugin` entry or the `claude mcp add …` command for them to run).

### 9. Optional extras

Use the `AskUserQuestion` tool with the **Optional extras** configuration in [`references/setup-questions.md`](references/setup-questions.md) — do not write any text before calling it. Wait for the reply. For each selected extra, follow [`references/optional-setup.md`](references/optional-setup.md): a one-paragraph `.workspace/shared/north-star.md`, a production-gate hook template at `.workspace/shared/hooks/production-gate.sh` (never installed), or cost-attribution hints in chat.

### 10. Save Strategy
Record the workspace mode chosen in step 1 in `${CLAUDE_PLUGIN_DATA}/workspace-strategy.json`, the magician plugin data folder. Step 1 of a later run reads it. No hook reads it. Read the file first if it exists, then write it with exactly one of:
- Shared mode (only `.workspace/local/` is gitignored): `{"mode": "shared", "ignored": "false"}`
- Private mode (the whole `.workspace/` is gitignored): `{"mode": "private", "ignored": "true"}`

### 11. Commit (if shared mode)
```bash
git add .workspace/shared/ CLAUDE.md .gitignore
git add AGENTS.md
git add REVIEW.md
git add .claude/skills/verify/SKILL.md
git add .claude/skills/simplify/SKILL.md
git commit -m "chore: initialize magician workspace"
```
The first line also stages the step 9 files. Run the other lines only for files steps 5 and 6 wrote. Each is a separate exact command, so a skipped file never breaks the staging.

## Obstacles

This is a terminal, user-facing skill. It reports to the human directly, not upward to an orchestrator, so it emits no upward Obstacles block. Surface any blocker in prose to the user and stop.

See [`lore/obstacles.md`](../../lore/obstacles.md).

## Completion Signal

"Almanac complete. Workspace initialized in <mode> mode. Run /conjure to start designing, or /manifest for the full flow."

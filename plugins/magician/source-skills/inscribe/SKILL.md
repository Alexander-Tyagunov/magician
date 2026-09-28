---
name: inscribe
description: Creates a new reusable project skill from a workflow worth capturing, written to .claude/skills/NAME/SKILL.md in the current repo. Use to scaffold a new SKILL.md.
allowed-tools: Read, Glob, AskUserQuestion, Edit(./.claude/skills/**), Bash(git commit -m *)
disable-model-invocation: true
argument-hint: "[skill-name or pattern description]"
---

# /inscribe — Write New Skills

Create a new project skill from a recurring pattern. Claude Code loads project skills from `.claude/skills/<name>/SKILL.md` in the repository, so that is where the new skill goes.

## When to Use

- User explicitly requests a new skill
- You observe a workflow worth capturing and the user wants it saved as a skill

## Process

1. **Understand the pattern** — ask: "What is the behavior you want to capture as a skill? Describe it in a sentence or two." **End your turn. Wait for their description before naming or drafting anything.**
2. **Name it** — one word, verb-like, lowercase (e.g., `migrate`, `localize`, `document`). Glob `.claude/skills/*/SKILL.md` first so the name doesn't collide with an existing project skill.
3. **Define the scope** — what does the skill do, where does it start, where does it end
4. **Draft the skill**:

```
---
# Required: a specific description naming the trigger context (used for auto-invocation).
# Use a >- block if the description contains ": " (colon + space).
description: <one sentence; name when/why to use this skill and the trigger context>
# Optional: short slug name (defaults to the directory name)
name: <name>
# Recommended: scope tools to reduce permission prompts, e.g. Read, Edit(./src/**), Bash(git status)
# Never grant bare Bash, Write, WebFetch or WebSearch, a whole CLI (Bash(git *)), or an
# interpreter or shell; scope each command, e.g. Bash(npm test *).
# allowed-tools: <comma-separated tools>
# For side-effectful or standalone skills, prevent silent auto-invocation:
# disable-model-invocation: true
# Optional: hint shown for arguments. Always a double-quoted string (write an inner " as \").
# argument-hint: "[arg description]"
# For heavy read-only skills, run in a forked context to keep the main thread lean:
# context: fork
---

# /<name> — <Title>

<One paragraph describing the skill's purpose and when to use it.>

## Process

1. <step>
2. <step>
...

## Obstacles

State how this skill surfaces obstacles. If it does dispatchable work, include the producer block. If it dispatches/consumes workers, include roll-up + detect-pattern + memorize (`ctx learn`) wiring. If it is terminal/utility, a one-line note that it reports to the human in prose. The block format is described in magician's lore/obstacles.md.

## Completion Signal

"<name> complete. <what was accomplished>."
```

Quote any other frontmatter value that contains `: ` or `#`, or that starts with `[ { | > ! & * '` or `"`, so it parses as a plain string.

5. **Write to disk** — write the drafted content to `.claude/skills/<name>/SKILL.md` (writing the file creates the folders).

6. **Test it** — invoke the skill once to verify it works as expected

7. **Commit** — only after the user confirms they want it committed:
```bash
git add .claude/skills/<name>/
git commit -m "feat: add /<name> skill"
```

8. Say: "Skill /<name> created in .claude/skills/<name>/. If /<name> does not show up yet, restart Claude Code."

## Skill Quality Checklist

- [ ] Frontmatter uses only valid fields (description, name, allowed-tools, disable-model-invocation, argument-hint, context), parses as strict YAML, and has a specific description
- [ ] `allowed-tools` is scoped: no bare Bash/Write/WebFetch/WebSearch, no whole-CLI or interpreter grants, file writes as `Edit(<path>)`
- [ ] SKILL.md stays lean (<~250 lines); heavy reference material lives in references/ and is linked
- [ ] Has a clear completion signal
- [ ] Has an `## Obstacles` section — a producer block if it does dispatchable work, roll-up/detect/memorize wiring if it consumes workers, or a one-line terminal note otherwise (see lore/obstacles.md)
- [ ] Process steps are concrete and actionable (not vague)
- [ ] Does not duplicate an existing skill
- [ ] Name is memorable and matches the behavior

## Obstacles

/inscribe is an interactive, user-facing scaffolder — it reports to the human, not upward — so it emits no upward Obstacles block: surface any blocker in prose to the user and stop. See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Inscribe complete. New skill /<name> ready. Invoke it with /<name>."

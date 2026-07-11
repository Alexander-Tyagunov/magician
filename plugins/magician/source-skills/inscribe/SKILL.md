---
name: inscribe
description: Creates a new reusable skill — can be suggested by the pattern detector after repeated requests. Use to scaffold a new SKILL.md.
allowed-tools: Read, Write, Edit, Bash(mkdir:*), Bash(git add:*), Bash(git commit:*)
disable-model-invocation: true
argument-hint: [skill-name or pattern description]
---

# /inscribe — Write New Skills

Create a new magician skill from a recurring pattern.

## When to Use

- User explicitly requests a new skill
- Pattern detector (UserPromptSubmit hook) reaches threshold of 5 repetitions
- You observe a workflow worth capturing

## Process

1. **Understand the pattern** — ask: "What is the behavior you want to capture as a skill? Describe it in a sentence or two." **End your turn. Wait for their description before naming or drafting anything.**
2. **Name it** — one word, verb-like, lowercase (e.g., `migrate`, `localize`, `document`)
3. **Define the scope** — what does the skill do, where does it start, where does it end
4. **Draft the skill**:

```
---
# Required: a specific description naming the trigger context (used for auto-invocation)
description: <one sentence; name when/why to use this skill and the trigger context>
# Optional: short slug name (defaults to the directory name)
name: <name>
# Recommended: scope tools to reduce permission prompts, e.g. Read, Edit, Bash(git:*)
# allowed-tools: <comma-separated tools>
# For side-effectful or standalone skills, prevent silent auto-invocation:
# disable-model-invocation: true
# Optional: hint shown for arguments
# argument-hint: [arg description]
# For heavy read-only skills, run in a forked context to keep the main thread lean:
# context: fork
---

# /<name> — <Title>

<One paragraph describing the skill's purpose and when to use it.>

## Process

1. <step>
2. <step>
...

## Completion Signal

"<name> complete. <what was accomplished>."
```

5. **Write to disk**:
```bash
mkdir -p skills/<name>
# Write the skill content to skills/<name>/SKILL.md
```

6. **Test it** — invoke the skill once to verify it works as expected

7. **Commit**:
```bash
git add skills/<name>/
git commit -m "feat: add /<name> skill"
```

8. Say: "Skill /<name> created and available immediately."

## Skill Quality Checklist

- [ ] Frontmatter uses only valid fields (description, name, allowed-tools, disable-model-invocation, argument-hint, context) and has a specific description
- [ ] SKILL.md stays lean (<~250 lines); heavy reference material lives in references/ and is linked
- [ ] Has a clear completion signal
- [ ] Process steps are concrete and actionable (not vague)
- [ ] Does not duplicate an existing skill
- [ ] Name is memorable and matches the behavior

## Completion Signal

"Inscribe complete. New skill /<name> ready. Invoke it with /<name>."

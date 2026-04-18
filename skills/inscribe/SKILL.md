---
name: inscribe
description: Creates a new reusable skill — can be triggered automatically by the pattern detector at 5 repetitions
keep-coding-instructions: true
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
name: <name>
description: <one sentence describing what this skill does>
keep-coding-instructions: true
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

- [ ] Has `keep-coding-instructions: true` in frontmatter
- [ ] Has a clear completion signal
- [ ] Process steps are concrete and actionable (not vague)
- [ ] Does not duplicate an existing skill
- [ ] Name is memorable and matches the behavior

## Completion Signal

"Inscribe complete. New skill /<name> ready. Invoke it with /<name>."

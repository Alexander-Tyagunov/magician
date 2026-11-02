# almanac — file templates

Exact text for the files that steps 4 and 6 of [`../SKILL.md`](../SKILL.md) write. Never overwrite a file that exists.

## Step 4: initial workspace files

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

## Step 6: REVIEW.md

If `REVIEW.md` does not exist, create it from the template part of [`skills/divine/references/review-md-template.md`](../../divine/references/review-md-template.md) (everything below its marker line). Fill `<repository name>` and, from the detected stack, the obvious skip paths (lock files, generated folders, vendored code). Leave the other placeholders for the code owners and say so. `/divine` and `/scrutinize` read it before every review ([`lore/review.md`](../../../lore/review.md)). If the file exists, leave it as it is.

## Step 6: pre-commit skills

**`.claude/skills/verify/SKILL.md`**: write the delegator below, exactly. It must stay model-invocable (no `disable-model-invocation`), or the pre-commit run does not happen.

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

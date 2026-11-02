# almanac — AskUserQuestion configurations

Exact `AskUserQuestion` tool configurations for the run-once setup flow. Do not write any text before calling each one. Wait for each reply before proceeding.

## Workspace Mode (step 1)

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

## Review setup (step 6)

```json
{
  "questions": [
    {
      "question": "Scaffold the review contract and the pre-commit skills? REVIEW.md tells /divine and /scrutinize what failure means here; the verify and simplify skills run before each commit.",
      "header": "Review",
      "multiSelect": false,
      "options": [
        {
          "label": "REVIEW.md + verify + simplify (Recommended)",
          "description": "Write REVIEW.md from magician's template, and two 10-line project skills: verify (runs /certify before each commit) and simplify (runs the simplification lens before each commit)."
        },
        {
          "label": "REVIEW.md + verify",
          "description": "Write REVIEW.md and the verify skill only. No simplify pass before commits."
        },
        {
          "label": "REVIEW.md only",
          "description": "Write the review contract only. Nothing runs before commits."
        },
        {
          "label": "Skip",
          "description": "Write none of these. /divine and /scrutinize use magician's default review rules."
        }
      ]
    }
  ]
}
```

A file that exists is never overwritten. In Shared mode, step 10 commits the written files.

## Permission suggestions (step 7)

```json
{
  "questions": [
    {
      "question": "Show suggested permission rules for this project? Almanac only lists them; you add the ones you want with /permissions.",
      "header": "Permissions",
      "multiSelect": false,
      "options": [
        {
          "label": "Show suggestions",
          "description": "List narrow allow rules for this stack's own test/lint/build commands, and deny rules that keep secrets such as .env files off-limits. Nothing is written to any settings file."
        },
        {
          "label": "Skip",
          "description": "No suggestions. Claude Code keeps asking for approval as usual, and you can manage rules any time with /permissions."
        }
      ]
    }
  ]
}
```

If **Skip**: continue. Do not ask again this session.

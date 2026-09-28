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

## Permission suggestions (step 6)

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

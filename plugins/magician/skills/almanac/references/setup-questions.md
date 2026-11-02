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

## Instructions file (step 5)

```json
{
  "questions": [
    {
      "question": "Write the project instructions for Claude Code only, or also an AGENTS.md that Codex and other agents read?",
      "header": "Instructions",
      "multiSelect": false,
      "options": [
        {
          "label": "CLAUDE.md only (Recommended)",
          "description": "A lean CLAUDE.md for project rules, if none exists. No AGENTS.md."
        },
        {
          "label": "AGENTS.md + CLAUDE.md import",
          "description": "A short AGENTS.md (commands, package manager, the verify command, the REVIEW.md pointer, where specs and plans live), imported by an @AGENTS.md line in CLAUDE.md so there is one source. An existing AGENTS.md is never overwritten."
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

A file that exists is never overwritten. In Shared mode, step 11 commits the written files.

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

If **Show suggestions**: print a short list in chat, built from the detected stack, and write nothing:
- **Allow** — the project's own test, lint and build commands, each named with its subcommand (for example `Bash(npm test *)`, `Bash(npm run lint *)`, `Bash(pytest *)`, `Bash(go test *)`). Never suggest a whole CLI (`Bash(git *)`, `Bash(npm *)`), an interpreter, or a package launcher.
- **Deny** — files that should stay off-limits to Claude (for example `Read(./.env)`, `Read(./.env.*)`, `Read(./secrets/**)`, plus any credential files you noticed while inspecting the project).

Then tell the user they can add any of these with `/permissions` (or by editing their own settings). Trust is per task type: suggest an allow rule that lets a magician skill run without prompts only for a skill that `/chronicle consolidate` shows with 5 or more clean runs and no blocked run.

Add one more line to the same list: STE-lite, magician's simplified technical English for prose, is off by default. To turn it on, the user runs `magician-ui ste on` or creates a `.magician/ste` file with the content `on`. Write no file for it.

If **Skip**: continue. Do not ask again this session.

## Optional extras (step 9)

```json
{
  "questions": [
    {
      "question": "Add any optional extras? Each one is small, and almanac installs nothing.",
      "header": "Extras",
      "multiSelect": true,
      "options": [
        {
          "label": "North star",
          "description": "A one-paragraph .workspace/shared/north-star.md: what the project is for and the outcome that shows it works. /manifest and /conjure read it."
        },
        {
          "label": "Production-gate hook template",
          "description": "A hook template at .workspace/shared/hooks/production-gate.sh that blocks a production deploy unless RELEASE_APPROVAL is set, plus a settings snippet you can paste. Not installed."
        },
        {
          "label": "Cost attribution hints",
          "description": "How to tag OpenTelemetry cost metrics per team and project, and how to read magician's own token cost. Printed in chat only."
        }
      ]
    }
  ]
}
```

No selection: continue.

> On Codex: `magician-ui` and the status line are Claude Code only and do not ship here; turn STE-lite on with a `.magician/ste` file that holds `on`, or `MAGICIAN_STE=1`.

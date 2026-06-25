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

## Permissions (step 6)

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

If **Choose**: present each group with its own `AskUserQuestion` call (core, workspace, stack tools) — one at a time, wait for each reply.

If **Skip**: continue. Do not ask again this session.

## Playwright access (step 6, only if "Add all")

First ask which Playwright tools to grant:

```json
{
  "questions": [
    {
      "question": "Which Playwright tools should Claude have access to?",
      "header": "Playwright",
      "multiSelect": false,
      "options": [
        {
          "label": "Grant all playwright",
          "description": "mcp__playwright__* — allows all current and future Playwright tools automatically without listing each one."
        },
        {
          "label": "Grant suggested (Recommended)",
          "description": "The 5 tools used by this plugin: navigate, take_screenshot, wait_for, snapshot, close."
        },
        {
          "label": "Grant specific",
          "description": "Choose which Playwright tool groups to allow — I'll ask you to pick from grouped categories with descriptions."
        }
      ]
    }
  ]
}
```

If **Grant specific**: follow up with:

```json
{
  "questions": [
    {
      "question": "Which Playwright tool groups do you want to allow?",
      "header": "Playwright",
      "multiSelect": true,
      "options": [
        {
          "label": "Navigation",
          "description": "browser_navigate, browser_navigate_back, browser_wait_for, browser_tabs — browse to URLs, go back, wait for conditions, manage browser tabs"
        },
        {
          "label": "Screenshots",
          "description": "browser_take_screenshot, browser_snapshot — capture visual state and accessibility tree of pages"
        },
        {
          "label": "Interaction",
          "description": "browser_click, browser_type, browser_fill_form, browser_press_key, browser_hover, browser_drag, browser_select_option — simulate user input and mouse actions"
        },
        {
          "label": "Inspection",
          "description": "browser_evaluate, browser_run_code, browser_console_messages, browser_network_requests, browser_file_upload, browser_resize, browser_handle_dialog, browser_close — execute JS, inspect network traffic, handle dialogs, control browser state"
        }
      ]
    }
  ]
}
```

Determine `playwright_rules` from the answer:
- **Grant all playwright** → `["mcp__playwright__*"]`
- **Grant suggested** → `["mcp__playwright__browser_navigate", "mcp__playwright__browser_take_screenshot", "mcp__playwright__browser_wait_for", "mcp__playwright__browser_snapshot", "mcp__playwright__browser_close"]`
- **Grant specific** → combine rules for each selected group:
  - Navigation: `["mcp__playwright__browser_navigate", "mcp__playwright__browser_navigate_back", "mcp__playwright__browser_wait_for", "mcp__playwright__browser_tabs"]`
  - Screenshots: `["mcp__playwright__browser_take_screenshot", "mcp__playwright__browser_snapshot"]`
  - Interaction: `["mcp__playwright__browser_click", "mcp__playwright__browser_type", "mcp__playwright__browser_fill_form", "mcp__playwright__browser_press_key", "mcp__playwright__browser_hover", "mcp__playwright__browser_drag", "mcp__playwright__browser_select_option"]`
  - Inspection: `["mcp__playwright__browser_evaluate", "mcp__playwright__browser_run_code", "mcp__playwright__browser_console_messages", "mcp__playwright__browser_network_requests", "mcp__playwright__browser_file_upload", "mcp__playwright__browser_resize", "mcp__playwright__browser_handle_dialog", "mcp__playwright__browser_close"]`

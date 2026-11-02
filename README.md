# Magician for Codex and ChatGPT

Generated from the magician 5.0.0 source tree by `scripts/build-codex.sh`. Do not edit it here.

- 24 skills under `skills/`, and 7 review-lens skills (`*-lens`) made from the Claude Code agents.
- `lore/` holds the shared guidance the skills link to. `tools/` holds the command-line helpers (`kg`, `jira`,
  `confluence`, `ctx`, `plan-render`, ...). They need Python 3 and a shell.
- No hooks, monitors, output styles or plugin options, so no destructive guard: on Codex, rely on its
  sandbox and approval policy. Each skill ends with an "On Codex" section that maps the Claude Code
  features it names.
- Left out because they only work in Claude Code: the `statusline` skill and its `magician-statusline`
  and `magician-ui` tools (they drive Claude Code's status line and session-start settings). For
  STE-lite, create a `.magician/ste` file that holds `on`, or set `MAGICIAN_STE=1`.

## Jira and Confluence

Codex has no plugin options, so the `jira` and `confluence` helpers read their settings from the
environment Codex starts from:

| Variable | Value |
|---|---|
| `MAGICIAN_JIRA_BASE_URL` | `https://<site>.atlassian.net`, or your Jira Server/Data Center URL |
| `MAGICIAN_JIRA_EMAIL` | Jira Cloud only |
| `MAGICIAN_JIRA_API_TOKEN` | An API token (Cloud) or a personal access token (Server/Data Center) |
| `MAGICIAN_CONFLUENCE_BASE_URL` | `https://<site>.atlassian.net/wiki`, or your Confluence URL |
| `MAGICIAN_CONFLUENCE_EMAIL` | Confluence Cloud only |
| `MAGICIAN_CONFLUENCE_API_TOKEN` | An API token or a personal access token |

Keep tokens out of shell history and out of the repository.

## Install locally

```text
codex plugin marketplace add <folder that holds .agents/plugins/marketplace.json>
codex plugin add magician@magician
```

Start with `$almanac` in a project.

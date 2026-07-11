# Jira setup (first run)

Runs when `JIRA_BASE_URL` or a token is missing. Goal: get the user's base URL + a token into `~/.claude/settings.json` `env`, then verify — **without you ever handling the secret**.

<HARD-GATE>
Never type, echo, generate, or write the token value. API tokens / PATs are secrets. You may write the **non-secret** base URL and email; the **user pastes the token themselves** into their settings file. You only provide the exact snippet and then verify connectivity.
</HARD-GATE>

## Steps

1. **Confirm intent** (AskUserQuestion): "Set up Jira access now? It's a one-time step — create a token and save it to your Claude settings." Options: *Set it up* / *Not now* (skip this time) / *No, I don't use Jira — don't ask again*. On the last option, record the opt-out per [lore/integration-prefs.md](../../lore/integration-prefs.md) (`"jira":"disabled"`) and confirm you won't bring it up again unless they ask. Don't continue setup.

2. **Collect non-secret config** (AskUserQuestion or a direct question):
   - **Base URL** — `https://<site>.atlassian.net` (Cloud) or `https://jira.<company>.com` (Server/Data Center).
   - **Deployment** — Cloud or Server/DC. (Cloud → Basic auth with email + API token; Server/DC → Bearer PAT.)
   - For Cloud, the **account email**.

3. **Guide token creation** (the user does this in their browser):
   - **Cloud API token** — id.atlassian.com → *Security* → *Create and manage API tokens* → create one, copy it.
   - **Server/DC PAT** — Jira → profile avatar → *Personal Access Tokens* → *Create token* (read/write scope), copy it.
   Link the user to their instance's docs with WebFetch only if they ask; do not fetch their private instance.

4. **Show the settings snippet to paste.** Tell the user to open `~/.claude/settings.json` and add to the `env` block (create the file/block if absent). Provide it with a **placeholder** they replace:
   ```jsonc
   {
     "env": {
       "JIRA_BASE_URL": "<their base URL>",
       // Cloud only:
       "JIRA_EMAIL": "<their email>",
       // paste the token in place of the placeholder — do not share it with the assistant:
       "JIRA_API_TOKEN": "<PASTE_YOUR_TOKEN_HERE>"
     }
   }
   ```
   You MAY offer to write the **non-secret** keys (`JIRA_BASE_URL`, `JIRA_EMAIL`) for them; leave `JIRA_API_TOKEN` for the user to paste. If the user already has a token env var from a prior setup (e.g. `JIRA_PAT`/`JIRA_PROD_PAT`), the skill reads those too — no new variable needed, just set `JIRA_BASE_URL`.

5. **Reload.** `env` from settings is applied to new sessions — tell the user to start a new session (or restart Claude Code) so the variables load. (Within this session, they can `export` the vars in the shell for an immediate test.)

6. **Verify**: run **`jira myself`** (the `jira` CLI is on PATH when the plugin is enabled). It prints your name on success; `401` → token wrong/rotated, connection failure → base URL wrong or VPN.

7. **(Optional) allow it everywhere**: the `jira` skill already pre-allows the `jira` CLI via its `allowed-tools`, so there are no prompts while the skill runs. If you also want it allowed when other skills call it (e.g. `/magic`), add `"Bash(jira:*)"` to `permissions.allow` in `~/.claude/settings.json` once.

Once verified, continue with the user's original request.

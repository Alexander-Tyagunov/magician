# Confluence setup (first run)

Runs when `CONFLUENCE_BASE_URL` or a token is missing. Get the user's base URL + a token into `~/.claude/settings.json` `env`, then verify — **without you ever handling the secret**.

<HARD-GATE>
Never type, echo, generate, or write the token value. You may write the **non-secret** base URL and email; the **user pastes the token themselves**. You only provide the snippet and verify.
</HARD-GATE>

## Steps

1. **Confirm intent** (AskUserQuestion): "Set up Confluence access now? One-time — create a token and save it to your Claude settings." Options: *Set it up* / *Not now* (skip this time) / *No, I don't use Confluence — don't ask again*. On the last option, record the opt-out per [lore/integration-prefs.md](../../lore/integration-prefs.md) (`"confluence":"disabled"`) and confirm you won't bring it up again unless they ask. Don't continue setup.

2. **Collect non-secret config**:
   - **Base URL** — Cloud: `https://<site>.atlassian.net/wiki` (include `/wiki`). Server/DC: `https://confluence.<company>.com` (plus any context path).
   - **Deployment** — Cloud (Basic, email + API token) or Server/DC (Bearer PAT).
   - For Cloud, the **account email**.
   - Confluence Cloud uses the **same Atlassian API token** as Jira — if Jira is already set up on the same site, reuse it.

3. **Guide token creation** (user, in browser):
   - **Cloud** — id.atlassian.com → *Security* → *API tokens* → create, copy. (Same token works for Jira + Confluence on that site.)
   - **Server/DC** — Confluence → profile → *Personal Access Tokens* → create (read/write), copy.

4. **Show the settings snippet to paste** into `~/.claude/settings.json` `env` (placeholder for the secret):
   ```jsonc
   {
     "env": {
       "CONFLUENCE_BASE_URL": "<their base URL>",
       // Cloud only:
       "CONFLUENCE_EMAIL": "<their email>",
       "CONFLUENCE_API_TOKEN": "<PASTE_YOUR_TOKEN_HERE>"
     }
   }
   ```
   You MAY write the non-secret keys for them; leave the token for the user. If they already have `CONFLUENCE_PAT`/`CONFLUENCE_PROD_PAT`, the skill reads those — just set `CONFLUENCE_BASE_URL`.

5. **Reload** — `env` applies to new sessions; have the user start a new session (or `export` for an immediate test).

6. **Verify**: run **`confluence whoami`** (the `confluence` CLI is on PATH when the plugin is enabled). Prints your name on success; `401` → token, connection failure → base URL / VPN.

7. **(Optional) allow it everywhere**: the skill already pre-allows the `confluence` CLI via `allowed-tools`. To allow it when other skills call it too, add `"Bash(confluence:*)"` to `permissions.allow` in `~/.claude/settings.json` once.

Once verified, continue with the user's original request.

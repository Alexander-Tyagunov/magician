# Confluence setup (first run)

Runs when `CONFLUENCE_BASE_URL` or a token is missing. Get the user's base URL + a token into `~/.claude/settings.json` `env`, then verify — **without you ever handling the secret**.

<HARD-GATE>
Never type, echo, generate, or write the token value. You may write the **non-secret** base URL and email; the **user pastes the token themselves**. You only provide the snippet and verify.
</HARD-GATE>

## Steps

1. **Confirm intent** (AskUserQuestion): "Set up Confluence access now? One-time — create a token and save it to your Claude settings." Options: *Set it up* / *Not now*.

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

6. **Verify** (no secret printed):
   ```bash
   BASE="${CONFLUENCE_BASE_URL%/}"; TOKEN="${CONFLUENCE_API_TOKEN:-${CONFLUENCE_PAT:-${CONFLUENCE_PROD_PAT:-}}}"
   if [ -n "${CONFLUENCE_EMAIL:-}" ]; then A=(-u "$CONFLUENCE_EMAIL:$TOKEN"); else A=(-H "Authorization: Bearer $TOKEN"); fi
   curl -sS --max-time 15 -o /dev/null -w "%{http_code}\n" "${A[@]}" "$BASE/rest/api/space?limit=1"
   ```
   `200` → success. `401/403` → token wrong/rotated or insufficient scope. Connection failure → base URL wrong or network/VPN.

Once verified, continue with the user's original request.

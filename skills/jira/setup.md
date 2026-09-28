# Jira setup (first run)

Runs when `jira myself` says Jira isn't configured or its settings aren't loaded. Jira settings live in
magician's **plugin configuration**. Claude Code shows the form, keeps the API token in the system's
secure credential store (never in `settings.json`), and magician loads the values into each new session.
**You never see, type, or handle the token.**

<HARD-GATE>
Never ask for, type, echo, generate, store, or write a token value in chat, files, commands, or settings.
Never tell the user to put a token in `settings.json`, an environment variable, or a shell command
(`claude plugin install --config …` would leave it in shell history). The token is entered in exactly one
place: the `/plugin configure magician` form. If the user pastes a token into the conversation anyway,
don't repeat it; tell them to revoke it and create a new one. Don't open or read `~/.claude/settings.json`:
it may still hold a token from the old setup.
</HARD-GATE>

## Steps

1. **Confirm intent** (AskUserQuestion): "Set up Jira access now? It's a one-time step: create a token,
   then save it in magician's plugin settings." Options: *Set it up* / *Not now* (skip this time) /
   *No, I don't use Jira — don't ask again*. On the last option, record the opt-out per
   [lore/integration-prefs.md](../../lore/integration-prefs.md) (`"jira":"disabled"`) and confirm you won't
   bring it up again unless they ask. Don't continue setup.

2. **Tell the user what the form asks for.** They type the values into the form, not into chat:
   - **Jira base URL**: `https://<site>.atlassian.net` (Cloud) or their Jira Server/Data Center URL. It must
     start with `https://`.
   - **Jira account email**: Cloud only (Basic auth, REST v3). Leave it **empty** for Server/Data Center
     (Bearer token, REST v2); an email there causes `401`.
   - **Jira API token / PAT**.

3. **Guide token creation** (the user does this in their browser):
   - **Cloud API token**: id.atlassian.com → *Security* → *Create and manage API tokens* → create one, copy it.
   - **Server/DC PAT**: Jira → profile avatar → *Personal Access Tokens* → *Create token* (read/write scope) → copy it.
   Link the user to their instance's docs with WebFetch only if they ask. Don't fetch their private instance.

4. **Have the user open the form.** Ask them to run **`/plugin configure magician`** (a slash command they
   type; you can't run it for them). If another installed plugin is also named `magician`, use
   `/plugin configure magician@magician`. They fill in the three Jira fields; the Confluence fields are
   optional and can stay empty. Later, the base URL and email can also be edited from `/config`. The token
   can only be changed through `/plugin configure magician`.

5. **Start a new session.** Magician loads the settings when a session starts, so the current session can't
   see values saved in it. Ask the user to start a new session (or restart Claude Code) and ask you again there.

6. **Verify** in the new session: run **`jira myself`**. It prints the user's name on success.

   | Output | Meaning → action |
   |---|---|
   | "settings aren't loaded in this session" | Saved after this session started → start a new session. If it persists, check that `/plugin` shows magician enabled and `/hooks` lists its SessionStart hooks. |
   | "no Jira base URL / API token configured" | A field is empty → re-open `/plugin configure magician`. |
   | "must start with https://" | The base URL uses `http://` → re-enter it as `https://…`. |
   | `401` | Token wrong, expired, or rotated; on Server/DC, make sure the email field is empty. |
   | `403` | The account lacks permission for that project or action. |
   | redirect (`3xx`) | The base URL points at a page that redirects (often a missing path or `http`) → use the final `https://` URL. |
   | connection failure / timeout | Base URL wrong, or VPN/network. Don't retry blindly. |

7. **Moving from the old setup.** Earlier versions kept Jira settings in the `env` block of
   `~/.claude/settings.json`. Magician no longer reads them. Once `jira myself` works, suggest the user delete
   the Jira entries they added there. They should **edit the file themselves**: you mustn't open it, because
   it contains the token.

8. **(Optional) fewer prompts outside this skill.** The `jira` skill pre-approves the CLI's read commands
   through its `allowed-tools`; creates, links, and other writes always ask. If the user also wants Jira reads
   auto-approved when other skills call the CLI, they can add read-only rules themselves with `/permissions`
   (for example `Bash(jira get *)` and `Bash(jira search *)`). Don't suggest a blanket `Bash(jira *)` rule:
   it would auto-approve writes too.

Once verified, continue with the user's original request.

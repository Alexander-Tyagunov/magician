# Confluence setup (first run)

Runs when `confluence whoami` says Confluence isn't configured or its settings aren't loaded. Confluence
settings live in magician's **plugin configuration**. Claude Code shows the form, keeps the API token in the
system's secure credential store (never in `settings.json`), and magician loads the values into each new
session. **You never see, type, or handle the token.**

<HARD-GATE>
Never ask for, type, echo, generate, store, or write a token value in chat, files, commands, or settings.
Never tell the user to put a token in `settings.json`, an environment variable, or a shell command
(`claude plugin install --config …` would leave it in shell history). The token is entered in exactly one
place: the `/plugin configure magician` form. If the user pastes a token into the conversation anyway,
don't repeat it; tell them to revoke it and create a new one. Don't open or read `~/.claude/settings.json`:
it may still hold a token from the old setup.
</HARD-GATE>

## Steps

1. **Confirm intent** (AskUserQuestion): "Set up Confluence access now? It's a one-time step: create a
   token, then save it in magician's plugin settings." Options: *Set it up* / *Not now* (skip this time) /
   *No, I don't use Confluence — don't ask again*. On the last option, record the opt-out per
   [lore/integration-prefs.md](../../lore/integration-prefs.md) (`"confluence":"disabled"`) and confirm you
   won't bring it up again unless they ask. Don't continue setup.

2. **Tell the user what the form asks for.** They type the values into the form, not into chat:
   - **Confluence base URL**: Cloud is `https://<site>.atlassian.net/wiki` (include `/wiki`). Server/DC is the
     Confluence URL plus any context path. It must start with `https://`.
   - **Confluence account email**: Cloud only (Basic). Leave it **empty** for Server/Data Center (Bearer).
   - **Confluence API token / PAT**. On Cloud, the **same Atlassian API token** works for Jira and Confluence
     on one site, so enter it here too.
   - If Jira is already configured for Cloud on the same site, you may leave the Confluence email and token
     empty; the CLI reuses the Jira ones only when both base URLs have the same scheme and host.

3. **Guide token creation** (the user does this in their browser):
   - **Cloud**: id.atlassian.com → *Security* → *API tokens* → create, then copy. The same token covers both
     products on that site.
   - **Server/DC**: Confluence → profile → *Personal Access Tokens* → create (read/write), then copy.
   Link the user to their instance's docs with WebFetch only if they ask. Don't fetch their private instance.

4. **Have the user open the form.** Ask them to run **`/plugin configure magician`** (a slash command they
   type; you can't run it for them). If another installed plugin is also named `magician`, use
   `/plugin configure magician@magician`. They fill in the Confluence fields; the Jira fields are optional
   and can stay empty. Later, the base URL and email can also be edited from `/config`. The token can only
   be changed through `/plugin configure magician`.

5. **Start a new session.** Magician loads the settings when a session starts, so the current session can't
   see values saved in it. Ask the user to start a new session (or restart Claude Code) and ask you again there.

6. **Verify** in the new session: run **`confluence whoami`**. It prints the user's name on success.

   | Output | Meaning → action |
   |---|---|
   | "settings aren't loaded in this session" | Saved after this session started → start a new session. If it persists, check that `/plugin` shows magician enabled and `/hooks` lists its SessionStart hooks. |
   | "no Confluence base URL / API token configured" | A field is empty → re-open `/plugin configure magician`. |
   | "must start with https://" | The base URL uses `http://` → re-enter it as `https://…`. |
   | `401` | Token wrong, expired, or rotated; on Server/DC, make sure the email field is empty. |
   | `403` | No permission on that space/page. |
   | redirect (`3xx`) | The base URL points at a page that redirects (often a missing `/wiki` or `http`) → use the final `https://` URL. |
   | connection failure / timeout | Base URL wrong, or VPN/network. Don't retry blindly. |

7. **Moving from the old setup.** Earlier versions kept Confluence settings in the `env` block of
   `~/.claude/settings.json`. Magician no longer reads them. Once `confluence whoami` works, suggest the user
   delete the Confluence entries they added there. They should **edit the file themselves**: you mustn't open
   it, because it contains the token.

8. **(Optional) fewer prompts outside this skill.** The `confluence` skill pre-approves the CLI's read
   commands through its `allowed-tools`; creates, updates, and other writes always ask. If the user also wants
   Confluence reads auto-approved when other skills call the CLI, they can add read-only rules themselves with
   `/permissions` (for example `Bash(confluence get *)` and `Bash(confluence search *)`). Don't suggest a
   blanket `Bash(confluence *)` rule: it would auto-approve writes too.

Once verified, continue with the user's original request.

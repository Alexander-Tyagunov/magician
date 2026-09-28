# Privacy policy

Effective date: 2026-09-27.

This policy covers magician, the Claude Code plugin in this repository, from version 4.15.0 onwards. It explains what magician reads and stores on your computer, what it sends and to whom, and how to remove it.

## Summary

magician is open-source software that runs on your own computer. The author runs no servers and receives no data from you. There is no telemetry, analytics, crash reporting, usage statistics or account.

## What magician reads

- Project files that show which languages, frameworks and databases you use, such as package manifests and lock files. Stack detection never reads dotenv files.
- git metadata for the current project: branch, recent commits and the names of changed files.
- The records it saved in earlier sessions, listed below.
- When you run `/chronicle status` or ask for a context report, the `ctx` command reads the current session's transcript file for its token counts and model name only, and stores nothing from it.
- When `/sentinel` runs its local scan, the `magician-scan` command reads every file in the folder, dotenv files included. For each match it prints the file, the line and a short snippet into the conversation. For credential and private-key matches the snippet shows only the key name, never the value.

magician does not store the text of your prompts, Claude's replies or your conversation transcripts.

## What magician stores on your computer

The plugin data folder is the folder Claude Code gives each plugin, usually `~/.claude/plugins/data/magician-<marketplace>/`, where the last part is the name of the marketplace you installed from. If Claude Code does not provide that folder, magician uses `~/.local/share/magician/` instead.

| Location | What is stored | How long it is kept |
|---|---|---|
| Plugin data folder | One record per session: time, folder, branch, commit count, names of changed files and a one-line summary taken from git | The newest 50 records |
| Same folder | Session start times | 30 days |
| Same folder | Per-project learnings (facts recorded with the `ctx` command and commit subjects that describe a decision), the log platform you use, and references you asked it to remember | Until you delete them or uninstall |
| Same folder | Jira and Confluence memory: the names of people, projects, boards, epics, spaces, pages and repositories you work with, which the `/jira` and `/confluence` skills record without asking and announce with "Remembered" | Until you edit or delete `jira-memory.md` and `confluence-memory.md`, or uninstall |
| Same folder | Your integration opt-outs, the workspace mode you chose in `/almanac`, and the pull requests `/divine` has reviewed with the commit it reviewed | Until you uninstall |
| Same folder | A short-lived cache of Jira and Confluence responses, reused for 30 seconds and replaced by later requests, and the time of the last request, used for pacing | Until you uninstall |
| Same folder | Small marker files, such as a note that a one-time or weekly message was shown | Until you uninstall |
| `~/.claude/magician/` | Your magician preferences (status line, voice and lore settings), a copy of the status line renderer, and the local code index for repositories you index, including a local socket file while the optional index helper runs | Until you delete them |
| `~/.claude/magician/status/` | Per-session status line markers such as the active skill name, written only while the status line is on | 7 days |
| `~/.claude/settings.json.bak-magician-ui-*` | Backups of your Claude Code settings, taken before `magician-ui` changes them, readable only by you | The newest 3 |
| `.workspace/` in your projects | Specs, plans, research notes, decision records, post-mortems, `/conjure` designs and mockups, `/divine` review diffs and `/transmute` session state | Until you delete them |
| `.workspace/local/` in your projects | The `/conjure` design preview's log of your clicks and chat messages, and its server files | Until you delete them |
| `.magician/` in your projects | Optional voice and lore files you create yourself | Until you delete them |

The session record is not kept when you turn off the `session_history` option. Claude Code deletes the plugin data folder when you uninstall the plugin.

## What is sent, and to whom

magician sends data only to services you already use, and only when you use a feature that needs them:

- Your Jira and Confluence sites, at the URLs you configure, over HTTPS. Requests carry your token and whatever you asked Claude to read or change.
- GitHub or GitLab, through your own `gh` or `glab` login, when you use `/seal`, `/deploy`, `/divine`, `/autopsy` or `/jira`, or when the CI monitor runs after `/deploy`. `/seal` also pushes to your git remote.
- Vulnerability databases, when `/sentinel` runs a dependency audit: `npm audit` sends the dependency list to the npm registry; `pip-audit` sends package names and versions to PyPI (or OSV, if you choose it); `safety check` downloads Safety's vulnerability database and, when you use a Safety API key, sends the package list to Safety's servers; `govulncheck` asks the Go vulnerability database at vuln.go.dev about the modules you use, and the go command downloads any module missing from its cache from your module proxy (proxy.golang.org by default); and `cargo audit` downloads the RustSec advisory database from GitHub and, to spot yanked versions, fetches the crates.io index entry of each crate in Cargo.lock.
- Web search and web pages, through Claude Code's own web tools, which follow your permission settings. If you added the Context7 documentation MCP server, `/magic`, `/divine` and `/transmute` may query it without a permission prompt.
- Websites you name, when `/transmute` uses the Claude in Chrome tools to open them in your browser. Each browser action goes through your normal permission prompt. Page text and captured network requests enter the conversation; the skill is told to mask secrets and stay read-only, and it asks in chat before typing into a page.
- Your own design pages, when `/conjure` uses a Playwright MCP server, if you have one, to open and screenshot them.
- jsDelivr, when you open the `/conjure` preview: your browser downloads one pinned diagram library from it, checked against an integrity hash, so jsDelivr sees your IP address and browser details as any website would. A hosted web font service is used only if you ask for such a font.
- Claude Artifacts, when `/magic`, `/conjure`, `/autopsy`, `/accelerate`, `/scrutinize` or `/divine` offers to publish a result and you accept.

Each of these services handles your data under its own privacy policy. Nothing is sent to the author.

Text that magician adds to your session, such as lore, project notes and scan results, becomes part of your conversation. Claude Code sends your conversation to your model provider under Claude Code's and that provider's terms.

## Credentials

You enter Jira and Confluence settings in the plugin's options (`/plugin configure magician`). Claude Code stores the tokens in your system keychain, or in its credentials file where no keychain is available, and stores the other values in its settings.

At the start of each session, a magician hook copies the non-empty Jira and Confluence values, tokens included, into the session environment file that Claude Code provides. The `jira` and `confluence` commands read them from there. The hook also writes, in every session, the path of magician's data folder and a variable showing that it ran; these hold no personal data. When the hook creates that file it is readable only by your user account, the hook never prints the values, and Claude Code manages the file's lifetime.

While a session runs, any command Claude runs in it can read those values from its environment. Tokens are sent only to the site you configured, over HTTPS; the commands refuse plain HTTP URLs unless the site runs on your own computer, pass the token to curl without putting it on the command line, and don't follow redirects. magician never writes tokens to your repositories or to settings files.

## How to delete everything

Steps 1 and 2 use magician's own commands, so ask Claude to run them while the plugin is still enabled, and in this order.

1. Run `magician-ui cleanup`. This removes the permission rules and auto-mode setting that versions 4.14 and earlier recorded adding to your settings.
2. Run `magician-ui disable --purge`. This removes magician's status line entry from your settings, the renderer copy, the status markers and your preferences. It refuses while cleanup still has recorded entries to remove, because cleanup needs magician's record of what it added; `--purge --force` purges anyway and leaves those entries.
3. Uninstall the plugin with `/plugin uninstall magician@magician`. Claude Code deletes the plugin data folder.
4. Delete `~/.claude/magician/` to remove the code index and anything left there, and `~/.local/share/magician/` if it exists.
5. Delete the `~/.claude/settings.json.bak-magician-ui-*` backups if you don't want them.
6. In each project, delete `.workspace/` and `.magician/` if you no longer want them. Files you committed from `.workspace/shared/` stay in your git history.
7. Clear the Jira and Confluence options, and revoke the tokens on your sites if you no longer use them.

## Changes to this policy

Changes are recorded in the changelog and the repository history, and the effective date above is updated.

## Contact

Email tyagunov.alex@gmail.com with privacy questions. For questions that are not sensitive, you can also [open an issue on GitHub](https://github.com/Alexander-Tyagunov/magician/issues).

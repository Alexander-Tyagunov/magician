![magician: plan, build, verify, and ship software with Claude Code](assets/banner.svg)

magician is a Claude Code plugin for the software lifecycle: research, design, planning, test-first building, verification, review and release. It adds 25 skills, 7 agents and a few command-line helpers. A skill is a set of instructions Claude follows for one kind of task, and you start one with its slash command.

magician asks for your approval before it first pushes a change, opens or merges a pull request, or deploys; when CI then fails, `/seal` pushes its fixes under that same approval. Local commits happen as steps of work you have already approved, such as an agreed plan or the `/almanac` setup.

When a session starts, magician looks at the project and adds short guidance, called [lore](#lore), for the languages, frameworks and databases it finds. Everything it runs, stores and sends is listed in [What runs on your machine](#what-runs-on-your-machine).

## Install

### Requirements

- Claude Code with plugin support, in the terminal, the desktop app or an IDE. magician ships command-line tools in a `bin/` folder, so Claude chat and Cowork can't install it.
- bash 3.2 or later for the hooks. On Windows, run Claude Code with Git Bash installed or inside WSL.
- Python 3 for the bundled commands and the status line. The hooks don't use it.
- git. The GitHub CLI (`gh`), or `glab` for GitLab, is optional.
- Node.js, optional, for the `/conjure` design preview in your browser. Without it, the design conversation stays in chat.

### Add the plugin

```text
/plugin marketplace add Alexander-Tyagunov/magician
/plugin install magician@magician
```

Claude Code may ask for the plugin's options during install. All of them are optional and are described in [Options](#options). Restart Claude Code if it asks.

The first time you open a code project, magician shows a one-line hint suggesting `/almanac`. To check that it loaded, type `/` and look for its skills, or run `/hooks` to see its hooks.

Using Codex? The Codex package lives on the [codex-plugin branch](https://github.com/Alexander-Tyagunov/magician/tree/codex-plugin). Add it with `codex plugin marketplace add Alexander-Tyagunov/magician --sparse .agents/plugins`, then `codex plugin add magician@magician`.

### Updates

Claude Code updates marketplace plugins on its own. To update right away, run:

```text
/plugin marketplace update
/plugin update magician@magician
```

Start a new session afterwards so the hooks reload. In Codex, run `codex plugin marketplace upgrade magician`, then `codex plugin add magician@magician`.

## Quick start

In a project, set up the workspace once, then describe a feature:

```text
/almanac
/manifest add CSV export to the reports page
```

`/almanac` asks whether to share the workspace with your team or keep it private. It then creates `.workspace/`, a folder where skills save specs and plans, updates `.gitignore`, writes a short `CLAUDE.md` and, in Shared mode, commits those files. Permission rules and MCP servers are only suggested in chat; your Claude Code settings are not changed.

`/manifest` runs design, planning, building, verification, review and release in order. It stops for your approval after scoping, after the spec, after the plan and before the pull request, and asks whether to build on the current branch or in a new worktree. To run the stages one at a time, use the skills in [How it works](#how-it-works).

## Examples

### Review a branch

```text
/divine review my current branch against main
```

Claude returns findings ranked by severity, each with its impact and a suggested fix. It posts pull request comments only if you ask.

### Port a feature

```text
/transmute port the saved-searches feature in ../admin-app into apps/customer
```

magician first reads the existing feature and writes down how it behaves, then plans the port against that description. You approve the plan before any code changes.

### Debug a failure

```text
/unravel the checkout total test fails on CI but passes locally
```

Claude lists hypotheses and gathers evidence for each before it changes any code. It then fixes the confirmed cause and adds a regression test.

### Work with Jira

```text
/jira what's assigned to me in the current sprint?
```

The bundled `jira` command reads your issues from the site you set up in [Jira and Confluence](#jira-and-confluence), and Claude summarizes them. Creating, commenting on or moving an issue always shows the full change first and waits for your yes.

## How it works

Each stage has its own skill, and `/manifest` runs them in order. Claude can also pick a skill when your request matches its description, except `/manifest`, `/transmute`, `/deploy`, `/autopsy`, `/almanac` and `/inscribe`, which run only when you type them.

| Stage | Skill | What you get |
|---|---|---|
| Research | `/magic` | Findings in `.workspace/shared/research/` |
| Design | `/conjure` | An approved spec in `.workspace/shared/specs/` |
| Plan | `/blueprint` | A test-first plan in `.workspace/shared/plans/` |
| Build | `/orchestrate`, `/ward` | Code and tests, one behaviour at a time |
| Verify | `/certify` | Test, type, lint and build results |
| Review | `/scrutinize`, `/divine` | Findings ranked by severity |
| Ship | `/seal` | A pull request watched through CI |

### What skills run without asking

magician adds no permission rules and doesn't change your permission mode. Each skill lists the tools it needs in the `allowed-tools` line of its `SKILL.md`, and while that skill is active Claude Code lets it use them without a prompt. Anything else follows your own permission settings. These grants go beyond reading files:

| Skill | Runs without asking |
|---|---|
| `/certify` | Your project's test, lint and build commands as `/certify` writes them, such as `npm run build`, `go test ./...` and `mvn test`. `npm test`, `pytest`, `mypy` and `cargo test` accept any arguments, including ones that update test snapshots, install type stubs, load a plugin or run another program. Test commands run the project's own code |
| `/seal` | `git add -A`, `git commit -m` with any further arguments, `git push -u origin HEAD` exactly (it names the branch, so your git push settings can't widen it to a force, delete or other branch), `gh pr create` and `gh pr merge --squash --delete-branch`, plus edits to `CLAUDE.md` and `README.md`. It shows one summary and asks before the first push, pull request or merge |
| `/almanac` | `git add .workspace/shared/ CLAUDE.md .gitignore` exactly, the files it sets up. `/autopsy`, `/conjure`, `/inscribe` and `/magic` ask before staging the file they wrote |
| `/almanac`, `/autopsy`, `/conjure`, `/inscribe`, `/magic` | `git commit -m` with any message and any further arguments, such as `-a`, `--amend` or `--no-verify` |
| `/portal` | `git worktree add` with any arguments |
| `/sentinel` | Dependency auditors in report mode only: `npm audit`, `pip-audit`, `safety check`, `govulncheck ./...` and `cargo audit` |
| `/deploy` | Edits to CI configuration in `.github/workflows/`, `.gitlab-ci.yml` and `.circleci/` |
| `/conjure` | Starting and stopping its local preview server. Opening the preview in your browser asks first |

`/knowledge-graph` and `/weave` also run `kg refresh`, which builds or updates the code index in `~/.claude/magician/knowledge-graph/`, and `kg query` and `kg blast` save their results to a cache in that folder. The remaining grants are read-only commands, such as `kg check` and `kg neighbors`, the read commands of `jira` and `confluence`, and `gh` views; creating and editing files inside `.workspace/`, `.claude/skills/` or magician's data folder; and `/almanac`'s edits to `CLAUDE.md` and `.gitignore`.

## Skills

| Skill | Use it to |
|---|---|
| `/almanac` | Set up a project workspace, once per project |
| `/manifest` | Run the full lifecycle with four approval points |
| `/magic` | Research a question across documentation, the web and local files |
| `/conjure` | Agree on a design and spec before writing code |
| `/blueprint` | Turn an approved spec into a test-first plan |
| `/portal` | Isolate a feature in its own git worktree |
| `/orchestrate` | Build a plan with parallel agents |
| `/weave` | Deliver many related items as one tracked workflow |
| `/ward` | Build one behaviour at a time, test first |
| `/unravel` | Debug from a hypothesis and evidence, then add a regression test |
| `/certify` | Check tests, types, lint and build before calling work done |
| `/scrutinize` | Review a diff with three reviewers and fix what they confirm |
| `/divine` | Review a change or pull request in depth, ranked by severity |
| `/sentinel` | Scan a codebase for security issues without changing it |
| `/accelerate` | Profile and optimize against a measured baseline |
| `/seal` | Commit, open a pull request, watch CI and merge |
| `/deploy` | Create, fix or monitor CI/CD pipelines |
| `/autopsy` | Write a blameless post-incident review |
| `/transmute` | Understand an existing feature, then port it or change it in place |
| `/knowledge-graph` | Build and query the local code index |
| `/chronicle` | Review session history, saved references and project learnings |
| `/statusline` | Turn the status line on or off and set the voice |
| `/jira` | Read, search, create and update Jira issues |
| `/confluence` | Read, search, create and update Confluence pages |
| `/inscribe` | Write a new reusable skill for the current repository |

## Agents

Skills start these agents; you rarely call them yourself. Most are read-only: `fixer` can edit files and run shell commands, and `gatekeeper` can run shell commands.

| Agent | Role |
|---|---|
| `reviewer` | Finds bugs, logic errors and missed edge cases |
| `sentinel` | Finds vulnerabilities and attack surfaces |
| `simplifier` | Finds unnecessary complexity |
| `verifier` | Checks that the tests actually prove the change |
| `guardian` | Audits agent-specific risks such as prompt injection and over-broad tool access |
| `fixer` | Makes the smallest change that resolves a confirmed finding, then reruns the check |
| `gatekeeper` | Runs the release checks and returns go or no-go with evidence |

## Bundled commands

While magician is enabled, these commands are on the PATH of the shell Claude uses, not your own terminal. Skills call them for you. To run one yourself, ask Claude, for example "run magician-ui status".

| Command | What it does | Network |
|---|---|---|
| `kg` | Builds a local SQLite index of your code and answers queries with `file:line` results and change impact. An optional helper that keeps the index loaded starts only when you agree and exits after 15 idle minutes | None |
| `ctx` | Stores project learnings and reports how full the context is, reading only token counts and the model name from this session's transcript file | None |
| `jira` | REST client for your Jira site | Your Jira site only, over HTTPS |
| `confluence` | REST client for your Confluence site | Your Confluence site only, over HTTPS |
| `magician-ui` | Turns the status line, voice and lore on or off, and removes settings earlier versions added | None |
| `magician-statusline` | Draws the status line from the data Claude Code passes to it | None |
| `magician-scan` | Scans a folder for security issues and prints each match with its file, line and a short snippet; credential values are redacted | None |

## Configuration

### Jira and Confluence

1. Run `/plugin configure magician` and fill in the site URL, the token and, for Cloud, your account email. Site URLs must start with `https://`, except for a site on your own computer.
2. Start a new session, because the values load at session start.
3. Check the connection with `/jira` or `/confluence`, or ask Claude to run `jira myself` or `confluence whoami`.

Claude Code keeps the two tokens in your system keychain, or in its credentials file where no keychain is available, and saves the other values in its settings. Leave the options empty if you don't use Jira or Confluence.

At session start, a hook copies the non-empty Jira and Confluence values, tokens included, into the session environment file that Claude Code loads before each shell command. If the hook creates that file, it makes it readable only by you; either way, every command Claude runs in the session can read the tokens from its environment. Use a token with the narrowest access your site allows, or leave the options empty if that exposure is not acceptable.

### Options

| Option | Default | What it does |
|---|---|---|
| `jira_base_url` | empty | Your Jira site, for example `https://your-site.atlassian.net` |
| `jira_email` | empty | Account email for Jira Cloud; leave it empty for Server or Data Center |
| `jira_api_token` | empty | Cloud API token, or a personal access token for Server or Data Center; kept in the keychain |
| `confluence_base_url` | empty | Your Confluence site; Cloud URLs end in `/wiki` |
| `confluence_email` | empty | Account email for Confluence Cloud; leave it empty for Server or Data Center |
| `confluence_api_token` | empty | Cloud API token or Server/Data Center personal access token; kept in the keychain. Leave it empty on the same Cloud site to reuse the Jira token |
| `auto_format` | off | After Claude writes or edits a file, runs ruff (or black), gofmt, rustfmt or shfmt if already installed |
| `auto_format_prettier` | off | Also runs prettier, which loads the project's config and plugins and so can run code from the repository |
| `desktop_notifications` | off | Shows a desktop notification when a background session finishes or needs input |
| `session_history` | on | Keeps a short record of each session: time, folder, branch, commit count, changed file names and a one-line summary |

### Voice

Voice is the output-brevity level, meaning how much prose Claude writes around the facts. `warrior` gives the shortest complete answer, `scribe` (the default) is leaner than usual, and `bard` leaves Claude at its normal length. Code, commands, paths and error text are never shortened.

Set it with `/statusline`, by asking Claude to run `magician-ui voice warrior` (or another name), with a `.magician/voice` file in the project, or with the `MAGICIAN_VOICE` environment variable. The environment variable wins, then the project file, then the saved setting. A change applies from the next session.

### Status line

The status line stays off until you turn it on with `/statusline`. It shows how full the context is, with a warning as it fills and a small chart of recent use, plus the model, git branch and cost, the active skill, the reasoning effort, and the lore and voice state. Turning it on edits one key in your settings, as described in [Settings it can change](#settings-it-can-change).

## What runs on your machine

### Hooks

Hooks are scripts Claude Code runs on session events. They make no network calls and don't read your conversation transcript. All of them, the safety guard included, are plain bash.

| Event | Script | What it does | How to turn it off |
|---|---|---|---|
| Session start | `session-start.sh` | Detects the stack and adds matching lore, the voice note, a note from the last session in this folder, recent learnings, saved references, a code-index hint and the detected log platform | Turn off lore, voice or `session_history`; the hook itself only by disabling the plugin |
| Session start | `userconfig-env.sh` | Copies non-empty Jira and Confluence options into the session environment, with the path of magician's data folder and a marker showing the hook ran | Leave those options empty; the folder path and marker are always written |
| After compaction | `compact-context.sh` | Restates the branch, uncommitted files, this session's commits and shared workspace files; writes nothing | Disable the plugin |
| Each prompt | `pattern-detect.sh` | Adds at most one line naming a matching skill; stores nothing from the prompt | Disable the plugin |
| Before shell commands | `destructive-guard.sh` | Blocks a fixed list of dangerous commands, see [Safety guard](#safety-guard) | Not possible, by design |
| After writes and edits | `format.sh` | Runs an installed formatter on the edited file | Off by default (`auto_format`) |
| Notifications | `notify.sh` | Shows a desktop notification when a background session finishes or needs input, through your terminal | Off by default (`desktop_notifications`) |
| Session stop | `chronicle-stop.sh` | Saves a short session record from git and adds decision-style commit subjects to project learnings | Turn off `session_history` |

At session start magician also shows you two notices of its own: a one-time hint to run `/almanac` in a new project, and, if 4.14 or earlier recorded adding permission rules or auto mode, a weekly reminder that repeats until you run `magician-ui cleanup`. It records each session's start time in its data folder, and writes status markers only when the status line is on. If cli-ui.json can't be read, magician leaves it as is and session start keeps reading its old values, so the reminder and the markers continue until you fix or delete the file.

### Background monitor

The first time you run `/deploy` in a session, a monitor starts checking GitHub Actions every 90 seconds, for up to three hours, for new failed runs on the current branch. It uses your installed `gh` login, prints only the run ID and stores nothing. It stays silent when `gh`, a git repository, an `origin` remote or a branch is missing.

### Files it writes

Claude Code gives each plugin a data folder, usually `~/.claude/plugins/data/magician-<marketplace>/`, where the last part is the name of the marketplace you installed from. It deletes that folder when you uninstall the plugin. If Claude Code provides no data folder, magician uses `~/.local/share/magician/` instead.

| Location | Contents | Kept for |
|---|---|---|
| Data folder | Session records: time, folder, branch, commit count, changed file names and a one-line summary | Newest 50 |
| Data folder | Session start times | 30 days |
| Data folder | Project learnings, the detected log platform and references you save with `/chronicle` | Until you remove them or uninstall |
| Data folder | Jira and Confluence memory: names of the people, projects, boards, epics, spaces and pages you work with | Until you edit the file or uninstall |
| Data folder | Integration opt-outs, your `/almanac` workspace choice, the pull request versions `/divine` has reviewed, a 30-second Jira and Confluence cache, and pacing and marker files | Until you uninstall |
| `~/.claude/magician/` | Preferences in `cli-ui.json`, the status line renderer, status markers, the code index | Status markers 7 days; the rest until you delete it |
| `~/.claude/settings.json.bak-magician-ui-*` | Backups taken before `magician-ui` edits your settings | Newest 3 |
| `.workspace/` in your project | Specs, plans, research, decisions, post-mortems, `/conjure` designs and mockups, the design preview's chat log, `/divine` review diffs and `/transmute` session state | Until you delete it |
| `.magician/` in your project | Optional `voice` and `lore.off` files you create | Until you delete it |

The `/jira` and `/confluence` skills add to their memory files, `jira-memory.md` and `confluence-memory.md`, without asking, and say "Remembered" when they do. Edit or delete those files to clear them.

### What leaves your machine

- `jira` and `confluence` send requests only to the site URLs you configure, over HTTPS, and don't follow redirects.
- `/seal`, `/deploy`, `/divine`, `/autopsy`, `/jira` and the CI monitor use your own `gh` login, and `/divine` can use `glab`, to talk to GitHub or GitLab. `/seal` also pushes to your git remote.
- Research skills use Claude Code's web tools, which follow your permission settings. If you added the Context7 documentation MCP server, `/magic`, `/divine` and `/transmute` may query it without a prompt.
- `/transmute` can open pages on hosts you name in your Chrome browser, through the Claude in Chrome tools, and read their text and network requests into the conversation. Each browser action goes through your normal permission prompt, the skill is told to stay read-only and mask secrets, and it asks in chat before typing into a page.
- The `/conjure` preview server listens on `127.0.0.1` only. Its page loads one pinned diagram library, mermaid 10.9.3, from jsDelivr in your browser, with an integrity hash so the browser rejects any other file, and hosted web fonts only if you ask for them. `/conjure` can also use a Playwright MCP server, if you have one, to screenshot its design pages; opening a page in that browser asks first.
- `/sentinel` may run a dependency auditor: `npm audit` sends the dependency list to the npm registry; `pip-audit` sends package names and versions to PyPI (or OSV, if you choose it); `safety check` downloads Safety's vulnerability database and, when you use a Safety API key, sends the package list to Safety's servers; `govulncheck` asks the Go vulnerability database at vuln.go.dev about the modules you use, and the go command downloads any module missing from its cache from your module proxy (proxy.golang.org by default); and `cargo audit` downloads the RustSec advisory database from GitHub and, to spot yanked versions, fetches the crates.io index entry of each crate in Cargo.lock.
- `/magic`, `/conjure`, `/autopsy`, `/accelerate`, `/scrutinize` and `/divine` can offer to publish a result as a Claude Artifact, and do so only if you accept.

Nothing goes to the author, and there is no telemetry. Text magician adds to your session is part of your conversation, so Claude Code sends it to your model provider like any other text.

### Settings it can change

magician never changes Claude Code settings on its own. These commands edit `~/.claude/settings.json` only when you or `/statusline` run them, and each one saves a backup first.

| Command | Change | Undo |
|---|---|---|
| `magician-ui enable` | Points the `statusLine` key at magician's renderer, replacing any status line you had | `magician-ui disable`, then restore your earlier status line from the backup |
| `magician-ui disable` | Removes `statusLine` if it runs magician; a status line of your own is left alone | `magician-ui enable` |
| `magician-ui cleanup` | Removes the permission rules, auto-mode setting and old data files that 4.14 and earlier recorded adding | Add rules yourself with `/permissions` |

`/almanac` edits `.gitignore`, `CLAUDE.md` and `.workspace/` in your project and, in Shared mode, commits them. It writes no Claude Code settings.

## Safety guard

Before each Bash or PowerShell command runs, a hook checks the command text against a fixed list of catastrophic forms:

- recursive deletion of the filesystem root, system folders or your home folder
- raw writes to disk devices, and formatting a filesystem
- overwriting critical system files such as the password database
- recursive permission or ownership changes on system folders
- a fork bomb: a shell function that pipes into itself and runs in the background
- piping downloaded or base64-decoded content into a shell or interpreter, or evaluating a downloaded script
- a forced git clean that also deletes ignored files (`-x` or `-X` with `-f` or `--force`, also after git options such as `-C`), such as local secrets files
- in PowerShell, a forced recursive delete of any drive root, anything under `C:\Windows`, or a home folder or its whole contents, and disk-wiping cmdlets

Wrappers such as sudo, env, timeout and nice, and full program paths, are removed before this check. The checks for piping a download into a shell and for fork bombs ignore text inside quotes, so a commit message that only mentions them passes. The other rules split the command at every `;`, `|` and `&`, quoted or not, and at line breaks outside quotes, so a quoted message that holds one of those separators followed by one of the commands above is refused. A match is blocked before Claude Code evaluates permission rules, so no allow rule or permission mode overrides it.

For Bash commands, a second list reads quoted parts too. It blocks a recursive forced delete of a path written from `/`, `eval` of quoted, variable or backquoted content, using `cat` on SSH keys, AWS, gcloud or Azure credentials, or a `.env` or `.env.*` file anywhere in a path (templates such as `.env.example` excepted), and a command that mentions a secret such as a token or password, uses a network tool and pipes into an interpreter.

Bash commands are also refused when they name magician's saved options or the session environment file, read another process's environment through `/proc` (quoted paths included), or print the whole environment with `env`, `printenv`, `set`, `export -p`, `declare -x`, `declare -p` or `compgen -e`, including behind a wrapper such as `sudo` or `timeout` or inside `( )` or `{ }`. During a session that environment holds the Jira and Confluence tokens you entered.

Each line of a multi-line command is checked on its own, and so is a quoted script passed to `sh -c`, `bash -c` or another shell's `-c`, with or without other shell options before it. A command over 50,000 bytes as JSON-escaped in the hook event is refused rather than checked in part: a non-ASCII character counts 2 to 4 bytes, a quote, backslash, tab or line break 2, and another control character 6. The check's running time grows in step with the command's length and stays within a few seconds at that limit, because Claude Code runs a command unchecked if the hook times out.

The guard is one bash script, `scripts/destructive-guard.sh`. It reads the command text and never runs it. It is a denylist and does not sandbox anything. It doesn't block deleting a folder inside your home folder, such as `~/Documents`, or a fork bomb written without both the pipe and the `&`. It can also miss new obfuscations, deletion done from inside a language runtime, and actions taken through tools other than the shell. If the check itself fails, it lets the command through rather than lock up your shell, so keep Claude Code's sandbox and permission prompts on.

## Lore

Lore is magician's bundled guidance for specific technologies: a short core file per topic, with a longer deep-dive file for many of them. At session start magician detects the languages, frameworks, databases and log platform in the project and adds the matching cores within a fixed size budget. When the budget runs short, the security, language, framework and database engine cores are kept ahead of the general guides. Deep dives are read only when the work needs them, and your repository's own conventions always take priority.

| Category | Topics |
|---|---|
| Languages and runtimes | 9, including Python, Go, Rust, Java, Kotlin, Swift and TypeScript |
| Frameworks and libraries | 70, from web frameworks and ORMs to UI styling, data and machine learning |
| Databases | 30 engines across relational, analytics, document, key-value, vector, graph and search, plus a shared guide |
| Logging and observability | 6 platforms with their query languages, plus a general logging guide |
| Infrastructure | 4: Docker, Kubernetes, Terraform and GitHub Actions |
| Working practices | 12, including security, verification, test-driven development, git and models |

The [lore folder](lore/) holds all 133 core files, and the [deep-dive folder](lore/deep/) holds 110 deep dives. Turn lore off by asking Claude to run `magician-ui lore off`, with a `.magician/lore.off` file in the project, or with `MAGICIAN_LORE=0`.

## Workspace

The workspace is a `.workspace/` folder in your project where skills save specs, plans, research and decisions, so later sessions and teammates can pick them up. `/almanac` creates two parts:

| Folder | In git | Contents |
|---|---|---|
| `shared/` | Committed | Team context and roadmap, specs from `/conjure`, plans from `/blueprint`, research from `/magic`, decision records and reviews from `/autopsy` |
| `local/` | Always ignored | Per-machine preferences and the last session's state |

Teammates share `shared/` through git, and each machine keeps its own `local/`. If you choose Private when `/almanac` asks, it ignores the whole `.workspace/` folder instead, so nothing is shared.

## Model support

magician works with the models Claude Code offers, and nothing in it requires a particular model. Skills check what the session's model supports, such as the available effort levels, and keep the earlier behaviour on older models. The model facts they rely on are in [lore/models.md](lore/models.md).

## Troubleshooting

### Jira or Confluence says it is not configured

Follow the steps in [Jira and Confluence](#jira-and-confluence), and start a new session after saving the options. A site URL that starts with `http://` fails unless the site runs on your own computer.

### The status line does not appear

It is off by default. Run `/statusline`, then send a message or two. After an update, ask Claude to run `magician-ui enable` again to refresh the renderer copy. It keeps the components you chose.

### Files are not formatted

Auto-format is off by default. Turn on `auto_format`, and `auto_format_prettier` for prettier, in the plugin options. The formatter must already be on your `PATH`, because magician never installs one.

### No desktop notifications

Notifications are off by default; turn on `desktop_notifications`. iTerm2, WezTerm, Kitty, Ghostty, Warp and Windows Terminal show them. Terminals without a notification escape, such as Terminal.app, the VS Code and JetBrains terminals, Alacritty, plain tmux and many Linux terminals, show none, because the hook only sends a terminal escape sequence and doesn't start a desktop notifier program.

### The safety guard blocked a command

The message names the rule that matched, and there is no override. If you intend the command, run it yourself in a terminal outside Claude Code. If the block looks wrong, open an issue with the command text so the pattern can be fixed.

### Leftover permission rules from older versions

Ask Claude to run `magician-ui status` to list what 4.14 and earlier added, then `magician-ui cleanup` to remove it. Cleanup removes a rule only if it is on the fixed list those versions used and magician's records show they added their list. A rule on that list that you also added yourself, such as `Bash(git status:*)`, can't be told apart and is removed too, so add it back with `/permissions` if you want it. The exceptions are `Bash(jira:*)` and `Bash(confluence:*)`: 4.4 and later removed those on every update, so if the record comes from one of those versions, cleanup keeps them. Without that record, cleanup keeps every rule and names the ones that match the list. Run cleanup before `magician-ui disable --purge`, which deletes the record. Purge refuses while the record still lists entries for cleanup to remove; `magician-ui disable --purge --force` deletes it anyway and leaves those entries in your settings.

### Hooks do not run or show errors

The hooks need bash 3.2 or later. On Windows, run Claude Code with Git Bash installed or inside WSL. Run `/hooks` to confirm magician's entries are listed, check that no settings file sets `disableAllHooks`, and start Claude Code with `--debug` to see each hook's output.

## Upgrading from 4.14

- magician no longer adds permission rules or sets auto mode. Ask Claude to run `magician-ui cleanup` once to remove what earlier versions added.
- In Claude Code, Jira and Confluence settings moved into the plugin options, and the shell environment variables 4.14 read are ignored (the Codex package still reads them). Set the values with `/plugin configure magician`, then delete the old entries from your settings file yourself, because they hold the token in plain text.
- Auto-format and desktop notifications are plugin options now, and both are off by default. The old notification environment variable is ignored.
- Hooks that tracked file reads, suggested searches or MCP servers, logged agent activity, prepared worktrees or summarized the transcript before compaction were removed. After compaction, magician restates the working state from git.
- The Codex package moved to the codex-plugin branch, as described in [Add the plugin](#add-the-plugin).
- If you use the status line, ask Claude to run `magician-ui enable` once to refresh it. Your chosen components are kept.

## Turn it off

To pause magician, disable it. Its hooks, skills and commands stop until you enable it again.

```text
/plugin disable magician@magician
```

To remove it, first ask Claude to run these, in this order, while the plugin is still enabled:

- `magician-ui cleanup` removes permission rules and auto mode left by 4.14 and earlier.
- `magician-ui disable --purge` removes the status line entry, the renderer copy, the status markers and your saved preferences. It refuses while cleanup still has recorded entries to remove; add `--force` to purge anyway and keep those entries.

Then uninstall:

```text
/plugin uninstall magician@magician
```

Claude Code deletes the plugin data folder on uninstall. Delete `~/.claude/magician/` to remove the code index, `~/.local/share/magician/` if it exists, and `.workspace/` or `.magician/` in a project if you no longer want them.

## Privacy and security

magician has no servers and collects no telemetry. [The privacy policy](https://github.com/Alexander-Tyagunov/magician/blob/main/PRIVACY.md) explains what it stores and sends, and [the security policy](https://github.com/Alexander-Tyagunov/magician/blob/main/SECURITY.md) explains how to report a vulnerability.

## Support

For questions and bug reports, [open an issue on GitHub](https://github.com/Alexander-Tyagunov/magician/issues). Report security problems privately as described in [the security policy](https://github.com/Alexander-Tyagunov/magician/blob/main/SECURITY.md), not in a public issue. For anything else, email tyagunov.alex@gmail.com.

## License

MIT, see [LICENSE](LICENSE). If magician saves you time, you can [sponsor its development on GitHub](https://github.com/sponsors/Alexander-Tyagunov).

# Security policy

## Supported versions

Security fixes go into the latest minor release of magician, currently 4.15. Older releases don't receive fixes, so please update before reporting a problem you found on one.

| Version | Supported |
|---|---|
| 4.15.x (latest minor) | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Please don't open a public issue for a security problem. Report it privately:

- Email tyagunov.alex@gmail.com with "magician security" in the subject. This is the main channel.
- If the repository's Security tab shows a "Report a vulnerability" button, you can use GitHub private vulnerability reporting instead.

Please include the magician version (shown in `/plugin`), your Claude Code version and operating system, the steps to reproduce the problem, and the impact you observed.

## What to expect

- An acknowledgement within 5 business days, and a status update within 14 days.
- A fix released as a new version, with a changelog entry that credits you unless you prefer not to be named.
- A request to keep the details private until the fix is released, and agreement with you on when to publish them.

magician is maintained by one person, so complex issues can take longer; you'll be told if that happens.

## Scope

In scope:

- The hook scripts in `scripts/` and the hook list in `hooks/hooks.json`.
- The bundled commands in `bin/`, including how they handle credentials, build requests and write files.
- Skill or agent instructions that could lead Claude to take an unsafe action, or to act without the confirmation the README describes.
- The `/conjure` preview server.
- Any network access, stored data or settings change that the README and privacy policy don't disclose.

Out of scope:

- Problems in Claude Code, git, `gh`, `glab`, third-party MCP servers or the services magician talks to. Please report those to their maintainers.
- Attacks that need an already compromised account or computer.

## Notes on specific areas

- The safety guard is a safety net and does not sandbox anything. It blocks a fixed list of catastrophic command forms and a few risky patterns, described in the README. A way to run one of those listed forms without being blocked is a vulnerability, and so is a command that keeps the guard busy until its hook times out, since Claude Code then runs the command unchecked; a destructive command outside that list is welcome as a feature request in a regular issue.
- Jira and Confluence tokens are copied into the session environment by design, so any command Claude runs in that session can read them. The README and privacy policy document this. Reports that rely only on it are out of scope; a way for a token to be printed, written somewhere else or sent to a host other than the configured site is in scope.
- The hooks are scripts you can read in full in `scripts/`. All of them, the safety guard included, are plain bash. They make no network calls and never change Claude Code settings. Settings change only when `magician-ui` runs at your request, directly or through `/statusline`, and it backs up the file first.

## Bug bounty

There is no bug bounty programme. Reporters are credited in the changelog unless they prefer otherwise.

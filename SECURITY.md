# Security policy

## Supported versions

Security fixes go into the latest minor release of magician, currently 4.18. Older releases don't receive fixes, so please update before reporting a problem you found on one.

| Version | Supported |
|---|---|
| 4.18.x (latest minor) | Yes |
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
- The bundled commands in `tools/` and the launchers magician writes for them, including how they handle credentials, build requests and write files. This includes `tools/plan-render`: it validates `plan.json` before rendering (secret patterns, absolute home paths, destructive command forms in verify commands) and writes only the three plan files and the `history/` snapshot next to it; the `plan.html` it writes loads nothing from the network, and text a reviewer types into the page is never executed, by the page or by Claude. It also includes `tools/ste-lint` and the `ste-lint-hook.sh` hook that runs it: the linter only reads the Markdown files it is given (and the project's `.magician/ste-terms` list) and never modifies a file; a way for the hook to run anything but the bundled linter, to check a file outside the paths the README describes, or to block a tool call, is in scope.
- Skill or agent instructions that could lead Claude to take an unsafe action, or to act without the confirmation the README describes.
- The companion server in `tools/companion/` that serves the `/conjure` design preview and the `/blueprint` plan page, and the `plan-watch` monitor script. The server must listen on `127.0.0.1` only, under a per-run token path, check the `Origin` of every write, accept plan events only as JSON of at most 8 KB with a known type, and write nothing but `events.jsonl` and `state.json` in the plan's local state folder; a way to make it serve a file outside the folder it was started on, accept a write from another origin, or run anything is in scope.
- The plan review loop. Text a reviewer types on the plan page (or into an artifact comment or the artifact database in artifact mode) is untrusted: the skill must never run it, put it into a shell command or a plan command field, or quote it to the model outside a fenced block labelled as a reviewer request, and a revised plan must pass `plan-render check` again before it is rendered. Claude's own watch on the events file runs only `tail` on that file through the `Monitor` tool, after your permission prompt, and the skill pre-approves nothing else for it; a skill or reference text that leads Claude to execute reviewer text, to widen that watch, or to upload the plan to claude.ai without the documented choice is in scope.
- Any network access, stored data or settings change that the README and privacy policy don't disclose.

Out of scope:

- Problems in Claude Code, git, `gh`, `glab`, third-party MCP servers or the services magician talks to. Please report those to their maintainers.
- Attacks that need an already compromised account or computer.

## Notes on specific areas

- The safety guard is a safety net and does not sandbox anything. It blocks a fixed list of catastrophic command forms and a few risky patterns, described in the README. A way to run one of those listed forms without being blocked is a vulnerability. The hook is registered to fail closed (`onFailure: block`, 5-second limit), so a command that keeps the guard busy past its limit is refused rather than run; a way to make the guard's fast path allow a command its full checks would refuse, or a benign command shape that makes the guard refuse everything, is still in scope. A destructive command outside that list is welcome as a feature request in a regular issue.
- The `PreModelSwitch` hook only asks for confirmation while a security scan marker exists or `MAGICIAN_PIN_MODEL=1` is set; it cannot keep a session on a model, and Claude Code's `switchModelsOnFlag` and `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK` settings are the controls for the safety fallback itself.
- Jira and Confluence tokens are copied into the session environment by design, so any command Claude runs in that session can read them. The README and privacy policy document this. Reports that rely only on it are out of scope; a way for a token to be printed, written somewhere else or sent to a host other than the configured site is in scope.
- The hooks are scripts you can read in full in `scripts/`. All of them, the safety guard included, are plain bash. They make no network calls and never change Claude Code settings. Settings change only when `magician-ui` runs at your request, directly or through `/statusline`, and it backs up the file first. One hook, `subagent-stop.sh`, reads the last 4 KiB of a finished magician agent's transcript for a status line; a way for it to read any other file, or to write transcript text anywhere but the documented status record, is in scope.

## Bug bounty

There is no bug bounty programme. Reporters are credited in the changelog unless they prefer otherwise.

# AGENTS.md template

When the user selects it and `AGENTS.md` does not exist, step 5 of `/almanac` writes the part below the marker line to `AGENTS.md`. Fill every `<...>` from the detected stack. If the project has no such command, remove its line. Keep the result at 40 lines or fewer.

<!-- template starts below this line -->
# AGENTS.md

Instructions for coding agents (Codex, Claude Code and others) in this repository. An `AGENTS.md` in a subfolder overrides this file for that folder.

## Commands

- Package manager: <npm | pnpm | yarn | uv | pip | go | cargo | maven | gradle>
- Install: `<install command>`
- Test: `<test command>`
- Lint: `<lint command>`
- Build: `<build command>`

## Before a pull request

Run the verify command: `<test command> && <lint command> && <build command>`.
Fix every failure before you open the pull request.
With magician installed, `/certify` (Claude Code) or `$certify` (Codex) runs it.

## Review rules

Read `REVIEW.md` before you review a change. It says what counts as a failure here, which paths to skip and how many nits to report.

## Where things live

- Specs: `.workspace/shared/specs/`
- Plans: `.workspace/shared/plans/`
- Decisions: `.workspace/shared/decisions/`
- Research: `.workspace/shared/research/`

## Rules

Add a rule here only after an agent gets the same thing wrong twice.

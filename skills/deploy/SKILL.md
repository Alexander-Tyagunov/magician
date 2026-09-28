---
name: deploy
description: CI/CD pipeline management — creates, updates, and monitors GitHub Actions, GitLab CI, and CircleCI pipelines. Use to set up or fix CI/CD.
allowed-tools: Read, Glob, AskUserQuestion, Edit(./.github/workflows/**), Edit(./.gitlab-ci.yml), Edit(./.circleci/**), Bash(gh run list *), Bash(gh run view *), Bash(gh run watch *), Bash(kg query *)
disable-model-invocation: true
argument-hint: "[create|monitor|fix] [provider]"
---

# /deploy — CI/CD Management

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Create and manage CI/CD pipelines.

## Detect Existing Pipeline

```bash
ls .github/workflows/ 2>/dev/null
ls .gitlab-ci.yml 2>/dev/null
ls .circleci/config.yml 2>/dev/null
```

## Process

### Creating a New Pipeline

Gather requirements via a **single AskUserQuestion call** (three questions in one `questions` array — not plain prose) so the user picks structured options instead of free-typing:
- **CI provider** — GitHub Actions · GitLab CI · CircleCI · Other
- **Stages** (multi-select) — lint · test · build · deploy · security scan
- **Environments** — staging · production · both

**End your turn at the AskUserQuestion call.** Wait for the answers before generating any pipeline template. If provider is "Other", follow up for the specific tool.

Once answered, present the **one-shot plan** — provider, stages, environments, and the exact file(s) to be written (e.g. `.github/workflows/ci.yml`) — and gate it with **AskUserQuestion** (not a bare sentence). Frame it "Pipeline plan ready — write it?" with options:
- **Approve** — write the workflow file(s) as planned
- **Revise** — adjust stages / environments (they describe the change)
- **Change scope** — different provider or file layout

**End your turn at the AskUserQuestion call.** Act on the selection; treat any free-form "looks good / approved / yes" as Approve. Write the workflow file only on Approve — this is the write gate; do not weaken it.

### GitHub Actions Template

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup runtime
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security scan
        # magician-scan is provided by the magician plugin (on PATH when the
        # plugin is enabled). Make it optional so the job degrades gracefully
        # in repos where the binary is not installed.
        run: command -v magician-scan >/dev/null 2>&1 && magician-scan . || echo "magician-scan not present, skipping"
```

### GitLab CI Template

```yaml
# .gitlab-ci.yml
stages: [lint, test, build, security]

lint:
  stage: lint
  script: [npm run lint]

test:
  stage: test
  script: [npm test]

build:
  stage: build
  script: [npm run build]
  artifacts:
    paths: [dist/]

security:
  stage: security
  # magician-scan is provided by the magician plugin (on PATH when the plugin
  # is enabled). Optional — degrades gracefully if the binary is not present.
  script:
    - command -v magician-scan >/dev/null 2>&1 && magician-scan . || echo "magician-scan not present, skipping"
```

### Monitoring a Pipeline

Run `gh run watch` with the Bash tool's background option so it does not hold the turn; you are notified when it exits, and its exit status tells you whether the run passed.
```bash
# GitHub Actions
gh run list --limit 5
gh run view <run-id>
gh run watch <run-id> --exit-status   # Bash background option; non-zero exit = the run failed
```
For an unattended "until green" wait, pair with **`/goal`**, or schedule with **`/loop`** (self-paces when the interval is omitted).

**Background CI watcher.** Running `/deploy` also starts magician's `ci-watch` monitor for the session. Every 90 s it asks `gh` for the newest failed GitHub Actions run on the current branch; the first check only records a baseline, and each later new failure is reported as a single line with the run ID only (the number in the run's Actions URL). It prints nothing without `gh`, a git repository, an `origin` remote or a branch, and stops after about 3 hours or when the session ends.

### Fixing a Failed Pipeline (loop until green)

1. Read the failure: `gh run view <id> --log-failed`
2. Fix the underlying issue
3. Push the fix
4. Watch the new run: `gh run watch <id> --exit-status` with the Bash tool's background option — on failure, repeat from step 1 until the run is green.

## Autonomy — approve the plan, then run

After the requirements answers (the three questions — provider, stages, environments — plus the one-shot create plan), execute the remaining phases **autonomously**: detecting existing pipelines, generating the template, and monitoring (`gh run list`/`view`/`watch`, `--log-failed`), plus `kg query` and read-only git need no confirmation question.
Re-gate **only** on this skill's real side effects: edits to the workflow file, `git add`/`commit`/`push`, and PR create. Do not weaken the write gate above. Commands outside the pre-approved list above (git writes, `gh pr create`) still show Claude Code's normal permission prompt.
Doctrine: [lore/autonomy.md](../../lore/autonomy.md).

## Obstacles

If this skill runs as a dispatched unit (under /orchestrate, /weave, /manifest, /transmute, or another skill) and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return an Obstacles block to the caller, alongside whatever you did complete:

```
STATUS: BLOCKED | DEGRADED | NEEDS_CONTEXT
OBSTACLE: <one-line label of what blocked or degraded the task — the claim alone>
BLOCKER: <the specific, actionable cause — distilled, never a raw traceback or dumped log>
SEVERITY: Critical | High | Medium | Low
WORKAROUND: <what you did to proceed and what it leaves unverified; empty if still fully blocked>
RECURRENCE: First-seen | Recurring | Systemic
SCOPE: <this task only | likely hits sibling/downstream work too>
NEXT: <the action or decision the caller must make to clear it — retry with X, supply input Y, accept degraded, or escalate>
```

When invoked interactively by a human, surface the same obstacle in prose instead. Omit the block entirely on a clean run. See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Deploy pipeline configured. Monitor at: <CI URL>."

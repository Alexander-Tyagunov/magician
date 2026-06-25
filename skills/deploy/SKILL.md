---
name: deploy
description: CI/CD pipeline management — creates, updates, and monitors GitHub Actions, GitLab CI, and CircleCI pipelines. Use to set up or fix CI/CD.
allowed-tools: Bash(gh run list:*), Bash(gh run view:*), Bash(gh run watch:*), Bash(ls:*), Read, Write, Edit
disable-model-invocation: true
argument-hint: [create|monitor|fix] [provider]
---

# /deploy — CI/CD Management

Create and manage CI/CD pipelines.

## Detect Existing Pipeline

```bash
ls .github/workflows/ 2>/dev/null
ls .gitlab-ci.yml 2>/dev/null
ls .circleci/config.yml 2>/dev/null
```

## Process

### Creating a New Pipeline

Ask all three questions in one message:
> "To create your pipeline, I need a few details:
> 1. Which CI provider? (GitHub Actions / GitLab CI / CircleCI / other)
> 2. What stages are needed? (lint, test, build, deploy, security scan)
> 3. What environments? (staging, production, both)"

**End your turn. Wait for all answers before generating any pipeline template.**

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

```bash
# GitHub Actions
gh run list --limit 5
gh run view <run-id>
gh run watch <run-id>
```

### Fixing a Failed Pipeline

1. Read the failure: `gh run view <id> --log-failed`
2. Fix the underlying issue
3. Push the fix
4. Monitor: `gh run watch`

## Completion Signal

"Deploy pipeline configured. Monitor at: <CI URL>."

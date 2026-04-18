---
name: deploy
description: CI/CD pipeline management — create, update, and monitor pipelines for GitHub Actions, GitLab CI, CircleCI
keep-coding-instructions: true
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

1. Ask: which CI provider? (GitHub Actions / GitLab CI / CircleCI / other)
2. Ask: what stages are needed? (lint, test, build, deploy, security scan)
3. Ask: what environments? (staging, production)

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
        run: bin/magician-scan .
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
  script: [bin/magician-scan .]
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

Common AI mistakes: hardcoding secrets in workflow files; missing `permissions` restriction; not pinning action versions by SHA; running expensive jobs on every push without path filters.
Commands: lint: `actionlint`, validate: `gh workflow run`.
Gotchas: use `secrets.GITHUB_TOKEN` for repo operations; `on: workflow_dispatch` for manual triggers; cache dependencies with `actions/cache`; `needs:` for job dependencies.

---
name: deploy
description: Gated CI/CD pipeline management for GitHub Actions and GitLab CI, plus configuration review for other providers when their authenticated tooling is available. Use to set up or fix CI/CD.
---

# $deploy — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/deploy/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Codex limits/overrides:

- GitHub Actions and GitLab CI may be created and monitored only when the matching repository/forge is detected and the relevant CLI or authenticated connector is available.
- The source advertises CircleCI but does not provide a complete Codex implementation. For CircleCI, inspect existing configuration and propose changes, but do not claim remote monitoring or mutation unless an authenticated CircleCI capability is actually available.
- Generated CI must not silently skip `magician-scan`. Verify that the packaged executable is reachable in CI or replace it with an explicit, user-approved installation step; otherwise report that scan as unavailable.
- Pipeline file edits require plan approval; triggering, rerunning, cancelling, or deploying requires a separate explicit approval. Monitor via forge read commands or an exec session with polling, not an assumed `Monitor` tool.

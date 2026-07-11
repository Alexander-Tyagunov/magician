---
name: certify
description: Full verification loop — tests, types, lint, build, and a Playwright browser check for UI projects; collects evidence before any success claim. Use to verify a change is actually green.
---

# $certify — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/certify/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

For UI checks, feature-detect Codex Browser Use first and use a configured Playwright tool only as fallback. If neither is available, run all non-browser checks and report browser verification as unavailable rather than claiming a full pass. Poll long-running test/build servers through their exec sessions.

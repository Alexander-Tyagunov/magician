#!/usr/bin/env bash
# Codex PreToolUse(Bash) adapter.  Kept separate from Claude's guard so either
# runtime can evolve its event schema and policy without changing the other.
exec python3 "$(cd "$(dirname "$0")" && pwd)/codex_destructive_guard.py"

---
name: small-diff-stays-inline
description: Fold-first routing. A quick review of a five-line diff stays in the main loop with the lens files as checklists and spawns no subagent, and still finds the planted bug. Written for the desired fold-first behavior of batch 6, so it is tagged expected-fail until that lands. The paired positive is large-plan-fans-out. Self-contained.
tags: [routing, fold-first, expected-fail, review]
runs: 3
max_turns: 15
timeout_seconds: 600
expected_outcome: The review raises that truncate can return more than limit characters or cuts a text of exactly limit characters, and no Agent call was made.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Write, Edit]
---

Quick review with `/divine`, please: report only, no fixes, no PR comments. The branch is not checked out here; the whole change is this diff.

```diff
--- a/util/strings.py
+++ b/util/strings.py
@@ -1,2 +1,7 @@
 """String helpers."""
 
+def truncate(text, limit):
+    """Return `text` cut to at most `limit` characters, with an ellipsis when cut."""
+    if len(text) < limit:
+        return text
+    return text[:limit] + "..."
```

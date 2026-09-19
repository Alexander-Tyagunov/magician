---
name: code-review-routes-to-review-skill
description: When a user asks for the plugin's code review by name, the divine review skill must be invoked (proving it is registered and dispatchable) and the resulting review must catch the planted correctness defects. Self-contained for the eval sandbox.
tags: [smoke, skill-routing, review]
runs: 3
max_turns: 6
allowed_tools: [Read, Grep, Glob, Skill]
---

Use your `divine` code-review skill — invoke the Skill tool with skill `divine` — to do a thorough, multi-lens review of the change below (correctness, security, simplification, test coverage) and summarize the findings by severity.

```diff
+def transfer(amount, source, dest):
+    # move money between two accounts
+    source.balance -= amount
+    dest.balance += amount
+    return True
```

The change ships to a payments service. Review it before merge.

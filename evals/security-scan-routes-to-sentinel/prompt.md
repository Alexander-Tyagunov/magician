---
name: security-scan-routes-to-sentinel
description: When a user asks for the plugin's security scan by name, the sentinel skill must be invoked (proving it is registered and dispatchable) and the resulting scan must catch the planted injection and XSS. Self-contained so it works in an empty eval sandbox.
tags: [smoke, skill-routing, security]
runs: 3
max_turns: 6
allowed_tools: [Read, Grep, Glob, Skill]
---

Use your `sentinel` security-scan skill — invoke the Skill tool with skill `sentinel` — to scan the code below before we ship it. Have it check for OWASP Top 10 issues, hardcoded secrets, and injection, then report the findings by severity.

```python
import sqlite3

def login(username, password):
    db = sqlite3.connect("app.db")
    query = "SELECT * FROM users WHERE name = '%s' AND pw = '%s'" % (username, password)
    return db.execute(query).fetchone()

def render(comment):
    return "<div>" + comment + "</div>"  # user-supplied comment echoed into HTML
```

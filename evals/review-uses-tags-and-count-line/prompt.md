---
name: review-uses-tags-and-count-line
description: A deep /divine review of a small diff speaks the review dialect - the count line "N Important, N Nit, N Pre-existing" opens the summary, every finding has a tag and file:line - and each lens finds its planted defect (correctness, needless abstraction, assertion-free test). Self-contained; the diff is in the prompt. A lens-ab case.
tags: [regression, review, divine, lens-ab]
runs: 3
max_turns: 30
timeout_seconds: 900
expected_outcome: The report opens with the count line, tags every finding and gives it a file:line, and raises the hidden failure in fetch(), the needless RetryPolicyFactory, and the assertion-free test.
allowed_tools: [Read, Grep, Glob, Skill, Agent, AskUserQuestion, Bash, Write, Edit]
---

Do a deep review with `/divine` of the change below before it merges. The branch is not checked out here, so review the diff as given. Report only: no fixes, no PR comments.

```diff
--- /dev/null
+++ b/client/fetch.py
@@ -0,0 +1,24 @@
+import time
+import urllib.request
+
+
+class RetryPolicyFactory:
+    """Builds RetryPolicy objects."""
+
+    def build(self, retries):
+        return RetryPolicy(retries)
+
+
+class RetryPolicy:
+    def __init__(self, retries):
+        self.retries = retries
+
+
+def fetch(url, retries=3):
+    policy = RetryPolicyFactory().build(retries)
+    for attempt in range(policy.retries):
+        try:
+            return urllib.request.urlopen(url, timeout=5).read()
+        except Exception:
+            time.sleep(2 ** attempt)
+    return None
--- /dev/null
+++ b/tests/test_fetch.py
@@ -0,0 +1,13 @@
+import urllib.request
+
+from client.fetch import fetch
+
+
+class FakeResponse:
+    def read(self):
+        return b"ok"
+
+
+def test_fetch_returns_bytes(monkeypatch):
+    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse())
+    fetch("http://example.invalid/data")
```

The change adds an HTTP helper with retries that the billing job will call.

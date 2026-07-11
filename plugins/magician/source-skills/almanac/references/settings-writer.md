# almanac — settings.json permissions writer

Use after the Permissions + Playwright `AskUserQuestion` answers (see [setup-questions.md](setup-questions.md)). Replace `playwright_rules` with the actual list determined from the user's Playwright answer, and fill `detected` from the inspector additionalContext.

```python
import json, os

path = ".claude/settings.json"
s = json.load(open(path)) if os.path.exists(path) else {}
s.setdefault("permissions", {}).setdefault("allow", [])

# playwright_rules determined by AskUserQuestion above
playwright_rules = [...]  # replace with actual list from user's answer

# Always
base = [
    "Bash(git *)",
    "Read(**)",
    "Write(.workspace/**)",
    "Read(.workspace/**)",
    "Bash(> .workspace/**)",
    "Bash(mkdir* .workspace/**)",
    "Bash(bash *conjure/scripts/vc-*.sh*)",
    "Bash(node *conjure/scripts/server.cjs*)",
    "Bash(open http://localhost:*)",
] + playwright_rules
# Stack-specific (add only what was detected)
stack_rules = {
    "javascript": ["Bash(npm *)", "Bash(npx *)"],
    "python":     ["Bash(pytest *)", "Bash(ruff *)", "Bash(pip *)"],
    "go":         ["Bash(go *)"],
    "rust":       ["Bash(cargo *)"],
    "java":       ["Bash(mvn *)", "Bash(gradle *)"],
}
# DETECTED_STACK comes from inspector additionalContext
detected = []  # fill from inspector context
for tech, rules in stack_rules.items():
    if tech in detected:
        base.extend(rules)

for r in base:
    if r not in s["permissions"]["allow"]:
        s["permissions"]["allow"].append(r)

os.makedirs(".claude", exist_ok=True)
json.dump(s, open(path, "w"), indent=2)
print("Permissions saved.")
```

#!/usr/bin/env bash
# PostToolUse(Read) hook — tracks file read patterns and suggests wildcard
# consolidation when Claude repeatedly reads from the same directory tree.
# Surfaces both: "consider excluding this" and "consider allowing via wildcard".

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
ACCESS_FILE="$PLUGIN_DATA/access-patterns.json"

mkdir -p "$PLUGIN_DATA"

INPUT=$(cat)

# PERF: a SINGLE python pass — was two cold-starts (extract file_path, then update the log).
# The program is read into a var (heredoc → PYCODE) and run via `python3 -c` with the hook JSON on
# STDIN (so it isn't limited by argv size), matching the kg-nudge pattern.
PYCODE=""
IFS= read -r -d '' PYCODE <<'PYEOF' || true
import json, os, sys
from pathlib import Path

access_file, home = sys.argv[1], sys.argv[2]

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
inp = d.get("tool_input", d.get("input", d))
file_path = inp.get("file_path", inp.get("path", "")) if isinstance(inp, dict) else ""
if not file_path:
    sys.exit(0)

# Skip non-project paths (tmp, home config, plugin data itself)
_skip = ("/tmp/", "/var/tmp/", os.path.join(home, ".claude"),
         os.path.join(home, ".local", "share", "magician"))
if file_path.startswith(_skip):
    sys.exit(0)

# Load existing access log
if os.path.exists(access_file):
    try:
        with open(access_file) as f:
            data = json.load(f)
    except Exception:
        data = {}
else:
    data = {}

paths      = data.get("paths", [])
by_parent  = data.get("by_parent", {})
suggested  = data.get("suggested", [])
large_sug  = data.get("large_suggested", [])

# Deduplicate: only track each unique path once
if file_path in paths:
    sys.exit(0)

paths.append(file_path)

# One-time nudge on large code reads — for recurring lookups, kg targets the lines.
_CODE = ("py", "js", "jsx", "ts", "tsx", "java", "go", "rs", "rb", "cpp", "cc",
         "c", "h", "cs", "php", "kt", "swift", "scala")
try:
    _sz = os.path.getsize(file_path)
except Exception:
    _sz = 0
if _sz > 20000 and file_path not in large_sug and file_path.rsplit(".", 1)[-1] in _CODE:
    large_sug.append(file_path)
    _rel = os.path.relpath(file_path)
    print(f"Large read (`{_rel}`, ~{_sz // 1000}KB). For recurring lookups in big files, "
          f"`kg query \"<what you need>\"` returns the relevant file:line ranges — cheaper than "
          f"re-reading the whole file (keeps context small).")

# Count accesses grouped by immediate parent and grandparent
p = Path(file_path)
for ancestor in [str(p.parent), str(p.parent.parent)]:
    if ancestor in (".", "/", ""):
        continue
    by_parent[ancestor] = by_parent.get(ancestor, 0) + 1

    # Threshold: 3 reads from the same directory tree → suggest wildcard
    if by_parent[ancestor] == 3 and ancestor not in suggested:
        suggested.append(ancestor)
        rel = os.path.relpath(ancestor)
        print(
            f"I've now read 3 or more files from `{rel}/`. "
            f"Two options worth considering:\n"
            f"• If this directory contains proprietary or sensitive code, add "
            f"`\"Read(**/{rel}/**)\"` to the deny list in settings.json.\n"
            f"• If broad access here is intentional and you want to suppress "
            f"future prompts, that's fine too — just let me know."
        )
        break  # one suggestion per read event

# Persist, cap at 1000 paths
data["paths"]     = paths[-1000:]
data["by_parent"] = by_parent
data["suggested"] = suggested
data["large_suggested"] = large_sug[-500:]

with open(access_file, "w") as f:
    json.dump(data, f, indent=2)
PYEOF

printf '%s' "$INPUT" | python3 -c "$PYCODE" "$ACCESS_FILE" "$HOME" 2>/dev/null || true

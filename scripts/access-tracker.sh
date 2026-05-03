#!/usr/bin/env bash
# PostToolUse(Read) hook — tracks file read patterns and suggests wildcard
# consolidation when Claude repeatedly reads from the same directory tree.
# Surfaces both: "consider excluding this" and "consider allowing via wildcard".

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
ACCESS_FILE="$PLUGIN_DATA/access-patterns.json"

mkdir -p "$PLUGIN_DATA"

INPUT=$(cat)

# Extract file_path from hook JSON
FILE_PATH=$(python3 - "$INPUT" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
    inp = d.get("tool_input", d.get("input", d))
    print(inp.get("file_path", inp.get("path", "")) if isinstance(inp, dict) else "")
except Exception:
    pass
PYEOF
)

[ -z "$FILE_PATH" ] && exit 0

# Skip non-project paths (tmp, home config, plugin data itself)
case "$FILE_PATH" in
  /tmp/*|/var/tmp/*|"$HOME/.claude"*|"$HOME/.local/share/magician"*) exit 0 ;;
esac

python3 - "$ACCESS_FILE" "$FILE_PATH" <<'PYEOF'
import json, os, sys
from pathlib import Path

access_file, file_path = sys.argv[1], sys.argv[2]

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

# Deduplicate: only track each unique path once
if file_path in paths:
    sys.exit(0)

paths.append(file_path)

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

with open(access_file, "w") as f:
    json.dump(data, f, indent=2)
PYEOF

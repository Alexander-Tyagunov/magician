"""Minimal, dependency-free frontmatter reader shared by the Claude-side gates.

The repo's tests deliberately avoid third-party deps (no PyYAML), so this parses the flat
`key: value` frontmatter that agent and skill files use. It is intentionally small: it does
not implement full YAML, only the single-line scalar fields these files rely on.
"""
from __future__ import annotations

import json
from pathlib import Path


def read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Return ({field: value}, body) for a Markdown file with `---` frontmatter.

    Raises AssertionError-friendly ValueError if the fences are missing so callers get a
    clear failure rather than a silent empty dict.
    """
    text = path.read_text(encoding="utf-8")
    all_lines = text.splitlines()
    if not all_lines or all_lines[0].rstrip() != "---":
        raise ValueError(f"{path}: no opening frontmatter fence")
    # The closing fence is the next line that is exactly `---` — never a `---` inside a value
    # (e.g. an argument-hint or description that happens to contain three dashes).
    end = next((n for n in range(1, len(all_lines)) if all_lines[n].rstrip() == "---"), None)
    if end is None:
        raise ValueError(f"{path}: unterminated frontmatter")
    lines = all_lines[1:end]
    body = "\n".join(all_lines[end + 1:])
    fields: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value and value[0] in "|>":
            # YAML block scalar (folded `>`/`>-` or literal `|`/`|-`): gather the following
            # indented lines. Folded joins with spaces; literal keeps newlines.
            folded = value[0] == ">"
            collected: list[str] = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
                collected.append(lines[i].strip())
                i += 1
            joined = (" " if folded else "\n").join(c for c in collected if c or not folded)
            fields[key] = joined.strip()
        elif len(value) >= 2 and value[0] == value[-1] == '"':
            # Double-quoted scalar: decode its escapes (\" inside an argument-hint) when it is
            # JSON-compatible, which the strict gate requires; otherwise just drop the quotes.
            try:
                fields[key] = json.loads(value)
            except ValueError:
                fields[key] = value[1:-1]
        else:
            fields[key] = value.strip('"').strip("'")
    return fields, body.strip()

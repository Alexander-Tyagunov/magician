"""Minimal, dependency-free frontmatter reader shared by the Claude-side gates.

The repo's tests deliberately avoid third-party deps (no PyYAML), so this parses the flat
`key: value` frontmatter that agent and skill files use. It is intentionally small: it does
not implement full YAML, only the single-line scalar fields these files rely on.
"""
from __future__ import annotations

from pathlib import Path


def read_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Return ({field: value}, body) for a Markdown file with `---` frontmatter.

    Raises AssertionError-friendly ValueError if the fences are missing so callers get a
    clear failure rather than a silent empty dict.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: no opening frontmatter fence")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: unterminated frontmatter")
    _, raw, body = parts
    fields: dict[str, str] = {}
    lines = raw.splitlines()
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
        else:
            fields[key] = value.strip('"').strip("'")
    return fields, body.strip()

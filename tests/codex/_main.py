"""Locate the magician main checkout/export the Codex package is built from."""

import os
from pathlib import Path


def main_source() -> Path:
    value = os.environ.get("MAGICIAN_MAIN_SOURCE")
    if not value:
        raise RuntimeError(
            "set MAGICIAN_MAIN_SOURCE to a main checkout/export (the codex gate does this)"
        )
    path = Path(value).resolve()
    if not (path / ".claude-plugin" / "plugin.json").is_file():
        raise RuntimeError(f"{path} is not a magician main checkout")
    return path

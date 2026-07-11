#!/usr/bin/env python3
"""Build the self-contained Codex marketplace package.

The repository root remains the Claude-first source of truth. This builder copies
only the files required by Codex into ``plugins/magician`` and rewrites adapter
links so the installed cache never depends on paths outside the plugin root.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile


REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "plugins" / "magician"
IGNORED_NAMES = {".DS_Store", "__pycache__"}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES or name.endswith(".pyc")}


def _copy_tree(source: Path, destination: Path) -> None:
    symlinks = [path for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        rendered = "\n".join(str(path) for path in symlinks)
        raise RuntimeError(f"refusing to follow symlinks in Codex package source:\n{rendered}")
    shutil.copytree(source, destination, ignore=_ignore, symlinks=False)


def _rewrite_codex_cli(path: Path) -> None:
    """Apply Codex-only state and secret-handling defaults to a copied CLI."""
    text = path.read_text()
    text = text.replace(
        'PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".local", "share", "magician")',
        'PLUGIN_DATA = (os.environ.get("MAGICIAN_HOME") or '
        '(os.path.join(os.environ["CODEX_HOME"], "magician") if os.environ.get("CODEX_HOME") '
        'else os.path.join(os.path.expanduser("~"), ".codex", "magician")))',
    )
    old = '''cmd = ["curl", "-sS", "--compressed", "--connect-timeout", "10", "--max-time", str(timeout),
           "-X", method, "-H", "Authorization: " + _auth(), "-H", "Accept: application/json"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]'''
    new = '''headers = "Authorization: " + _auth() + "\\nAccept: application/json\\n"
    cmd = ["curl", "-sS", "--compressed", "--connect-timeout", "10", "--max-time", str(timeout),
           "-X", method, "-H", "@-"]
    if body is not None:
        headers += "Content-Type: application/json\\n"
        cmd += ["--data-binary", json.dumps(body)]'''
    if old not in text:
        raise RuntimeError(f"expected curl command template not found in {path}")
    text = text.replace(old, new)
    old_run = "subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)"
    if old_run not in text:
        raise RuntimeError(f"expected subprocess call not found in {path}")
    text = text.replace(
        old_run,
        "subprocess.run(cmd, input=headers, capture_output=True, text=True, timeout=timeout + 5)",
    )
    path.write_text(text)


def _rewrite_codex_state_defaults(path: Path) -> None:
    """Prevent copied helpers from defaulting Codex state into Claude paths."""
    text = path.read_text()
    replacements = {
        'MAGICIAN_HOME = os.environ.get("MAGICIAN_HOME") or os.path.join(HOME, ".claude", "magician")':
            'MAGICIAN_HOME = (os.environ.get("MAGICIAN_HOME") or '
            '(os.path.join(os.environ["CODEX_HOME"], "magician") if os.environ.get("CODEX_HOME") '
            'else os.path.join(HOME, ".codex", "magician")))',
        'PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(HOME, ".local", "share", "magician")':
            'PLUGIN_DATA = (os.environ.get("MAGICIAN_HOME") or '
            '(os.path.join(os.environ["CODEX_HOME"], "magician") if os.environ.get("CODEX_HOME") '
            'else os.path.join(HOME, ".codex", "magician")))',
        '${MAGICIAN_HOME:-$HOME/.claude/magician}':
            '${MAGICIAN_HOME:-${CODEX_HOME:-$HOME/.codex}/magician}',
        'Env: MAGICIAN_HOME, CLAUDE_PLUGIN_DATA, CTX_MAX (default 200000).':
            'Env: MAGICIAN_HOME, CODEX_HOME, CTX_MAX (default 200000).',
    }
    original = text
    for old, new in replacements.items():
        text = text.replace(old, new)
    if text == original:
        raise RuntimeError(f"expected Codex state template not found in {path}")
    path.write_text(text)


def _write_manifest(destination: Path) -> None:
    manifest = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text())
    manifest["skills"] = "./skills/"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def _rewrite_adapter_links(skills_root: Path) -> None:
    for skill_file in skills_root.glob("*/SKILL.md"):
        text = skill_file.read_text()
        text = text.replace("../../../skills/", "../../source-skills/")
        skill_file.write_text(text)


def _rewrite_lore_links(lore_root: Path) -> None:
    for document in lore_root.rglob("*.md"):
        text = document.read_text()
        text = text.replace("../skills/", "../source-skills/")
        document.write_text(text)


def build(destination: Path) -> None:
    destination.mkdir(parents=True)
    _write_manifest(destination / ".codex-plugin" / "plugin.json")
    _copy_tree(REPO / ".codex-plugin" / "skills", destination / "skills")
    _rewrite_adapter_links(destination / "skills")
    _copy_tree(REPO / ".codex-plugin" / "references", destination / "references")
    _copy_tree(REPO / "skills", destination / "source-skills")
    _copy_tree(REPO / "lore", destination / "lore")
    _rewrite_lore_links(destination / "lore")
    _copy_tree(REPO / "bin", destination / "bin")
    for name in ("jira", "confluence"):
        _rewrite_codex_cli(destination / "bin" / name)
    for name in ("kg", "ctx"):
        _rewrite_codex_state_defaults(destination / "bin" / name)

    (destination / "hooks").mkdir()
    shutil.copy2(REPO / "hooks" / "codex-hooks.json", destination / "hooks" / "codex-hooks.json")
    (destination / "scripts").mkdir()
    for name in ("codex-destructive-guard.sh", "codex_destructive_guard.py"):
        source = REPO / "scripts" / name
        if not source.is_file():
            raise FileNotFoundError(f"missing Codex runtime file: {source}")
        shutil.copy2(source, destination / "scripts" / name)
    shutil.copy2(REPO / "LICENSE", destination / "LICENSE")


def _differences(left: Path, right: Path) -> list[str]:
    if not right.is_dir():
        return [f"missing generated package: {right}"]
    comparison = filecmp.dircmp(left, right)
    differences: list[str] = []
    differences.extend(f"only in generated: {left / name}" for name in comparison.left_only)
    differences.extend(f"only in tracked package: {right / name}" for name in comparison.right_only)
    differences.extend(f"content differs: {right / name}" for name in comparison.diff_files)
    differences.extend(f"unreadable comparison: {right / name}" for name in comparison.funny_files)
    for name in comparison.common_dirs:
        differences.extend(_differences(left / name, right / name))
    return differences


def _assert_no_symlinks(root: Path) -> None:
    symlinks = [path for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        rendered = "\n".join(str(path) for path in symlinks)
        raise RuntimeError(f"Codex package must not contain symlinks:\n{rendered}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the tracked package is stale")
    args = parser.parse_args()

    temp_parent = Path(tempfile.mkdtemp(prefix="magician-codex-package-", dir=REPO / "plugins"))
    generated = temp_parent / "magician"
    try:
        build(generated)
        _assert_no_symlinks(generated)
        if args.check:
            differences = _differences(generated, TARGET)
            if differences:
                print("Codex package is stale:")
                print("\n".join(f"- {item}" for item in differences))
                return 1
            print("Codex package is synchronized and self-contained.")
            return 0

        if TARGET.exists() or TARGET.is_symlink():
            if TARGET.is_symlink() or TARGET.is_file():
                TARGET.unlink()
            else:
                shutil.rmtree(TARGET)
        os.replace(generated, TARGET)
        _assert_no_symlinks(TARGET)
        for executable in (TARGET / "bin").iterdir():
            if executable.is_file():
                executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        print(f"Built self-contained Codex plugin at {TARGET}")
        return 0
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

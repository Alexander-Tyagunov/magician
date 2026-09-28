#!/usr/bin/env python3
"""Build the self-contained Codex marketplace package from a magician main checkout.

Main (the Claude Code plugin) is the source of truth for skills, lore, bundled CLIs, the LICENSE and
the release version. This branch owns everything Codex-specific (adapters, references, lore
overlays, the Codex hook and guard). The builder combines both into ``plugins/magician``, rewrites
adapter links so the installed cache never depends on paths outside the plugin root, and applies the
Codex-only CLI rewrites. Every rewrite anchor is mandatory: a miss means main drifted and the build
fails instead of silently shipping Claude-only behavior.

Release builds use ``--ref`` so only committed main content is packaged.
"""

from __future__ import annotations

import argparse
import ast
import filecmp
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile


CODEX_ROOT = Path(__file__).resolve().parents[2]
TARGET = CODEX_ROOT / "plugins" / "magician"
MAIN_INPUTS = ("skills", "lore", "tools", "LICENSE", ".claude-plugin/plugin.json")
IGNORED_NAMES = {".DS_Store", "__pycache__"}
# Every file in main's tools/ must be classified: shipped to Codex (reviewed for Codex behavior) or
# excluded. A new, unclassified CLI fails the build instead of shipping unreviewed. The package keeps
# them in bin/, where the Codex adapters look for them.
SHIPPED_BINS = {"jira", "confluence", "kg", "ctx", "magician-scan"}
# Claude-only helpers: they edit ~/.claude/settings.json and the Claude status line. Never shipped.
EXCLUDED_BINS = {"magician-ui", "magician-statusline"}
# Main's skills tell Claude where a bundled command lives when it isn't on PATH, in one line each with
# this prefix. Codex resolves the commands through its adapters instead, so the build drops them.
CLAUDE_FALLBACK_LINE = re.compile(r"^> \*\*Bundled command:\*\* [^\n]*\n(?:\n|\Z)", re.MULTILINE)
# Tracked paths that exist only on a pre-4.15 main (the Codex material used to live there).
PRE_415_CODEX_PATHS = (".codex-plugin", "tests/codex", "plugins/magician")

_CODEX_STATE_PY = (
    '(os.environ.get("MAGICIAN_HOME") or '
    '(os.path.join(os.environ["CODEX_HOME"], "magician") if os.environ.get("CODEX_HOME") '
    'else os.path.join({home}, ".codex", "magician")))'
)
_CODEX_DATA_COMMENT = (
    "# Cache/pacing dir (Codex build): MAGICIAN_HOME, then $CODEX_HOME/magician, then ~/.codex/magician."
)
_MAIN_DATA_COMMENT = (
    "# Cache/pacing dir: MAGICIAN_DATA (the plugin data dir, which the SessionStart hook exports into the\n"
    "# Bash environment), then CLAUDE_PLUGIN_DATA, then ~/.local/share/magician.\n"
)
_MAIN_DATA_LINES = (
    'PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".local", "share", "magician")\n'
    'PLUGIN_DATA = os.environ.get("MAGICIAN_DATA") or PLUGIN_DATA\n'
)
_CREDENTIAL_CLI_STATE = [
    (_MAIN_DATA_COMMENT, _CODEX_DATA_COMMENT + "\n"),
    (_MAIN_DATA_LINES, "PLUGIN_DATA = " + _CODEX_STATE_PY.format(home='os.path.expanduser("~")') + "\n"),
]

# {bin name: [(required anchor, replacement), ...]} — every anchor must be present or the build fails.
STATE_REWRITES: dict[str, list[tuple[str, str]]] = {
    "jira": _CREDENTIAL_CLI_STATE,
    "confluence": _CREDENTIAL_CLI_STATE,
    "kg": [
        ("${MAGICIAN_HOME:-$HOME/.claude/magician}", "${MAGICIAN_HOME:-${CODEX_HOME:-$HOME/.codex}/magician}"),
        (
            'MAGICIAN_HOME = os.environ.get("MAGICIAN_HOME") or os.path.join(HOME, ".claude", "magician")',
            "MAGICIAN_HOME = " + _CODEX_STATE_PY.format(home="HOME"),
        ),
    ],
    "ctx": [
        (
            "Data directory: $MAGICIAN_DATA, else $CLAUDE_PLUGIN_DATA, else ~/.local/share/magician.",
            "Data directory: $MAGICIAN_HOME, else $CODEX_HOME/magician, else ~/.codex/magician.",
        ),
        (
            'PLUGIN_DATA = (os.environ.get("MAGICIAN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")\n'
            '               or os.path.join(HOME, ".local", "share", "magician"))',
            "PLUGIN_DATA = " + _CODEX_STATE_PY.format(home="HOME"),
        ),
    ],
}

# Main reads each connection setting only as os.environ.get("CLAUDE_PLUGIN_OPTION_<KEY>") (Claude Code
# userConfig). Codex has no userConfig, so the Codex copy reads the plain environment names below.
CODEX_CREDENTIAL_ENV: dict[str, tuple[str, ...]] = {
    "JIRA_BASE_URL": ("JIRA_BASE_URL",),
    "JIRA_EMAIL": ("JIRA_EMAIL",),
    "JIRA_API_TOKEN": ("JIRA_API_TOKEN", "JIRA_PAT", "JIRA_PROD_PAT"),
    "CONFLUENCE_BASE_URL": ("CONFLUENCE_BASE_URL",),
    "CONFLUENCE_EMAIL": ("CONFLUENCE_EMAIL",),
    "CONFLUENCE_API_TOKEN": ("CONFLUENCE_API_TOKEN", "CONFLUENCE_PAT", "CONFLUENCE_PROD_PAT"),
}
_OPTION_READ = re.compile(r'os\.environ\.get\("CLAUDE_PLUGIN_OPTION_([A-Z0-9_]+)"\)')
_CONFIG_BEGIN = re.compile(r"(?m)^# ---- magician:connection-config begin\b.*\n")
_CONFIG_END = re.compile(r"(?m)^# ---- magician:connection-config end ----\n")
_NOT_LOADED_BRANCH = re.compile(
    r"(?m)^[ \t]*if not CONFIG_LOADED:\n[ \t]*die\(f\"[A-Za-z]+ settings aren't loaded in this session: \{SETUP_HINT\}\.\"\)\n"
)
# Comment paragraphs in the connection block that mention any of these are Claude-only and dropped.
_CLAUDE_CONFIG_TERMS = (
    "CLAUDE_PLUGIN_OPTION_",
    "/plugin configure",
    "userConfig",
    "MAGICIAN_USERCONFIG_BRIDGE",
    "SessionStart",
    "credential store",
)
# Text that must never survive anywhere in a Codex credential CLI.
_FORBIDDEN_IN_CREDENTIAL_CLI = (
    "CLAUDE_PLUGIN_OPTION_",
    "/plugin configure",
    "userConfig",
    "MAGICIAN_USERCONFIG_BRIDGE",
    "CLAUDE_PLUGIN_DATA",
    "CONFIG_LOADED",
    "settings aren't loaded",
    "the Codex build replaces",
)


def _credential_cli(label: str, prefix: str) -> dict[str, object]:
    token_names = " / ".join(CODEX_CREDENTIAL_ENV[f"{prefix}_API_TOKEN"])
    return {
        "required_keys": {f"{prefix}_BASE_URL", f"{prefix}_API_TOKEN", f"{prefix}_EMAIL"},
        "comment": (
            f"# Codex build: connection settings come straight from the environment Codex runs in —\n"
            f"# {prefix}_BASE_URL, a token ({token_names}) and, for Cloud, {prefix}_EMAIL.\n"
            f"# Codex has no plugin-settings form, so there is no settings bridge to wait for.\n"
        ),
        "assignments": {
            # Codex reads the environment directly, so there is no "not loaded yet" state.
            "CONFIG_LOADED": "",
            "SETUP_HINT": (
                f'SETUP_HINT = ("export {prefix}_BASE_URL and {prefix}_API_TOKEN (plus {prefix}_EMAIL for Cloud) "\n'
                f'              "in your shell profile or the shell that launches Codex, then restart Codex "\n'
                f'              "from that shell; never paste the token into the conversation")'
            ),
            "BASE_URL_HINT": f'BASE_URL_HINT = "the {label} base URL ({prefix}_BASE_URL)"',
        },
    }


CREDENTIAL_CLIS: dict[str, dict[str, object]] = {
    "jira": _credential_cli("Jira", "JIRA"),
    "confluence": _credential_cli("Confluence", "CONFLUENCE"),
}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES or name.endswith(".pyc")}


def _copy_tree(source: Path, destination: Path, exclude: set[str] | None = None) -> None:
    symlinks = [path for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        rendered = "\n".join(str(path) for path in symlinks)
        raise RuntimeError(f"refusing to follow symlinks in Codex package source:\n{rendered}")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = _ignore(directory, names)
        if exclude and Path(directory) == source:
            ignored |= {name for name in names if name in exclude}
        return ignored

    shutil.copytree(source, destination, ignore=ignore, symlinks=False)


def _apply_required(path: Path, text: str, rewrites: list[tuple[str, str]]) -> str:
    for old, new in rewrites:
        if old not in text:
            raise RuntimeError(f"{path}: required Codex rewrite anchor not found:\n{old}")
        text = text.replace(old, new)
    return text


def _rewrite_state_defaults(path: Path) -> None:
    """Point a copied CLI's state at the Codex home; every anchor for this file is mandatory."""
    text = _apply_required(path, path.read_text(), STATE_REWRITES[path.name])
    for leftover in ('os.environ.get("CLAUDE_PLUGIN_DATA")', 'os.path.join(HOME, ".claude", "magician")'):
        if leftover in text:
            raise RuntimeError(f"{path}: Claude state default left after the Codex rewrite: {leftover}")
    path.write_text(text)


def _replace_assignment(path: Path, text: str, name: str, replacement: str) -> str:
    """Replace the single top-level assignment to ``name`` (single- or multi-line) with ``replacement``
    (an empty replacement drops it)."""
    nodes = [
        node
        for node in ast.parse(text).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    ]
    if len(nodes) != 1:
        raise RuntimeError(f"{path}: expected exactly one top-level `{name} = …` assignment, found {len(nodes)}")
    lines = text.splitlines(keepends=True)
    start, end = nodes[0].lineno - 1, nodes[0].end_lineno
    return "".join(lines[:start]) + (replacement + "\n" if replacement else "") + "".join(lines[end:])


def _drop_claude_comment_paragraphs(block: str) -> str:
    kept: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph and not any(term in line for line in paragraph for term in _CLAUDE_CONFIG_TERMS):
            kept.extend(paragraph)
        paragraph.clear()

    for line in block.splitlines(keepends=True):
        if line.lstrip().startswith("#"):
            paragraph.append(line)
        else:
            flush()
            kept.append(line)
    flush()
    return "".join(kept)


def _rewrite_codex_credentials(path: Path) -> None:
    """Rewrite main's userConfig-based connection block for Codex (environment variables only)."""
    spec = CREDENTIAL_CLIS[path.name]
    text = path.read_text()
    begins, ends = list(_CONFIG_BEGIN.finditer(text)), list(_CONFIG_END.finditer(text))
    if len(begins) != 1 or len(ends) != 1 or begins[0].end() > ends[0].start():
        raise RuntimeError(f"{path}: expected one magician:connection-config begin/end block")
    head, block, tail = text[: begins[0].start()], text[begins[0].end() : ends[0].start()], text[ends[0].start() :]
    head += "# ---- magician:connection-config begin (Codex build: environment variables only) ----\n"

    seen: set[str] = set()

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in CODEX_CREDENTIAL_ENV:
            raise RuntimeError(f"{path}: no Codex env mapping for CLAUDE_PLUGIN_OPTION_{key}")
        seen.add(key)
        names = CODEX_CREDENTIAL_ENV[key]
        reads = " or ".join(f'os.environ.get("{name}")' for name in names)
        return reads if len(names) == 1 else f"({reads})"

    block = _OPTION_READ.sub(repl, block)
    missing = spec["required_keys"] - seen  # type: ignore[operator]
    if missing:
        raise RuntimeError(f"{path}: expected CLAUDE_PLUGIN_OPTION_* reads not found: {sorted(missing)}")
    block = spec["comment"] + _drop_claude_comment_paragraphs(block)  # type: ignore[operator]
    for name, replacement in spec["assignments"].items():  # type: ignore[union-attr]
        block = _replace_assignment(path, block, name, replacement)
    # Codex has no "settings not loaded yet" state: drop main's CONFIG_LOADED branch (mandatory anchor).
    tail, pruned = _NOT_LOADED_BRANCH.subn("", tail)
    if pruned != 1:
        raise RuntimeError(f"{path}: expected one `if not CONFIG_LOADED:` settings-not-loaded branch, found {pruned}")
    text = head + block + tail

    for forbidden in _FORBIDDEN_IN_CREDENTIAL_CLI:
        if forbidden in text:
            raise RuntimeError(f"{path}: Claude-only text left after the Codex rewrite: {forbidden}")
    assert_stdin_secret(path, text)
    path.write_text(text)


# Names and literals that must never reach curl's argv: the auth header travels on stdin only.
_SECRET_NAMES = {"_auth", "TOKEN", "EMAIL", "headers"}
_SECRET_LITERALS = ("authorization", "bearer", "basic")


def assert_stdin_secret(path: Path, text: str) -> None:
    """Structurally check the stdin-secret invariant with ``ast`` (not substring matching).

    Every ``cmd = [...]`` / ``cmd += [...]`` element must be free of the auth helper, the token,
    the email, the header string and any Authorization/Bearer/Basic literal (so f-strings, ``%`` or
    ``+`` formatting of the token all fail); the base command must pass ``"-H", "@-"``; and every
    ``subprocess.run(cmd, …)`` must send ``input=headers``.
    """
    tree = ast.parse(text)
    lists: list[ast.List] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "cmd" for t in node.targets):
            value = node.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "cmd":
            value = node.value
        else:
            continue
        if not isinstance(value, ast.List):
            raise RuntimeError(f"{path}:{node.lineno}: curl `cmd` must be built from list literals only")
        lists.append(value)
    if not lists:
        raise RuntimeError(f"{path}: no curl `cmd = [...]` found for the stdin-secret check")
    for value in lists:
        for element in value.elts:
            for sub in ast.walk(element):
                if isinstance(sub, ast.Name) and sub.id in _SECRET_NAMES:
                    raise RuntimeError(f"{path}:{element.lineno}: curl argv references `{sub.id}` — the auth header must go on stdin")
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and any(
                    word in sub.value.lower() for word in _SECRET_LITERALS
                ):
                    raise RuntimeError(f"{path}:{element.lineno}: curl argv carries an auth literal {sub.value!r}")
    stdin_header = any(
        isinstance(a, ast.Constant) and a.value == "-H" and isinstance(b, ast.Constant) and b.value == "@-"
        for value in lists
        for a, b in zip(value.elts, value.elts[1:])
    )
    if not stdin_header:
        raise RuntimeError(f"{path}: curl `cmd` lacks \"-H\", \"@-\" (headers on stdin)")
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "cmd"
    ]
    if not runs:
        raise RuntimeError(f"{path}: no subprocess.run(cmd, …) found for the stdin-secret check")
    for node in runs:
        keywords = {kw.arg: kw.value for kw in node.keywords}
        given = keywords.get("input")
        if not (isinstance(given, ast.Name) and given.id == "headers"):
            raise RuntimeError(f"{path}:{node.lineno}: subprocess.run(cmd, …) must pass input=headers")


def _write_manifest(destination: Path, source: Path) -> None:
    template = json.loads((CODEX_ROOT / ".codex-plugin" / "plugin.json").read_text())
    if "version" in template:
        raise RuntimeError(".codex-plugin/plugin.json must not carry a version; it comes from main")
    version = json.loads((source / ".claude-plugin" / "plugin.json").read_text())["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RuntimeError(f"unexpected main version: {version!r}")
    manifest = {"name": template["name"], "version": version}
    manifest.update((key, value) for key, value in template.items() if key != "name")
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


def _overlay_codex_lore(lore_root: Path) -> None:
    """Replace provider-specific lore with Codex-owned guidance in the Codex package."""
    source_root = CODEX_ROOT / ".codex-plugin" / "lore"
    for source in source_root.rglob("*"):
        if source.is_symlink():
            raise RuntimeError(f"refusing to follow symlink in Codex lore overlay: {source}")
        destination = lore_root / source.relative_to(source_root)
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            if not destination.is_file():
                raise RuntimeError(f"Codex lore overlay {source.name} has no counterpart in main lore/")
            shutil.copy2(source, destination)


def _strip_claude_fallbacks(skills_root: Path) -> None:
    """Drop the Claude-only fallback lines from the copied skills; at least one is mandatory."""
    stripped = 0
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        text, count = CLAUDE_FALLBACK_LINE.subn("", skill_file.read_text())
        stripped += count
        skill_file.write_text(text)
    for doc in sorted(skills_root.rglob("*.md")):
        text = doc.read_text()
        if "**Bundled command:**" in text or "CLAUDE_PLUGIN_ROOT}/tools/" in text:
            raise RuntimeError(f"{doc}: a Claude-only bundled-command fallback is left after stripping")
    if not stripped:
        raise RuntimeError("main skills have no bundled-command fallback lines; did main drift?")


def _check_bin_classification(bin_root: Path) -> None:
    names = {path.name for path in bin_root.iterdir() if path.name not in IGNORED_NAMES}
    unknown = sorted(names - SHIPPED_BINS - EXCLUDED_BINS)
    if unknown:
        raise RuntimeError(
            f"main tools/ has unclassified files {unknown}: add each to SHIPPED_BINS (after a Codex review) "
            "or EXCLUDED_BINS in build_package.py"
        )
    missing = sorted(SHIPPED_BINS - names)
    if missing:
        raise RuntimeError(f"main tools/ is missing shipped Codex CLIs {missing}")


def build(destination: Path, source: Path) -> None:
    destination.mkdir(parents=True)
    _write_manifest(destination / ".codex-plugin" / "plugin.json", source)
    _copy_tree(CODEX_ROOT / ".codex-plugin" / "skills", destination / "skills")
    _rewrite_adapter_links(destination / "skills")
    _copy_tree(CODEX_ROOT / ".codex-plugin" / "references", destination / "references")
    _copy_tree(source / "skills", destination / "source-skills")
    _strip_claude_fallbacks(destination / "source-skills")
    _copy_tree(source / "lore", destination / "lore")
    _overlay_codex_lore(destination / "lore")
    _rewrite_lore_links(destination / "lore")
    _check_bin_classification(source / "tools")
    _copy_tree(source / "tools", destination / "bin", exclude=EXCLUDED_BINS)
    for name in STATE_REWRITES:
        _rewrite_state_defaults(destination / "bin" / name)
    for name in CREDENTIAL_CLIS:
        _rewrite_codex_credentials(destination / "bin" / name)

    (destination / "hooks").mkdir()
    shutil.copy2(CODEX_ROOT / "hooks" / "codex-hooks.json", destination / "hooks" / "codex-hooks.json")
    (destination / "scripts").mkdir()
    for name in ("codex-destructive-guard.sh", "codex_destructive_guard.py"):
        runtime = CODEX_ROOT / "scripts" / name
        if not runtime.is_file():
            raise FileNotFoundError(f"missing Codex runtime file: {runtime}")
        shutil.copy2(runtime, destination / "scripts" / name)
    shutil.copy2(source / "LICENSE", destination / "LICENSE")


def _differences(left: Path, right: Path) -> list[str]:
    if not right.is_dir():
        return [f"missing generated package: {right}"]
    comparison = filecmp.dircmp(left, right, ignore=sorted(IGNORED_NAMES))
    differences: list[str] = []
    differences.extend(f"only in generated: {left / name}" for name in comparison.left_only)
    differences.extend(f"only in tracked package: {right / name}" for name in comparison.right_only)
    differences.extend(f"content differs: {right / name}" for name in comparison.diff_files)
    differences.extend(f"unreadable comparison: {right / name}" for name in comparison.funny_files)
    for name in comparison.common_files:
        if filecmp.cmp(left / name, right / name, shallow=False) is False:
            differences.append(f"content differs: {right / name}")
        if _exec_bits(left / name) != _exec_bits(right / name):
            differences.append(f"exec bit differs: {right / name}")
    for name in comparison.common_dirs:
        differences.extend(_differences(left / name, right / name))
    return sorted(set(differences))


def _exec_bits(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode) & 0o111


def _assert_no_symlinks(root: Path) -> None:
    symlinks = [path for path in root.rglob("*") if path.is_symlink()]
    if symlinks:
        rendered = "\n".join(str(path) for path in symlinks)
        raise RuntimeError(f"Codex package must not contain symlinks:\n{rendered}")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    return result


def _safe_extract(tar: tarfile.TarFile, into: Path) -> None:
    if hasattr(tarfile, "data_filter"):  # Python 3.12+ and patched 3.8-3.11 releases
        tar.extractall(into, filter="data")
        return
    root = into.resolve()
    for member in tar.getmembers():
        target = (root / member.name).resolve()
        if not (member.isfile() or member.isdir()) or not (target == root or target.is_relative_to(root)):
            raise RuntimeError(f"refusing unsafe archive member: {member.name}")
    tar.extractall(into)


def _export_ref(repo: Path, ref: str, into: Path) -> Path:
    """Materialize the committed main inputs at ``ref`` only (no untracked files, no empty dirs)."""
    if repo.resolve() == CODEX_ROOT.resolve():
        raise RuntimeError("--source must be a magician main checkout, not this codex-plugin worktree")
    resolved = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if resolved.returncode != 0:
        raise RuntimeError(f"--ref {ref!r} is not a commit in {repo}: {resolved.stderr.decode().strip()}")
    stale = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", *PRE_415_CODEX_PATHS)
    if stale.returncode != 0:
        raise RuntimeError(f"git ls-tree {ref} failed in {repo}: {stale.stderr.decode().strip()}")
    if stale.stdout.strip():
        first = stale.stdout.decode().splitlines()[0]
        raise RuntimeError(
            f"--ref {ref} still tracks Codex authoring files (e.g. {first}); "
            "is it a pre-4.15 main or the codex-plugin branch?"
        )
    archive = _git(repo, "archive", "--format=tar", ref, "--", *MAIN_INPUTS)
    if archive.returncode != 0:
        raise RuntimeError(f"git archive {ref} failed in {repo}: {archive.stderr.decode().strip()}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        _safe_extract(tar, into)
    return into


def _assert_main_checkout(source: Path) -> None:
    if source.resolve() == CODEX_ROOT.resolve():
        raise RuntimeError("--source must be a magician main checkout, not this codex-plugin worktree")
    for rel in MAIN_INPUTS:
        if not (source / rel).exists():
            raise RuntimeError(f"--source is missing {rel}; is it a magician main checkout?")
    # A git checkout: judge by tracked files, so ignored/untracked leftovers of an old checkout
    # (__pycache__, a stale plugins/ build) do not count. An export (no .git): judge by what exists.
    top = _git(source, "rev-parse", "--show-toplevel")
    if top.returncode == 0 and Path(top.stdout.decode().strip()).resolve() == source.resolve():
        tracked = _git(source, "ls-files", "--", *PRE_415_CODEX_PATHS).stdout.decode().splitlines()
    else:
        tracked = [
            path.relative_to(source).as_posix()
            for rel in PRE_415_CODEX_PATHS
            if (source / rel).exists()
            for path in [source / rel, *(source / rel).rglob("*")]
            if path.is_file() and not path.name.endswith(".pyc") and path.name not in IGNORED_NAMES
        ]
    if tracked:
        raise RuntimeError(
            f"--source contains Codex authoring files (e.g. {tracked[0]}); is it a pre-4.15 main?"
        )


def main() -> int:
    if sys.version_info < (3, 9):
        raise SystemExit("build_package.py needs Python 3.9 or newer")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="magician main checkout (clone or worktree)")
    parser.add_argument("--ref", help="build from the committed <ref> of --source via git archive (release builds)")
    parser.add_argument("--check", action="store_true", help="fail if the tracked package differs from the build")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="magician-main-") as exported:
        source = _export_ref(args.source, args.ref, Path(exported)) if args.ref else args.source.resolve()
        _assert_main_checkout(source)
        (CODEX_ROOT / "plugins").mkdir(exist_ok=True)
        temp_parent = Path(tempfile.mkdtemp(prefix="magician-codex-package-", dir=CODEX_ROOT / "plugins"))
        generated = temp_parent / "magician"
        try:
            build(generated, source)
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

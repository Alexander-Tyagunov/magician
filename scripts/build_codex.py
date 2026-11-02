#!/usr/bin/env python3
"""Build the Codex / ChatGPT plugin from the magician source tree (stdlib only).

Usage: python3 scripts/build_codex.py [--out DIR] [--no-validate]
       (normally run through scripts/build-codex.sh)

The output DIR (default dist/codex/magician) holds a portable Agent Plugins package:
  plugin.json                 name, version, ... plus extensions.com.openai {interface, onboardingSkill}
  skills/<name>/SKILL.md      every skill, frontmatter reduced to the Agent Skills (AAIF) keys
  skills/<agent>-lens/SKILL.md  one review-lens skill per agents/*.md
  lore/, tools/               copied with the same relative layout, so skill links still resolve
  README.md, LICENSE
and DIR/../.agents/plugins/marketplace.json lists it for `codex plugin marketplace add`.

Dropped: hooks/, monitors/, output-styles/, mods/, .claude-plugin/, tests/, evals/, scripts/, userConfig,
and the Claude Code-only status line (skills/statusline, tools/magician-statusline, tools/magician-ui:
they wire Claude Code's `statusLine` setting and the session-start hooks, which Codex does not have).
Codex-only text rewrites (the source files stay as they are, since Claude Code has the guard, the
transcripts and the plugin variables): see CODEX_TEXT_REWRITES, CODEX_FILE_NOTES and CLAUDE_VAR_RE.
The output is deterministic: sorted traversal, fixed file modes, no timestamps.
The conversion rules come from OpenAI's "Submit your Claude Code plugin" and "Package your plugin"
guides; the Codex mapping table is in lore/skill-authoring.md ("## On Codex").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "codex" / "magician"

# Agent Skills (agentskills.io, AAIF) top-level keys. Everything else is a Claude Code extension.
AAIF_KEYS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools")
DESC_MAX = 1024          # Agent Skills spec limit for `description`
COMPAT_MAX = 500         # Agent Skills spec limit for `compatibility`
META_PREFIX = "claude-code."   # metadata is a flat string->string map, so extension keys get a prefix
DROPPED_DIRS = ("hooks", "monitors", "output-styles", "mods", ".claude-plugin", "tests", "evals",
                "scripts", "agents", "commands", ".codex-plugin")
OUTPUT_MARKER = "plugin.json"
# Claude Code-only parts that do not work on Codex and are left out of the package (README says so).
EXCLUDED_SKILLS = ("statusline",)
EXCLUDED_TOOLS = ("magician-statusline", "magician-ui")
# The Agent Plugins manifest schema, as OpenAI's "Package your plugin" guide
# (https://developers.openai.com/plugins/build/plugins) gives it in its plugin.json example.
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
# Any Claude Code variable left in generated Markdown is a build failure (validate()).
CLAUDE_VAR_RE = re.compile(r"\$\{?CLAUDE_[A-Z_]+")

# Codex-only rewrites of one exact passage in one generated file: (output path, old, new). A rewrite
# whose old text is missing fails the build, so a source edit cannot silently bring the claim back.
CODEX_TEXT_REWRITES = [
    ("skills/sentinel/SKILL.md",
     "Independent of any scan, magician ships a `PreToolUse(Bash|PowerShell)` hook, `scripts/destructive-guard.sh` "
     "(self-contained plain bash — no other interpreter), that **unconditionally blocks catastrophic commands**:",
     "On Claude Code, magician also ships a `PreToolUse(Bash|PowerShell)` hook, the destructive guard, that blocks "
     "catastrophic commands; this Codex package ships no hooks, so nothing here blocks them, and they are the "
     "commands never to run:"),
    ("skills/chronicle/SKILL.md",
     "The path is this session's transcript: Glob `*/${CLAUDE_SESSION_ID}.jsonl` under `~/.claude/projects/`.",
     "The path is this session's transcript. On Codex there is none: session transcripts are Claude Code only, "
     "so say that the context % is not available here and report only the learnings count."),
]
# Codex-only notes: a generated Markdown file with a line that matches the pattern gets the note
# once (in a skill's "On Codex" footer for SKILL.md, as a closing line for any other file).
CODEX_FILE_NOTES = [
    (re.compile(r"destructive[- ]guard", re.I),
     "On Codex: this package ships no hooks; the destructive guard is Claude Code only."),
    (re.compile(r"~/\.claude/projects/"),
     "On Codex: session transcripts (`~/.claude/projects/`) are Claude Code only; `ctx pct` has no transcript to read."),
    (re.compile(r"\bmagician-ui\b"),
     "On Codex: `magician-ui` and the status line are Claude Code only and do not ship here; "
     "turn STE-lite on with a `.magician/ste` file that holds `on`, or `MAGICIAN_STE=1`."),
]

# Codex mappings used by the per-skill "## On Codex" footer. Same rows as lore/skill-authoring.md.
# (id, detection regex over the skill's text, footer line)
MAPPINGS = [
    ("goal", r"(?<![\w/])/goal\b",
     "`/goal`: Codex has the same `/goal` command (outcome, constraints and how to verify); one goal per chat."),
    ("workflow", r"\bWorkflows?\b",
     "`Workflow` fan-out: run one `codex exec --worktree` per independent unit, or use `/worktree` for parallel chats."),
    ("subagents", r"subagent|`Task`|`Agent`|\bTask tool|\bAgent tool|\bTask calls?\b",
     "Subagents (`Task`/`Agent`): Codex subagents are `.codex/agents/*.toml` files (`name`, `description`, "
     "`developer_instructions`); the review lenses ship here as `*-lens` skills."),
    ("hooks", r"\bhooks?\b",
     "Hooks: this package has none (the public directory does not accept them); local Codex hooks live in "
     "`.codex/hooks.json` and need trust through `/hooks`."),
    ("monitor", r"\bMonitor\b",
     "`Monitor`: Codex has no event monitor; poll the file or command instead."),
    ("ask", r"AskUserQuestion",
     "`AskUserQuestion`: Codex has no question form; ask the same question in prose, with the same options, "
     "and wait for the reply."),
    ("full-auto", r"--full-auto",
     "`--full-auto` is gone from `codex exec`; use `--sandbox workspace-write`."),
    ("claude-md", r"CLAUDE\.md",
     "`CLAUDE.md`: Codex reads `AGENTS.md` (root to current folder, nearest wins)."),
    ("userconfig", r"/plugin configure|userConfig|user_config",
     "Plugin options: Codex has no plugin options; set `MAGICIAN_JIRA_BASE_URL`, `MAGICIAN_JIRA_EMAIL`, `MAGICIAN_JIRA_API_TOKEN`, "
     "`MAGICIAN_CONFLUENCE_BASE_URL`, `MAGICIAN_CONFLUENCE_EMAIL`, `MAGICIAN_CONFLUENCE_API_TOKEN` in the environment Codex starts from."),
]
MAPPING_IDS = [m[0] for m in MAPPINGS]

CONN_BEGIN = "# ---- magician:connection-config begin"
CONN_END = "# ---- magician:connection-config end ----"
CONN_BLOCK = {
    "jira": '''# ---- magician:connection-config begin (Codex build: read from the environment) ----
# Codex has no plugin options. Set MAGICIAN_JIRA_BASE_URL, MAGICIAN_JIRA_API_TOKEN and, for Jira Cloud, MAGICIAN_JIRA_EMAIL in
# the environment Codex starts from.
BASE = (os.environ.get("MAGICIAN_JIRA_BASE_URL") or "").strip().rstrip("/")
TOKEN = (os.environ.get("MAGICIAN_JIRA_API_TOKEN") or "").strip()
EMAIL = (os.environ.get("MAGICIAN_JIRA_EMAIL") or "").strip()
CONFIG_LOADED = True
SETUP_HINT = ("set MAGICIAN_JIRA_BASE_URL and MAGICIAN_JIRA_API_TOKEN (and MAGICIAN_JIRA_EMAIL for Jira Cloud) in the environment "
              "Codex starts from, then start a new session")
BASE_URL_HINT = "MAGICIAN_JIRA_BASE_URL"
# ---- magician:connection-config end ----''',
    "confluence": '''# ---- magician:connection-config begin (Codex build: read from the environment) ----
# Codex has no plugin options. Set MAGICIAN_CONFLUENCE_BASE_URL, MAGICIAN_CONFLUENCE_API_TOKEN and, for Confluence Cloud,
# MAGICIAN_CONFLUENCE_EMAIL in the environment Codex starts from. On one Atlassian Cloud site the Jira token
# is reused when the hosts match and Jira Cloud is set up.
BASE = (os.environ.get("MAGICIAN_CONFLUENCE_BASE_URL") or "").strip().rstrip("/")
TOKEN = (os.environ.get("MAGICIAN_CONFLUENCE_API_TOKEN") or "").strip()
EMAIL = (os.environ.get("MAGICIAN_CONFLUENCE_EMAIL") or "").strip()
_jira_base = (os.environ.get("MAGICIAN_JIRA_BASE_URL") or "").strip()
_jira_email = (os.environ.get("MAGICIAN_JIRA_EMAIL") or "").strip()
if not TOKEN and BASE and _jira_base and _jira_email and \\
        urllib.parse.urlsplit(BASE.lower())[:2] == urllib.parse.urlsplit(_jira_base.lower())[:2]:
    TOKEN = (os.environ.get("MAGICIAN_JIRA_API_TOKEN") or "").strip()
    EMAIL = EMAIL or _jira_email
CONFIG_LOADED = True
SETUP_HINT = ("set MAGICIAN_CONFLUENCE_BASE_URL and MAGICIAN_CONFLUENCE_API_TOKEN (and MAGICIAN_CONFLUENCE_EMAIL for Confluence Cloud) "
              "in the environment Codex starts from, then start a new session")
BASE_URL_HINT = "MAGICIAN_CONFLUENCE_BASE_URL"
# ---- magician:connection-config end ----''',
}

LINK_RE = re.compile(r"(\]\()([^)\s]+)(\))")
# Only path-shaped targets are links to files: a folder part or a file extension (code such as
# `](href)` or `](err)` is not).
PATH_TARGET = re.compile(r"^(?:[\w.-]*/[\w./<>-]*|[\w-][\w.-]*\.[A-Za-z0-9]+)(?:#[\w.-]*)?$")


def is_file_link(target: str) -> bool:
    if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith(("#", "<")):
        return False
    return bool(PATH_TARGET.match(target))


FENCE_RE = re.compile(r"(?ms)(^[ \t]*```.*?^[ \t]*```[^\n]*$)")


def outside_fences(text: str, fn) -> str:
    """Apply fn to the text outside ``` fences only."""
    parts = FENCE_RE.split(text)
    return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


VAR_ROOT = "${CLAUDE_PLUGIN_ROOT}"
VAR_SKILL = "${CLAUDE_SKILL_DIR}"
VAR_DATA = "${CLAUDE_PLUGIN_DATA}"
DATA_REPLACEMENT = "${MAGICIAN_DATA:-$HOME/.local/share/magician}"
# A sentence that names one of these is about a Claude Code feature, so "Claude Code" stays.
CC_FEATURE = re.compile(
    r"Artifact|Monitor|Workflow|hook|settings|bundled|best practices|CLAUDE\.md|plugin|MCP|Cowork|"
    r"worktree|permission|status ?line|output.style|subagent|AskUserQuestion|auto mode|plan mode|"
    r"transcript|compact|the form|`|/[a-z]|\bclaude\b|\d+\.\d+|Claude Code's own|Claude chat",
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class BuildError(Exception):
    pass


# ------------------------------------------------------------------ frontmatter (source side)
def split_frontmatter(text: str) -> tuple[list[str], str]:
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise BuildError("no opening frontmatter fence")
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    raise BuildError("unterminated frontmatter")


def _scalar(raw: str):
    if raw.startswith('"'):
        return json.loads(raw)
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def parse_frontmatter(lines: list[str]) -> list[tuple[str, object]]:
    """Ordered (key, value) pairs. Values: str, list[str] (block list) or raw nested text."""
    out: list[tuple[str, object]] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r")
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if raw in (">", ">-", ">+", "|", "|-", "|+"):
            chunk = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] == " "):
                chunk.append(lines[i].strip())
                i += 1
            sep = " " if raw[0] == ">" else "\n"
            out.append((key, sep.join(c for c in chunk if c)))
        elif raw == "":
            items, nested = [], []
            while i < len(lines) and lines[i][:1] == " ":
                s = lines[i].strip()
                i += 1
                if s.startswith("- "):
                    items.append(str(_scalar(s[2:].strip())))
                else:
                    nested.append(s)
            out.append((key, items if items else "\n".join(nested)))
        else:
            out.append((key, _scalar(raw)))
    return out


def meta_value(v) -> str:
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def render_frontmatter(pairs: list[tuple[str, object]]) -> str:
    """Emit only AAIF keys; strings JSON-quoted (valid YAML), metadata as one flow mapping."""
    lines = ["---"]
    for key, value in pairs:
        if key == "metadata":
            lines.append("metadata: " + json.dumps(value, ensure_ascii=False, sort_keys=True))
        else:
            lines.append(f"{key}: " + json.dumps(value, ensure_ascii=False))
    lines.append("---")
    return "\n".join(lines) + "\n"


def convert_frontmatter(pairs, *, name: str, license_id: str, description: str | None = None,
                        extra_meta: dict | None = None) -> list[tuple[str, object]]:
    src = dict(pairs)
    meta: dict[str, str] = {}
    for key, value in pairs:
        if key not in AAIF_KEYS:
            meta[META_PREFIX + key] = meta_value(value)
    if isinstance(src.get("metadata"), str) and src["metadata"].strip():
        raise BuildError(f"{name}: source metadata must be converted by hand")
    meta.update(extra_meta or {})
    out: list[tuple[str, object]] = [("name", name),
                                     ("description", description if description is not None
                                      else str(src.get("description", "")))]
    out.append(("license", str(src.get("license", license_id))))
    if "compatibility" in src:
        out.append(("compatibility", str(src["compatibility"])))
    if "allowed-tools" in src:
        tools = src["allowed-tools"]
        out.append(("allowed-tools", ", ".join(tools) if isinstance(tools, list) else str(tools)))
    if meta:
        out.append(("metadata", dict(sorted(meta.items()))))
    return out


# ------------------------------------------------------------------ text rewrites
def rel(target: PurePosixPath, from_dir: PurePosixPath) -> str:
    r = os.path.relpath(str(target), str(from_dir))
    return r.replace(os.sep, "/")


class Rewriter:
    """Rewrites one Markdown file of the output: plugin variables, links, provider-neutral wording."""

    def __init__(self, path_map: dict[str, str], out_files: set[str]):
        self.path_map = path_map      # source rel path -> output rel path
        self.out_files = out_files    # output rel paths (files that will exist)
        self.unlinked: list[str] = []
        self.wording = 0

    def variables(self, text: str, out_rel: str, skill_dir: str | None) -> tuple[str, set[str]]:
        notes: set[str] = set()
        here = PurePosixPath(out_rel).parent
        root_rel = rel(PurePosixPath("."), here)

        def agent_ref(m: re.Match) -> str:
            notes.add("paths")
            return rel(PurePosixPath("skills"), here) + f"/{m.group(1)}-lens/SKILL.md"

        text = re.sub(r"\$\{CLAUDE_PLUGIN_ROOT\}/agents/([<>\w-]+)\.md", agent_ref, text)
        if VAR_ROOT in text:
            notes.add("paths")
            text = text.replace(VAR_ROOT, root_rel)
        if VAR_SKILL in text:
            if skill_dir is None:
                raise BuildError(f"{out_rel}: {VAR_SKILL} outside a skill")
            notes.add("paths")
            text = text.replace(VAR_SKILL, rel(PurePosixPath(skill_dir), here))
        # A Claude data folder kept as a fallback inside another default collapses to that default.
        text, n = re.subn(r"\$\{CLAUDE_PLUGIN_DATA:-([^{}]*)\}", r"\1", text)
        if n:
            notes.add("data")
        if VAR_DATA in text:
            notes.add("data")
            text = text.replace(VAR_DATA, DATA_REPLACEMENT)
        # Codex has no Claude session id; nothing sets MAGICIAN_SESSION_ID unless the user does.
        text = text.replace("${CLAUDE_SESSION_ID}", "${MAGICIAN_SESSION_ID:-unknown}")
        return text, notes

    def links(self, text: str, src_rel: str, out_rel: str) -> str:
        src_dir = PurePosixPath(src_rel).parent
        out_dir = PurePosixPath(out_rel).parent

        def fix(m: re.Match) -> str:
            target = m.group(2)
            if not is_file_link(target):
                return m.group(0)
            path, sep, anchor = target.partition("#")
            if not path:
                return m.group(0)
            src_target = os.path.normpath(str(src_dir / path)).replace(os.sep, "/")
            mapped = self.path_map.get(src_target)
            if mapped is None and src_target in self.out_files:
                mapped = src_target
            if mapped is None:
                # A folder link (e.g. lore/deep/) resolves when the folder ships.
                if any(f.startswith(src_target.rstrip("/") + "/") for f in self.out_files):
                    mapped = src_target
            if mapped is None:
                self.unlinked.append(f"{out_rel} -> {target}")
                return "\0UNLINK\0"
            new = rel(PurePosixPath(mapped), out_dir)
            if path.endswith("/") and not new.endswith("/"):
                new += "/"
            return f"{m.group(1)}{new}{sep}{anchor}{m.group(3)}"

        text = outside_fences(text, lambda t: LINK_RE.sub(fix, t))
        # Drop the link syntax but keep the label for targets that do not ship.
        text = re.sub(r"\[([^\]]*)\]\0UNLINK\0", r"\1", text)
        return text.replace("\0UNLINK\0", "")

    def wording_pass(self, text: str) -> str:
        out_lines = []
        in_fence = False
        for line in text.split("\n"):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                out_lines.append(line)
                continue
            if in_fence or "Claude Code" not in line:
                out_lines.append(line)
                continue
            parts = SENTENCE_SPLIT.split(line)
            seps = SENTENCE_SPLIT.findall(line)
            new_parts = []
            for part in parts:
                if "Claude Code" in part and not CC_FEATURE.search(part.replace("Claude Code", "")):
                    n = part.count("Claude Code")
                    part = re.sub(r"\b([Aa]) Claude Code\b", r"\1n agent", part)
                    part = re.sub(r"\b(an|An|another|Another|each|Each|any|Any|one|every|this|This|that|the|The)"
                                  r" Claude Code\b", r"\1 agent", part)
                    part = re.sub(r"(^|[.!?]\s+|\*\*|^\s*[-*]\s+)Claude Code's", r"\1The agent's", part)
                    part = re.sub(r"(^|[.!?]\s+|\*\*|^\s*[-*]\s+)Claude Code\b", r"\1The agent", part)
                    part = part.replace("Claude Code's", "the agent's").replace("Claude Code", "the agent")
                    self.wording += n
                new_parts.append(part)
            rebuilt = new_parts[0]
            for sep, part in zip(seps, new_parts[1:]):
                rebuilt += sep + part
            out_lines.append(rebuilt)
        return "\n".join(out_lines)


def apply_text_rewrites(out_rel: str, text: str, done: set[int]) -> str:
    for i, (path, old, new) in enumerate(CODEX_TEXT_REWRITES):
        if path == out_rel and old in text:
            text = text.replace(old, new)
            done.add(i)
    return text


def file_notes(text: str) -> list[str]:
    return [note for rx, note in CODEX_FILE_NOTES if rx.search(text)]


def detect_mappings(text: str) -> list[str]:
    return [mid for mid, rx, _ in MAPPINGS if re.search(rx, text)]


def codex_footer(ids: list[str], notes: set[str], skill_names: list[str], text: str,
                 lore_link: str, extra: list[str] | None = None) -> str:
    lines = ["", "## On Codex", "",
             f"Read the Claude Code features this skill names as follows on Codex and ChatGPT "
             f"(full table: [On Codex]({lore_link}#on-codex)).", ""]
    for mid, _, line in MAPPINGS:
        if mid in ids:
            lines.append(f"- {line}")
    if re.search(r"`/(?:magician:)?(" + "|".join(map(re.escape, skill_names)) + r")\b", text):
        lines.append("- Skill commands: `/<skill>` is `$<skill>` on Codex and `@<skill>` in ChatGPT.")
    if "paths" in notes:
        lines.append("- Paths such as `../../tools/kg` are relative to the folder of the file that names them; "
                     "resolve them to an absolute path before you run them.")
    if "data" in notes:
        lines.append("- Data folder: `$MAGICIAN_DATA`, else `~/.local/share/magician`.")
    for note in extra or []:
        note = note.removeprefix("On Codex: ")
        lines.append("- " + note[:1].upper() + note[1:])
    if len(lines) == 5:
        return ""
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ build
def is_exec(p: Path) -> bool:
    return bool(p.stat().st_mode & 0o111)


def walk(base: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and not d.startswith(".DS"))
        for f in sorted(filenames):
            if f.endswith((".pyc",)) or f in (".DS_Store", "Thumbs.db", "desktop.ini"):
                continue
            files.append(Path(dirpath) / f)
    return files


def readme_bits(readme: str) -> tuple[str, list[str]]:
    m = re.search(r"for the software lifecycle: ([^.]+)\.", readme)
    short = ("Skills for the software lifecycle: " + m.group(1) + ".") if m else \
        "Skills for the software lifecycle: research, design, planning, building, review and release."
    prompts = []
    ex = re.search(r"(?ms)^## Examples\s*$(.*?)^## ", readme)
    if ex:
        for block in re.findall(r"```text\n(.*?)```", ex.group(1), re.S):
            first = block.strip().splitlines()[0]
            mm = re.match(r"/([a-z-]+)\s+(.*)", first)
            if mm:
                prompts.append(f"${mm.group(1)} {mm.group(2)}")
    return short, prompts[:3]


def build(out: Path) -> dict:
    out = out.resolve()
    if out == ROOT or ROOT.is_relative_to(out):
        raise BuildError(f"refusing to build into {out}: it contains the source tree")
    if out.exists():
        if any(out.iterdir()) and not (out / OUTPUT_MARKER).is_file():
            raise BuildError(f"{out} exists, is not empty and holds no {OUTPUT_MARKER}; refusing to delete it")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    license_id = manifest.get("license", "MIT")

    skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")
                    if p.parent.name not in EXCLUDED_SKILLS)
    agents = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))
    clash = set(skills) & {a + "-lens" for a in agents}
    if clash:
        raise BuildError(f"lens skill names clash with skills: {sorted(clash)}")

    # Plan every output file first, so links can be checked against the final set.
    plan: list[tuple[str, str, str]] = []   # (kind, src rel, out rel)
    path_map: dict[str, str] = {}
    for s in skills:
        for f in walk(ROOT / "skills" / s):
            r = f.relative_to(ROOT).as_posix()
            plan.append(("skill", r, r))
    for a in agents:
        r = f"agents/{a}.md"
        o = f"skills/{a}-lens/SKILL.md"
        plan.append(("lens", r, o))
        path_map[r] = o
    for base in ("lore", "tools"):
        for f in walk(ROOT / base):
            r = f.relative_to(ROOT).as_posix()
            if base == "tools" and r.split("/")[1] in EXCLUDED_TOOLS:
                continue
            plan.append((base, r, r))
    out_files = {o for _, _, o in plan} | {"README.md", "LICENSE", "plugin.json"}
    for _, r, o in plan:
        path_map.setdefault(r, o)

    rw = Rewriter(path_map, out_files)
    lore_rel = "lore/skill-authoring.md"
    skill_texts: dict[str, list[str]] = {}
    skill_notes: dict[str, set[str]] = {}
    written: dict[str, tuple[bytes, int]] = {}

    rewrites_done: set[int] = set()

    def md_transform(src_rel: str, out_rel: str, text: str, skill_dir: str | None, wording: bool) -> str:
        text = apply_text_rewrites(out_rel, text, rewrites_done)
        text, notes = rw.variables(text, out_rel, skill_dir)
        text = rw.links(text, src_rel, out_rel)
        if wording:
            text = rw.wording_pass(text)
        if skill_dir:
            skill_notes.setdefault(skill_dir, set()).update(notes)
            skill_texts.setdefault(skill_dir, []).append(text)
        return text

    def with_notes(text: str) -> str:
        notes = file_notes(text)
        if not notes:
            return text
        return text.rstrip("\n") + "\n\n" + "\n".join("> " + n for n in notes) + "\n"

    pending_skill_md: dict[str, tuple[list, str, str]] = {}
    for kind, src_rel, out_rel in plan:
        src = ROOT / src_rel
        mode = 0o755 if is_exec(src) else 0o644
        if kind == "skill" and src_rel.endswith(".md"):
            skill_dir = "/".join(src_rel.split("/")[:2])
            text = src.read_text(encoding="utf-8")
            if src_rel.endswith("/SKILL.md"):
                fm_lines, body = split_frontmatter(text)
                body = md_transform(src_rel, out_rel, body, skill_dir, True)
                fm_text = "\n".join(fm_lines)
                fm_text, notes = rw.variables(fm_text, out_rel, skill_dir)
                skill_notes.setdefault(skill_dir, set()).update(notes)
                pending_skill_md[out_rel] = (parse_frontmatter(fm_text.split("\n")), body, skill_dir)
                continue
            written[out_rel] = (with_notes(md_transform(src_rel, out_rel, text, skill_dir, True)).encode("utf-8"), mode)
        elif kind == "lens":
            name = PurePosixPath(src_rel).stem
            skill_dir = f"skills/{name}-lens"
            fm_lines, body = split_frontmatter(src.read_text(encoding="utf-8"))
            pairs = parse_frontmatter(fm_lines)
            desc = str(dict(pairs).get("description", ""))
            rest = re.sub(r"^Use (to )?", "", desc)
            lens_desc = f"Use as a {name} review lens: {rest}"
            body = md_transform(src_rel, skill_dir + "/SKILL.md", body, skill_dir, True)
            converted = convert_frontmatter(pairs, name=f"{name}-lens", license_id=license_id,
                                            description=lens_desc,
                                            extra_meta={META_PREFIX + "agent": name})
            pending_skill_md[skill_dir + "/SKILL.md"] = (converted, body, skill_dir)
        elif kind == "lore" and src_rel.endswith(".md"):
            text = md_transform(src_rel, out_rel, src.read_text(encoding="utf-8"), None, False)
            written[out_rel] = (with_notes(text).encode("utf-8"), mode)
        elif kind == "tools" and PurePosixPath(src_rel).name in CONN_BLOCK and src_rel.count("/") == 1:
            text = src.read_text(encoding="utf-8")
            b, e = text.find(CONN_BEGIN), text.find(CONN_END)
            if b < 0 or e < 0:
                raise BuildError(f"{src_rel}: connection-config markers not found")
            text = text[:b] + CONN_BLOCK[PurePosixPath(src_rel).name] + text[e + len(CONN_END):]
            written[out_rel] = (text.encode("utf-8"), mode)
        else:
            written[out_rel] = (src.read_bytes(), mode)

    for out_rel, (pairs, body, skill_dir) in sorted(pending_skill_md.items()):
        name = skill_dir.split("/")[1]
        if not dict(pairs).get("license"):   # a source skill; lens pairs are converted already
            pairs = convert_frontmatter(pairs, name=name, license_id=license_id)
        text_all = body + "\n".join(skill_texts.get(skill_dir, []))
        here = PurePosixPath(out_rel).parent
        footer = codex_footer(detect_mappings(text_all), skill_notes.get(skill_dir, set()),
                              skills, text_all, rel(PurePosixPath(lore_rel), here), file_notes(body))
        content = render_frontmatter(pairs) + body.rstrip("\n") + "\n" + footer
        written[out_rel] = (content.encode("utf-8"), 0o644)

    missing = [CODEX_TEXT_REWRITES[i][0] for i in range(len(CODEX_TEXT_REWRITES)) if i not in rewrites_done]
    if missing:
        raise BuildError(f"Codex text rewrites found no source text in: {missing}")

    # plugin.json
    short, prompts = readme_bits(readme)
    desc = manifest["description"].replace(" in Claude Code", "").replace("Skills and agents", "Skills and review lenses")
    plugin = {
        "$schema": PLUGIN_SCHEMA,
        "name": manifest["name"],
        "version": manifest["version"],
        "description": desc,
        "author": manifest["author"],
        "homepage": manifest["homepage"],
        "repository": manifest["repository"],
        "license": license_id,
        "keywords": manifest.get("keywords", []),
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Magician",
                    "shortDescription": short,
                    "category": "Coding",
                    "capabilities": ["Interactive", "Read", "Write"],
                    "defaultPrompt": prompts,
                },
                "onboardingSkill": "./skills/almanac/SKILL.md",
            }
        },
    }
    written["plugin.json"] = ((json.dumps(plugin, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), 0o644)
    written["README.md"] = (codex_readme(manifest, skills, agents).encode("utf-8"), 0o644)
    written["LICENSE"] = ((ROOT / "LICENSE").read_bytes(), 0o644)

    for out_rel in sorted(written):
        data, mode = written[out_rel]
        dest = out / out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        os.chmod(dest, mode)

    # Only the keys OpenAI's "Package your plugin" guide shows in its marketplace.json example:
    # top level name, interface.displayName and plugins; per entry name, source, policy, category.
    market = {
        "name": manifest["name"],
        "interface": {"displayName": "Magician"},
        "plugins": [{
            "name": manifest["name"],
            "source": {"source": "local", "path": "./" + out.name},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Coding",
        }],
    }
    mdir = out.parent / ".agents" / "plugins"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "marketplace.json").write_text(json.dumps(market, indent=2) + "\n", encoding="utf-8")
    return {"files": len(written), "skills": len(skills), "lenses": len(agents),
            "unlinked": rw.unlinked, "wording": rw.wording}


def codex_readme(manifest: dict, skills: list[str], agents: list[str]) -> str:
    return f"""# Magician for Codex and ChatGPT

Generated from the magician {manifest['version']} source tree by `scripts/build-codex.sh`. Do not edit it here.

- {len(skills)} skills under `skills/`, and {len(agents)} review-lens skills (`*-lens`) made from the Claude Code agents.
- `lore/` holds the shared guidance the skills link to. `tools/` holds the command-line helpers (`kg`, `jira`,
  `confluence`, `ctx`, `plan-render`, ...). They need Python 3 and a shell.
- No hooks, monitors, output styles or plugin options, so no destructive guard: on Codex, rely on its
  sandbox and approval policy. Each skill ends with an "On Codex" section that maps the Claude Code
  features it names.
- Left out because they only work in Claude Code: the `statusline` skill and its `magician-statusline`
  and `magician-ui` tools (they drive Claude Code's status line and session-start settings). For
  STE-lite, create a `.magician/ste` file that holds `on`, or set `MAGICIAN_STE=1`.

## Jira and Confluence

Codex has no plugin options, so the `jira` and `confluence` helpers read their settings from the
environment Codex starts from:

| Variable | Value |
|---|---|
| `MAGICIAN_JIRA_BASE_URL` | `https://<site>.atlassian.net`, or your Jira Server/Data Center URL |
| `MAGICIAN_JIRA_EMAIL` | Jira Cloud only |
| `MAGICIAN_JIRA_API_TOKEN` | An API token (Cloud) or a personal access token (Server/Data Center) |
| `MAGICIAN_CONFLUENCE_BASE_URL` | `https://<site>.atlassian.net/wiki`, or your Confluence URL |
| `MAGICIAN_CONFLUENCE_EMAIL` | Confluence Cloud only |
| `MAGICIAN_CONFLUENCE_API_TOKEN` | An API token or a personal access token |

Keep tokens out of shell history and out of the repository.

## Install locally

```text
codex plugin marketplace add <folder that holds .agents/plugins/marketplace.json>
codex plugin add magician@magician
```

Start with `$almanac` in a project.
"""


# ------------------------------------------------------------------ validation
def _repo_reader():
    sys.path.insert(0, str(ROOT / "tests" / "claude"))
    try:
        from _frontmatter import read_frontmatter  # type: ignore
        return read_frontmatter
    except ImportError:
        return None
    finally:
        sys.path.pop(0)


def validate(out: Path) -> list[str]:
    out = out.resolve()
    problems: list[str] = []
    reader = _repo_reader()
    for d in DROPPED_DIRS:
        if (out / d).exists():
            problems.append(f"dropped folder present: {d}/")
    for rel_path in [f"skills/{s}" for s in EXCLUDED_SKILLS] + [f"tools/{t}" for t in EXCLUDED_TOOLS]:
        if (out / rel_path).exists():
            problems.append(f"Claude Code-only part present: {rel_path}")
    for jf in [out / "plugin.json", out.parent / ".agents" / "plugins" / "marketplace.json"]:
        try:
            json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"{jf.name}: {e}")
    for jf in sorted(out.rglob("*.json")):
        try:
            json.loads(jf.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{jf.relative_to(out)}: invalid JSON: {e}")
    for sk in sorted(out.glob("skills/*/SKILL.md")):
        relp = sk.relative_to(out).as_posix()
        try:
            if reader:
                fields, _ = reader(sk)
            else:
                fields = {k: v for k, v in parse_frontmatter(split_frontmatter(sk.read_text(encoding="utf-8"))[0])}
        except ValueError as e:
            problems.append(f"{relp}: {e}")
            continue
        extra = sorted(set(fields) - set(AAIF_KEYS))
        if extra:
            problems.append(f"{relp}: non-AAIF keys {extra}")
        if fields.get("name") != sk.parent.name:
            problems.append(f"{relp}: name {fields.get('name')!r} != folder {sk.parent.name!r}")
        desc = fields.get("description", "")
        if not desc or len(desc) > DESC_MAX:
            problems.append(f"{relp}: description length {len(desc)} (1..{DESC_MAX})")
        if len(fields.get("compatibility", "")) > COMPAT_MAX:
            problems.append(f"{relp}: compatibility over {COMPAT_MAX} chars")
        if "metadata" in fields:
            try:
                meta = json.loads(fields["metadata"])
                if not isinstance(meta, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                         for k, v in meta.items()):
                    raise ValueError("not a string-to-string map")
            except ValueError as e:
                problems.append(f"{relp}: metadata: {e}")
    for f in sorted(out.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relp = f.relative_to(out).as_posix()
        for var in (VAR_ROOT, VAR_SKILL):
            if var in text:
                problems.append(f"{relp}: unrewritten {var}")
        if f.suffix == ".md":
            for m in CLAUDE_VAR_RE.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{relp}:{line}: Claude Code variable {m.group(0)} in Codex output")
            if "unconditionally blocks" in text or re.search(r"magician ships a `PreToolUse", text):
                problems.append(f"{relp}: claims a hook this package does not ship")
        if f.suffix == ".md" and relp.startswith(("skills/", "lore/")):
            for m in LINK_RE.finditer(FENCE_RE.sub("", text)):
                target = m.group(2)
                if not is_file_link(target):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                resolved = (f.parent / path).resolve()
                if not resolved.exists():
                    problems.append(f"{relp}: broken link {target}")
                elif not resolved.is_relative_to(out):
                    problems.append(f"{relp}: link leaves the package: {target}")
    return problems


def codex_validate(out: Path) -> str:
    codex = shutil.which("codex")
    if not codex:
        return "codex CLI not found; `codex plugin validate` skipped"
    probe = subprocess.run([codex, "plugin", "validate", "--help"], capture_output=True, text=True)
    if probe.returncode != 0:
        return "this codex CLI has no `plugin validate` command; skipped"
    r = subprocess.run([codex, "plugin", "validate", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise BuildError("codex plugin validate failed:\n" + r.stdout + r.stderr)
    return "codex plugin validate: OK"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build the Codex/ChatGPT plugin package.")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output plugin folder (default dist/codex/magician)")
    ap.add_argument("--no-validate", action="store_true", help="skip the checks after the build")
    args = ap.parse_args(argv)
    out = Path(args.out)
    try:
        stats = build(out)
    except BuildError as e:
        print(f"build-codex: {e}", file=sys.stderr)
        return 1
    print(f"build-codex: {stats['files']} files in {out} ({stats['skills']} skills, "
          f"{stats['lenses']} lens skills); marketplace at {out.resolve().parent / '.agents/plugins/marketplace.json'}")
    print(f"build-codex: {stats['wording']} 'Claude Code' mentions made provider-neutral; "
          f"{len(stats['unlinked'])} links to files that do not ship were unlinked")
    for u in stats["unlinked"]:
        print(f"  unlinked: {u}")
    if args.no_validate:
        return 0
    problems = validate(out)
    for p in problems:
        print(f"build-codex: INVALID: {p}", file=sys.stderr)
    if problems:
        return 1
    try:
        print("build-codex: " + codex_validate(out))
    except BuildError as e:
        print(f"build-codex: {e}", file=sys.stderr)
        return 1
    print("build-codex: package valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Strict, dependency-free frontmatter reader plus the allowed-tools least-privilege policy.

Accepts only a conservative YAML subset whose meaning is identical in every YAML 1.1/1.2
parser (PyYAML, Psych, js-yaml, eemeli/yaml, Bun.YAML), so a file that passes here cannot
fail a stricter directory-validation parser. Anything outside the subset is an error, not a guess.

`tool_problems()` encodes the allowed-tools rules: no bare Bash/Edit/Write/WebFetch/WebSearch/
Monitor, no interpreter or package-launcher grants, no whole-CLI grants for multi-purpose CLIs,
file writes as `Edit(<path>)` (Write(path) rules are never consulted), and nothing that
pre-approves a change to Claude Code's own settings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SKILL_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
}
AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "color", "effort",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory",
    "background", "isolation", "initialPrompt",
}
BOOL_KEYS = {"disable-model-invocation", "user-invocable", "background"}
MAP_KEYS = {"metadata", "hooks", "mcpServers"}
LIST_OK_KEYS = {"allowed-tools", "disallowed-tools", "paths", "arguments", "skills", "tools",
                "disallowedTools"}
STR_KEYS = {"name", "description", "when_to_use", "argument-hint", "model", "effort",
            "context", "agent", "shell", "license", "compatibility", "color"}
# House rule: always a double-quoted string (hints are bracket-heavy; write an inner " as \").
MUST_DOUBLE_QUOTE = {"argument-hint"}
BLOCK_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}
KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?: (.*))?$")
# JSON-compatible escapes only, so json.loads() decodes exactly what every YAML parser does.
DQ_RE = re.compile(r'^"(?:[^"\\\x00-\x1f]|\\["\\/bfnrt]|\\u[0-9A-Fa-f]{4})*"$')
SQ_RE = re.compile(r"^'(?:[^']|'')*'$")
# Plain scalars that YAML 1.1 or 1.2 resolve to a non-string.
NON_STR_RE = re.compile(
    r"^(?:~|null|Null|NULL|true|True|TRUE|false|False|FALSE|yes|Yes|YES|no|No|NO|on|On|ON|"
    r"off|Off|OFF|y|Y|n|N|[-+]?(?:0|[1-9][0-9_]*)(?:\.[0-9_]*)?(?:[eE][-+]?[0-9]+)?|"
    r"0x[0-9A-Fa-f_]+|0o?[0-7_]+|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)|"
    r"\d{4}-\d\d?-\d\d?(?:[Tt ].*)?)$")
INDICATOR_START = set("[]{}#&*!|>'\"%@`,?:-")
BOM = "\ufeff"


class FrontmatterError(ValueError):
    pass


def _plain_scalar_problem(v: str) -> str | None:
    if "\t" in v:
        return "tab character"
    if v[0] in INDICATOR_START and not (v[0] in "-?:" and len(v) > 1 and v[1] not in " \t"):
        return f"plain scalar may not start with {v[0]!r} -- quote it"
    if ": " in v or v.endswith(":"):
        return "contains ': ' (mapping indicator) -- quote it or use a >- block"
    if " #" in v:
        return "contains ' #' (comment start) -- quote it"
    return None


def _scalar(key: str, v: str, where: str):
    if v.startswith('"'):
        if not DQ_RE.match(v):
            raise FrontmatterError(f"{where}: {key}: malformed double-quoted scalar")
        return json.loads(v), "dq"
    if v.startswith("'"):
        if not SQ_RE.match(v):
            raise FrontmatterError(f"{where}: {key}: malformed single-quoted scalar")
        return v[1:-1].replace("''", "'"), "sq"
    problem = _plain_scalar_problem(v)
    if problem:
        raise FrontmatterError(f"{where}: {key}: {problem}")
    if NON_STR_RE.match(v):
        if v in ("true", "false"):
            return v == "true", "plain"
        return v, "nonstr"
    return v, "plain"


def parse_strict(path: Path) -> tuple[dict, dict, str]:
    """Return (fields, styles, body). styles[key] in {plain, dq, sq, block, list, map, nonstr}."""
    text = path.read_text(encoding="utf-8")
    if text.startswith(BOM):
        raise FrontmatterError(f"{path}: BOM before frontmatter")
    lines = text.split("\n")
    if lines[0].rstrip("\r") != "---":
        raise FrontmatterError(f"{path}: first line must be exactly '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\r") == "---")
    except StopIteration:
        raise FrontmatterError(f"{path}: unterminated frontmatter") from None
    fm, body = lines[1:end], "\n".join(lines[end + 1:])
    fields: dict = {}
    styles: dict = {}
    i = 0
    while i < len(fm):
        ln, where = fm[i].rstrip("\r"), f"{path}:{i + 2}"
        i += 1
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if ln[0] in " \t":
            raise FrontmatterError(f"{where}: unexpected indented line (continuation of a plain "
                                   f"scalar?) -- use a >- block scalar")
        m = KEY_RE.match(ln)
        if not m:
            raise FrontmatterError(f"{where}: not a 'key: value' line")
        key, raw = m.group(1), (m.group(2) or "").strip()
        if key in fields:
            raise FrontmatterError(f"{where}: duplicate key {key!r}")
        if raw in BLOCK_INDICATORS:
            chunk = []
            while i < len(fm) and (not fm[i].strip() or fm[i][:1] == " "):
                chunk.append(fm[i].rstrip("\r")); i += 1
            if not any(c.strip() for c in chunk):
                raise FrontmatterError(f"{where}: {key}: empty block scalar")
            if any("\t" in c[: len(c) - len(c.lstrip())] for c in chunk):
                raise FrontmatterError(f"{where}: {key}: tab indentation")
            sep = " " if raw[0] == ">" else "\n"
            fields[key] = sep.join(c.strip() for c in chunk if c.strip())
            styles[key] = "block"
        elif raw == "":
            items, sub = [], {}
            while i < len(fm) and fm[i][:1] == " ":
                s = fm[i].strip(); i += 1
                if s.startswith("- "):
                    items.append(_scalar(key, s[2:].strip(), where)[0])
                else:
                    sub[s.split(":", 1)[0]] = s  # opaque nested map (hooks/metadata)
            if items and not sub:
                if key not in LIST_OK_KEYS:
                    raise FrontmatterError(f"{where}: {key}: must be a string, not a list")
                fields[key], styles[key] = items, "list"
            elif sub and not items:
                if key not in MAP_KEYS:
                    raise FrontmatterError(f"{where}: {key}: nested mapping not allowed")
                fields[key], styles[key] = sub, "map"
            else:
                raise FrontmatterError(f"{where}: {key}: empty value (null) -- give it a value")
        else:
            fields[key], styles[key] = _scalar(key, raw, where)
    return fields, styles, body


def schema_problems(path: Path, fields: dict, styles: dict, kind: str) -> list[str]:
    out, allowed = [], (SKILL_KEYS if kind == "skill" else AGENT_KEYS)
    for k in fields:
        if k not in allowed:
            out.append(f"{path}: unknown {kind} key {k!r}")
    for k in ("name", "description"):
        if k not in fields:
            out.append(f"{path}: missing {k!r}")
    for k, v in fields.items():
        st = styles[k]
        if k in STR_KEYS and (st in ("nonstr", "list", "map") or not isinstance(v, str)):
            out.append(f"{path}: {k!r} must be a single text value, got {st}")
        if k in BOOL_KEYS and v not in (True, False):
            out.append(f"{path}: {k!r} must be true or false")
        if k in MUST_DOUBLE_QUOTE and st != "dq":
            out.append(f"{path}: {k!r} must be a double-quoted string (house rule)")
    return out


# ---------------------------------------------------------------- allowed-tools policy
INTERPRETERS = r"(?:python[0-9.]*|node|nodejs|deno|bun|ruby|perl|php|bash|sh|zsh|dash|ksh|fish|pwsh|osascript|env|xargs|eval|exec|sudo|awk|gawk|lua|Rscript)"
LAUNCHERS = r"(?:npx|bunx|uvx|pnpx|pipx|pnpm dlx|yarn dlx|uv run|npm exec)"
WHOLE_CLI = {"gh", "glab", "git", "kg", "ctx", "jira", "confluence", "magician-ui", "docker",
             "kubectl", "npm", "yarn", "pnpm", "pip", "cargo", "go", "make", "curl", "wget",
             "claude", "open", "rm", "mv", "cp", "chmod", "tee"}
KNOWN = {"Read", "Edit", "Write", "NotebookEdit", "Bash", "Grep", "Glob", "Task", "Agent",
         "Workflow", "AskUserQuestion", "WebFetch", "WebSearch", "Monitor", "Skill",
         "TodoWrite", "LSP"}
BANNED_TOOLS = {"Monitor": "runs arbitrary commands in the background",
                "WebSearch": "unscoped network egress",
                "Write": "Write(path) rules are never consulted; use Edit(<path>)",
                "NotebookEdit": "use Edit(<path>) (covers all edit tools)"}
# Read-only commands Claude Code already auto-allows; granting them is noise.
REDUNDANT = {"ls", "cat", "echo", "pwd", "head", "tail", "grep", "find", "wc", "which", "diff",
             "stat", "du", "cd", "git status", "git log", "git diff", "git show"}
BROAD_EDIT = {"*", "**", "./**", "./*", "/**", "//**", "~/**", "~/.claude/**"}
SETTINGS_PATH = re.compile(r"(^|/)\.claude/(settings(\.local)?\.json|\*)")
# Commands that change Claude Code's own configuration/permissions: never pre-approve.
SETTINGS_CMDS = re.compile(r"^(claude (mcp|config|permissions)\b|magician-ui (allow|automode|enable|disable|set)\b)")


def split_tools(value) -> list[str]:
    """Split an allowed-tools value on commas/whitespace, never inside (...)."""
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    out, buf, depth = [], [], 0
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and (ch == "," or ch.isspace()):
            if "".join(buf).strip():
                out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def tool_problems(entry: str) -> list[str]:
    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_*-]*)(?:\((.*)\))?", entry)
    if not m:
        return [f"unparseable entry {entry!r}"]
    tool, arg = m.group(1), m.group(2)
    if tool.startswith("mcp__"):
        return ["wildcard MCP grant"] if tool.endswith("*") or tool.count("__") < 2 else []
    if tool not in KNOWN:
        return [f"unknown tool {tool!r}"]
    if tool in BANNED_TOOLS:
        return [f"{tool}: {BANNED_TOOLS[tool]}"]
    if tool == "Edit":
        if arg is None:
            return ["bare Edit (unscoped write) -- scope to Edit(./<dir>/**)"]
        if SETTINGS_PATH.search(arg):
            return [f"Edit({arg}) pre-approves writes to Claude Code settings"]
        if arg.strip() in BROAD_EDIT or arg.startswith("//"):
            return [f"Edit({arg}) is effectively unscoped"]
        if arg.startswith("/") or "${" in arg:
            return [f"Edit({arg}): use ./ (cwd) or ~/ anchors; /x is settings-relative and "
                    "${VARS} are not substituted in Edit rules"]
        return []
    if tool == "WebFetch":
        if arg is None or not arg.startswith("domain:") or arg in ("domain:*", "domain:*.*"):
            return ["WebFetch must be domain-scoped: WebFetch(domain:<host>)"]
        return []
    if tool == "Bash":
        if arg is None or arg.strip() in ("", "*", ":*"):
            return ["bare Bash (unbounded shell)"]
        cmd = re.sub(r"(?::\*|\s?\*)$", "", arg.strip()).strip()
        first = cmd.split()[0] if cmd.split() else ""
        probs = []
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", cmd):
            probs.append("env-assignment prefix (blocks rule matching; add a CLI flag instead)")
        if re.fullmatch(INTERPRETERS, first) or re.search(rf"(^|/){INTERPRETERS}$", first):
            probs.append(f"interpreter grant {first!r} (arbitrary code)")
        if re.match(rf"^{LAUNCHERS}\b", cmd):
            probs.append("package launcher (download-and-run)")
        if "*" in cmd:
            probs.append("wildcard before the end of the rule")
        if any(c in cmd for c in ";&|`$(<>") and not cmd.startswith("${CLAUDE_"):
            probs.append("shell metacharacter in rule")
        if cmd in WHOLE_CLI and arg.strip() != cmd:  # "gh *" / "gh:*"
            probs.append(f"whole-CLI grant for multi-purpose {cmd!r} -- name the subcommand")
        if first in ("rm", "chmod", "chown", "sudo", "dd", "mkfs"):
            probs.append(f"destructive command {first!r}")
        if cmd.startswith("${CLAUDE_") and "/scripts/" not in cmd and "/bin/" not in cmd:
            probs.append("plugin-path grant must name a specific script")
        if SETTINGS_CMDS.match(cmd):
            probs.append("pre-approves a command that changes Claude Code settings/permissions")
        if cmd in REDUNDANT:
            probs.append(f"redundant: {cmd!r} is auto-allowed read-only")
        return probs
    return []

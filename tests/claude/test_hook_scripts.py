"""Hook and monitor script contract: every script named in hooks/hooks.json or monitors/monitors.json.

Static half (reads the files): each script is plain bash 3.2 that `/bin/bash -n` accepts, sets
LC_ALL=C, runs no interpreter, inline program, eval, source, package launcher, install or network
fetcher, calls no other plugin file, never enables `set -e`/`-u`, always exits 0 (the destructive
guard alone may exit 2), never reads transcript fields, never writes Claude Code settings or the
session env file (only userconfig-env.sh and tools-path.sh write that), and prints additionalContext only inside
hookSpecificOutput with the event it is wired to. The scripts ported in 4.15 (pattern-detect,
chronicle-stop, format, notify, ci-watch) are also held to a literal token list. Launcher, install and
fetcher words are assembled from pieces so this file does not itself contain them.

Behaviour half: the scripts run for real under /bin/bash. External tools they may call (gofmt,
prettier, gh, sleep) are stub scripts on a temp PATH that record their argv (osascript and
notify-send are stubbed too, only to prove no hook runs them), so no real notification, formatter,
GitHub call or wait ever happens. Every run gets a fully
specified env built from temp dirs (HOME, CLAUDE_PLUGIN_DATA, MAGICIAN_HOME, MAGICIAN_SETTINGS,
CLAUDE_ENV_FILE): nothing is inherited from the parent process, so the real ~/.claude/settings.json and
~/.claude/magician are never read or touched.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks" / "hooks.json"
MONITORS = ROOT / "monitors" / "monitors.json"
SCRIPTS = ROOT / "scripts"
BASH = "/bin/bash" if os.path.exists("/bin/bash") else (shutil.which("bash") or "bash")
BUDGET = 9500

COMMAND_RE = re.compile(r'^"\$\{CLAUDE_PLUGIN_ROOT\}"/scripts/([a-z0-9-]+\.sh)$')

# Scripts ported to plain bash in 4.15: they carry no stack-detection data, so the literal list applies.
STRICT = ("pattern-detect.sh", "chronicle-stop.sh", "format.sh", "notify.sh", "ci-watch.sh")
GUARD = "destructive-guard.sh"          # the one hook allowed to exit 2 (it blocks the tool call)
ENV_WRITERS = ("userconfig-env.sh", "tools-path.sh")  # the hooks allowed to touch CLAUDE_ENV_FILE
TOOLS_LINKER = "tools-path.sh"  # names the plugin tools folder to write launchers; runs nothing from it
LINT_RUNNER = "ste-lint-hook.sh"  # the one hook that runs a bundled command: tools/ste-lint, by plugin root

# Steering phrases that must never appear in text a hook writes into Claude's context.
IMPERATIVE = re.compile(
    r"before doing any other work|\bdo not\b|\bdon't\b|\bmust\b|\bnever\b|\binvoke\b|AskUserQuestion"
    r"|\byou should\b|\balways\b|\bmake sure\b|\bIMPORTANT\b|\binstead of\b|\bavoid\b", re.I)

_GIT = shutil.which("git")
_PATH = ":".join(dict.fromkeys(
    ([str(Path(_GIT).parent)] if _GIT else []) + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]))


def _wired() -> dict:
    """script name -> set of hook events it is wired to ("monitor" for monitors.json)."""
    out: dict = {}
    hooks = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                m = COMMAND_RE.match(hook.get("command", ""))
                out.setdefault(m.group(1) if m else hook.get("command", ""), set()).add(event)
    for mon in json.loads(MONITORS.read_text(encoding="utf-8")):
        m = COMMAND_RE.match(mon.get("command", ""))
        out.setdefault(m.group(1) if m else mon.get("command", ""), set()).add("monitor")
    return out


WIRED = _wired()


# ---------- static checks ----------

def _code(text: str) -> str:
    """Script text without the shebang, full-line comments and trailing ` # ...` comments."""
    out = []
    for i, line in enumerate(text.splitlines()):
        if (i == 0 and line.startswith("#!")) or line.lstrip().startswith("#"):
            out.append("")
        else:
            out.append(re.sub(r"(^|\s)#(\s.*)?$", r"\1", line))
    return "\n".join(out)


def _j(*parts: str) -> str:
    return "".join(parts)


# A word in command position: line start, after ; & | ( { $( "! " or an unescaped backtick, or after
# a keyword that runs its argument; optionally after VAR=value assignments and a directory prefix.
_CMD = (r"(?:^|[;&|({]|(?<!\\)`|\$\(|!\s"
        r"|\b(?:then|do|else|elif|if|while|until|exec|nohup|env|time|xargs|sudo)\s)"
        r"\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(?:\S*/)?")
_END = r"(?=\s|;|$)"

INTERPRETERS = ("python[0-9.]*", "node", "nodejs", "perl", "ruby", "php", "lua", "deno", "bun", "awk",
                "gawk", "mawk", "nawk", "jq", "pwsh", "powershell", "tclsh", "expect", "Rscript", "osascript",
                "osacompile")
PLUGIN_CLIS = ("ctx", "kg", "jira", "confluence", "magician-ui", "magician-statusline", "magician-scan",
               "ste-lint", "gate.sh")
LAUNCHERS = (_j("n", "px"), _j("bun", "x"), _j("u", "vx"), _j("pnpm", r"\s+dlx"), _j("yarn", r"\s+dlx"),
             _j("pip", r"x\s+run"), _j("uv", r"\s+run"), _j("npm", r"\s+exec"), _j("go", r"\s+run"))
INSTALLS = tuple(_j(tool, r"\s+", verb) for tool, verb in (
    ("npm", "(?:install|i|ci)"), ("pnpm", "(?:install|add)"), ("yarn", "add"), ("bun", "(?:install|add)"),
    ("pip[0-9.]*", "install"), ("uv", "(?:pip|tool)"), ("brew", "install"), ("gem", "install"),
    ("cargo", "install"), ("go", "install"), ("apt(?:-get)?", "install")))
FETCHERS = (_j("cu", "rl"), _j("wg", "et"), _j("n", "c"), "ncat", "socat", "telnet", "ssh", "scp", "rsync",
            "ftp")

CODE_RULES = {   # name -> pattern (applied to comment-free code of every script)
    "interpreter": _CMD + "(?:" + "|".join(INTERPRETERS) + ")" + _END,
    "shell -c": _CMD + r"(?:bash|sh|zsh|ksh|dash|fish)\s+-[A-Za-z]*c" + _END,
    "eval": r"\beval\b",
    "source": _CMD + r"(?:source|\.)\s+\S",
    "set -e/-u": r"(?:^|[;&]|\b(?:then|do|else)\s)\s*set\s+(?:-[A-Za-z]*[eu][A-Za-z]*|-o\s+(?:errexit|nounset))\b",
    "other plugin file": r"(?<!#!)/bin/|PLUGIN_ROOT\}?\"?/(?:bin|scripts|tools)\b"
                         r"|dirname\s+\"?\$(?:0|\{?BASH_SOURCE)[^\n]*\.(?:py|js|cjs|mjs|ts|rb|pl|php|sh)\b"
                         r"|PLUGIN_ROOT[^\n]*\.(?:py|js|cjs|mjs|ts|rb|pl|php|sh)\b",
    "plugin CLI": _CMD + "(?:" + "|".join(re.escape(c) for c in PLUGIN_CLIS) + ")" + _END,
    "package launcher": r"\b(?:" + "|".join(LAUNCHERS) + r")\b",
    "package install": r"\b(?:" + "|".join(INSTALLS) + r")\b",
    "network fetcher": _CMD + "(?:" + "|".join(FETCHERS) + ")" + _END + r"|/dev/(?:tcp|udp)/",
    "bash 4+ syntax": r"\b(?:declare|local|typeset)\s+-[A-Za-z]*[AgnN]\b|\bmapfile\b|\breadarray\b|\bcoproc\b"
                      r"|\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?(?:,,?|\^\^?)[^}]*\}|&>>|\|&|;;&"
                      r"|\$\{[^}]*@[QEPAaKkUuL]\}|\bwait\s+-n\b|\$\{[A-Za-z_][A-Za-z0-9_]*:[^}:]*:\s*-[0-9]"
                      r"|%\([^)]*\)T|\bshopt\s+-s\s+(?:globstar|lastpipe|autocd|direxpand|checkjobs)"
                      r"|\[\[?\s+-v\s|\bEPOCH(?:SECONDS|REALTIME)\b|\bBASHPID\b",
    "GNU- or BSD-only utility": r"\bstat\b|\bshasum\b|\breadlink\s+-[A-Za-z]*f|\brealpath\b|\btac\b"
                                r"|\bgrep\s+-[A-Za-z]*P|\bsed\b[^|;\n]*\s-i\b|\bdate\b[^|;\n]*\s-[dr]\s"
                                r"|\bfind\b[^\n]*-printf|\bxargs\s+-[A-Za-z]*r|\bhead\s+-n\s*-[0-9]"
                                r"|\bsort\b[^|;\n]*\s-V\b|" + _CMD + "timeout" + _END,
    "exit without an explicit 0": r"(?:^|[;&|({]|\$\(|\b(?:then|do|else)\s)\s*exit"
                                  r"(?:\s*(?:$|;|&&|\|\||\}|\))|\s+[^0\s;)}&|]|\s+0[0-9])",
    "top-level additionalContext": r"\{\s*\\?\"additionalContext",
    "Claude Code settings write": r"(?:>|\btee\b|\bmv\b|\bcp\b|\bsed\s+-i)[^\n;|&]*settings(?:\.local)?\.json",
    "removed feature": r"patterns\.json|\bcapsule|\.resume\b|kg-?nudge|access-tracker|access-patterns"
                       r"|agent-lifecycle|worktree-init|mcp-?nudge|fingerprint|session-start-time"
                       r"|\bctx\s+(?:capsule|hook|resume)\b|\bgreet|statusLine",
    "imperative wording": r"(?i:\binvoke\b|before responding|before doing any other work|\bdo not\b"
                          r"|AskUserQuestion|auto-activat|let the user know|\byou must\b|\bIMPORTANT:)",
}
TEXT_RULES = {   # applied to the whole file (comments included)
    "transcript field": r"transcript_path|last_assistant_message|agent_transcript_path",
}
# The one documented exception: subagent-stop.sh reads the last 4 KiB of the finished agent's own
# transcript, named by the event, to find a STATUS: BLOCKED / DEGRADED / CLEAN line (README, PRIVACY.md).
TRANSCRIPT_READER = "subagent-stop.sh"
STRICT_TOKENS = (r"\bpython", r"\bnode\b", r"\bperl\b", r"\bruby\b", r"\bawk\b", r" -c ", r"\beval\b",
                 r"\bsource\s", r"(?m)^\s*\.\s", r"\bjq\b", r"/bin/", r"PLUGIN_ROOT", r"transcript_path",
                 r"last_assistant_message", r"settings\.json", r"CLAUDE_ENV_FILE", r"\binscribe\b",
                 r"\bInvoke\b")


_BT = "\x60"                         # a backtick, kept out of this file's own text
_INDIRECT = "$" + "{" + "!"          # indirect-expansion opener, built from parts for the same reason
_SPAN = re.compile(_BT + "([^" + _BT + "\n]*)" + _BT)
_LEAD = re.compile(r"^[\s({!]*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")
# Quoted text is read left to right, so a plain single- or double-quoted string (one ending in $
# included) is taken whole and only a real ANSI-C string reaches the check below.
_ANSI_C = re.compile(r"\$'((?:[^'\\]|\\.)*)'|'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\.")


def _computed_program_sites(text: str) -> list:
    """Text the plugin directory reads as a command whose program is computed at run time. Its
    launcher scan parses inline-code spans as commands even inside comments, so a span may not hold
    a command substitution or indirect expansion, nor start with an expansion (the plugin-root
    variable excepted, which the directory accepts). A comment may not carry indirect-expansion
    text, and an ANSI-C string may not hold an escaped quote or a backtick (a plain quote scanner
    loses its place there)."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in _SPAN.finditer(re.sub(r"\\.", "  ", line)):
            span, head = m.group(1), _LEAD.sub("", m.group(1))
            if ("$(" in span or _INDIRECT in span
                    or (head.startswith(("$", '"$')) and not head.lstrip('"').startswith("${CLAUDE_PLUGIN_ROOT}"))):
                found.append((n, m.group(0)))
        comment = line if line.lstrip().startswith("#") else ""
        if not comment:
            tail = re.search(r"(?:^|\s)(#\s.*)$", line)
            comment = tail.group(1) if tail else ""
        if _INDIRECT in comment:
            found.append((n, line.strip()))
    code = _code(text)
    for m in _ANSI_C.finditer(code):
        if m.group(0).startswith("$'") and ("\\'" in m.group(1) or _BT in m.group(1)):
            found.append((code[:m.start()].count("\n") + 1, m.group(0)))
    return found


class StaticScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.texts = {}
        for name in WIRED:
            path = SCRIPTS / name
            cls.texts[name] = path.read_text(encoding="utf-8") if path.is_file() else ""

    def test_every_wired_command_is_a_bundled_script(self) -> None:
        self.assertIn("ci-watch.sh", WIRED)
        for name in WIRED:
            with self.subTest(script=name):
                self.assertRegex(name, r"^[a-z0-9-]+\.sh$", "command is not the quoted literal script form")
                path = SCRIPTS / name
                self.assertTrue(path.is_file(), f"missing scripts/{name}")
                self.assertTrue(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
                                f"scripts/{name} is not executable")

    def test_shebang_syntax_and_locale(self) -> None:
        for name, text in self.texts.items():
            with self.subTest(script=name):
                self.assertTrue(text.startswith("#!/usr/bin/env bash\n"), "shebang must be #!/usr/bin/env bash")
                proc = subprocess.run([BASH, "-n", str(SCRIPTS / name)], capture_output=True, text=True,
                                      env={"PATH": _PATH, "LANG": "C"}, timeout=60, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertRegex(_code(text), r"(?m)^\s*(?:export\s+)?LC_ALL=C\b")

    def test_code_rules(self) -> None:
        for name, text in self.texts.items():
            code = _code(text)
            for rule, pattern in CODE_RULES.items():
                if rule == "exit without an explicit 0" and name == GUARD:
                    pattern = pattern.replace(r"[^0\s;)}&|]", r"[^02\s;)}&|]")
                if rule == "other plugin file" and name == TOOLS_LINKER:
                    pattern = pattern.replace("(?:bin|scripts|tools)", "(?:bin|scripts)")
                with self.subTest(script=name, rule=rule):
                    m = re.search(pattern, code, re.M)
                    self.assertIsNone(m, f"{rule}: {m.group(0)!r}" if m else "")
            for rule, pattern in TEXT_RULES.items():
                if rule == "transcript field" and name == TRANSCRIPT_READER:
                    continue
                with self.subTest(script=name, rule=rule):
                    self.assertIsNone(re.search(pattern, text), rule)

    def test_scripts_end_with_exit_0(self) -> None:
        for name, text in self.texts.items():
            with self.subTest(script=name):
                lines = [ln.strip() for ln in _code(text).splitlines() if ln.strip()]
                self.assertEqual(lines[-1] if lines else "", "exit 0")

    def test_only_the_env_writers_name_the_session_env_file(self) -> None:
        for name, text in self.texts.items():
            with self.subTest(script=name):
                if name in ENV_WRITERS:
                    self.assertIn("CLAUDE_ENV_FILE", text)
                else:
                    self.assertNotIn("CLAUDE_ENV_FILE", _code(text))

    def test_hook_event_names_match_the_wiring(self) -> None:
        for name, text in self.texts.items():
            code = _code(text)
            with self.subTest(script=name):
                used = set(re.findall(r'\\?"hookEventName\\?"\s*:\s*\\?"([A-Za-z]+)', code))
                self.assertLessEqual(used, WIRED[name] - {"monitor"})
                if "additionalContext" in code:
                    self.assertIn("hookSpecificOutput", code)
                if "monitor" in WIRED[name]:
                    self.assertNotIn("hookSpecificOutput", code)

    def test_ported_scripts_have_none_of_the_literal_tokens(self) -> None:
        for name in STRICT:
            text = "\n".join(self.texts.get(name, "").splitlines()[1:])
            for token in STRICT_TOKENS:
                with self.subTest(script=name, token=token):
                    m = re.search(token, text)
                    self.assertIsNone(m, f"{token}: {m.group(0)!r}" if m else "")

    def test_no_text_reads_as_a_computed_program(self) -> None:
        """Every script under scripts/, comments included (see _computed_program_sites)."""
        for path in sorted(SCRIPTS.glob("*.sh")):
            with self.subTest(script=path.name):
                self.assertEqual(_computed_program_sites(path.read_text(encoding="utf-8")), [])

    def test_computed_program_scan_flags_samples(self) -> None:
        """Self-check for the scan above; samples are assembled so this file holds none of them."""
        d, b = "$", _BT
        caught = ("# so " + b + d + "(sudo (tool ...))" + b + " is seen",
                  "# needed so " + b + "ev" + "al \"" + d + "(fetcher ...)\"" + b + " stays visible",
                  "# " + b + _INDIRECT + "prefix*}" + b + " reads by prefix",
                  "# a real " + _INDIRECT + "...} is caught",
                  "# " + b + d + "CMD --flag" + b + " runs it",
                  "X=" + d + "'a\\'b'", "X=" + d + "'a" + b + "b'",
                  "re='^x" + d + "'\nX=" + d + "'a\\'b'")
        missed = ("# " + b + "sudo -u root" + b + " resolves", "# " + b + "-rf \"" + d + "HOME\"" + b,
                  "# " + b + d + "{CLAUDE_PLUGIN_ROOT}/bin/x" + b + " is named", "X=" + d + "'a\\x27b'",
                  "echo \"\\" + b + "kg query\\" + b + "\"", "[ \"" + _INDIRECT + "v-}\" = x ]",
                  "re='^x" + d + "'\nM=\"\\" + b + "k\\" + b + "\"\ny='z'")
        for s in caught:
            self.assertTrue(_computed_program_sites(s), s)
        for s in missed:
            self.assertFalse(_computed_program_sites(s), s)

    def test_only_the_lint_hook_names_the_bundled_linter(self) -> None:
        """ste-lint-hook.sh runs tools/ste-lint by the plugin root (the one bundled command a hook
        runs, read-only, on the file the event names); no other hook names it or the tools folder,
        and the runner names nothing else in it."""
        for name, text in self.texts.items():
            code = _code(text)
            with self.subTest(script=name):
                if name == LINT_RUNNER:
                    self.assertEqual(code.count("/tools/ste-lint"), 1)
                    self.assertRegex(code, r'LINT="\$\{CLAUDE_PLUGIN_ROOT:-[^\n]*\}/tools/ste-lint"')
                    self.assertIn('[ -x "$LINT" ] || exit 0', code)
                    self.assertIn('"$LINT" --max 10 "$F"', code)
                elif name != TOOLS_LINKER:
                    self.assertNotIn("/tools/", code)
                    self.assertNotIn("ste-lint", code)

    def test_ci_watch_reads_only_the_run_number(self) -> None:
        text = self.texts["ci-watch.sh"]
        for token in ("displayTitle", "headBranch", "--jq", "--template"):
            with self.subTest(token=token):
                self.assertNotIn(token, _code(text))
        self.assertEqual(re.findall(r"--json\s+(\S+)", text), ["databaseId"])
        self.assertIn('--branch "$BRANCH"', text)
        self.assertRegex(text, r"(?m)^POLLS=120$")
        self.assertRegex(text, r"(?m)^\s*sleep 90$")


# ---------- behaviour ----------

def _tree(root: Path) -> dict:
    """path -> (size, mtime_ns) for every file under root (a snapshot to diff)."""
    snap = {}
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                st = p.stat()
                snap[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return snap


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(root.rglob("*")) if p.is_file())


class Sandbox:
    """Temp HOME / plugin data / magician home / settings / env-file paths, a stub dir and a work dir."""

    def __init__(self, tmp: str) -> None:
        self.base = Path(os.path.realpath(tmp))
        self.home = self.base / "home"
        self.data = self.base / "data"
        self.mag = self.base / "maghome"
        self.stubs = self.base / "stubs"
        self.work = self.base / "work"
        self.settings = self.home / ".claude" / "settings.json"
        self.envfile = self.base / "session.env"
        for d in (self.home, self.data, self.mag, self.stubs, self.work):
            d.mkdir(parents=True)

    def env(self, path: str | None = None, **extra: str) -> dict:
        env = {
            "PATH": path if path is not None else f"{self.stubs}:{_PATH}",
            "HOME": str(self.home), "LANG": "C", "TMPDIR": str(self.base),
            "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PLUGIN_DATA": str(self.data),
            "MAGICIAN_HOME": str(self.mag), "MAGICIAN_SETTINGS": str(self.settings),
            "CLAUDE_ENV_FILE": str(self.envfile),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CEILING_DIRECTORIES": str(self.base.parent),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        env.update(extra)
        return env

    def stub(self, name: str, body: str = "") -> Path:
        """A /bin/sh stub that records each call's argv (unit-separated, one record per call)."""
        log = self.base / f"{name}.calls"
        p = self.stubs / name
        p.write_text(f"#!/bin/sh\nprintf '%s\\037' \"$@\" >> {shlex.quote(str(log))}\n"
                     f"printf '\\036' >> {shlex.quote(str(log))}\n{body}\nexit 0\n", encoding="utf-8")
        p.chmod(0o755)
        return p

    def calls(self, name: str) -> list:
        log = self.base / f"{name}.calls"
        if not log.exists():
            return []
        return [rec.split("\x1f")[:-1] for rec in log.read_text(encoding="utf-8").split("\x1e")[:-1]]

    def run(self, script: str, payload: str | dict = "", cwd: Path | None = None, path: str | None = None,
            **extra: str) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return subprocess.run([BASH, str(SCRIPTS / script)], input=stdin, encoding="utf-8", errors="replace",
                              capture_output=True, cwd=str(cwd or self.work), env=self.env(path, **extra),
                              timeout=120, check=False)

    def git(self, cwd: Path, *args: str) -> None:
        subprocess.run([_GIT, "-c", "commit.gpgsign=false", *args], cwd=str(cwd), env=self.env(),
                       check=True, capture_output=True, timeout=60)

    def repo(self, name: str, branch: str = "work") -> Path:
        p = self.base / name
        p.mkdir()
        self.git(p, "init", "-q", ".")
        self.git(p, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
        return p

    def snapshot(self) -> tuple:
        return _tree(self.home), _tree(self.data), _tree(self.mag)


class _SandboxCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.sb = Sandbox(self._tmp.name)

    def tearDown(self) -> None:
        self.assertFalse(self.sb.settings.exists(), "a hook created the settings file")
        self._tmp.cleanup()


OPTIONS_ON = {"CLAUDE_PLUGIN_OPTION_AUTO_FORMAT": "true", "CLAUDE_PLUGIN_OPTION_AUTO_FORMAT_PRETTIER": "true",
              "CLAUDE_PLUGIN_OPTION_DESKTOP_NOTIFICATIONS": "true", "CLAUDE_PLUGIN_OPTION_SESSION_HISTORY": "true"}


class AllScriptsTests(_SandboxCase):
    def test_every_script_exits_0_on_empty_and_malformed_input(self) -> None:
        for name in ("osascript", "notify-send", "gh", "sleep", "gofmt", "prettier"):
            self.sb.stub(name)
        for name in sorted(WIRED):
            for payload in ("", "not json", "{}"):
                for options in ({}, OPTIONS_ON):
                    with self.subTest(script=name, payload=payload, options=bool(options)):
                        proc = self.sb.run(name, payload, **options)
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        out = proc.stdout.strip()
                        if out and "monitor" not in WIRED[name]:
                            doc = json.loads(out)
                            ctx = doc.get("hookSpecificOutput", {}).get("additionalContext", "")
                            self.assertLessEqual(len(ctx), BUDGET)
                        if name not in ENV_WRITERS:
                            self.assertFalse(self.sb.envfile.exists(), f"{name} wrote CLAUDE_ENV_FILE")
        for name in ("osascript", "notify-send", "gh", "gofmt", "prettier"):
            self.assertEqual(self.sb.calls(name), [], f"{name} ran on empty input")


class ChronicleTests(_SandboxCase):
    SCRIPT = "chronicle-stop.sh"

    def _records(self) -> list:
        return sorted((self.sb.data / "chronicle").glob("*Z-*.json"))

    def test_one_record_per_session_with_git_fields(self) -> None:
        repo = self.sb.repo("proj")
        (repo / "a.txt").write_text("one\n", encoding="utf-8")
        self.sb.git(repo, "add", "a.txt")
        self.sb.git(repo, "commit", "-q", "-m", "Add a")
        (self.sb.data / "sessions").mkdir()
        (self.sb.data / "sessions" / "sess-1.start").write_text("2000-01-01T00:00:00Z\n", encoding="utf-8")
        (repo / "a.txt").write_text("two\n", encoding="utf-8")
        payload = {"session_id": "sess-1", "cwd": str(repo), "hook_event_name": "Stop"}
        for _ in range(2):
            self.assertEqual(self.sb.run(self.SCRIPT, payload).returncode, 0)
        recs = self._records()
        self.assertEqual([p.name for p in recs], ["20000101T000000Z-sess-1.json"])
        doc = json.loads(recs[0].read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"timestamp", "session_id", "session_start", "working_dir", "branch",
                                    "commits", "changed_files", "summary"})
        self.assertEqual(doc["session_id"], "sess-1")
        self.assertEqual(doc["session_start"], "2000-01-01T00:00:00Z")
        self.assertEqual(doc["working_dir"], str(repo))
        self.assertEqual(doc["branch"], "work")
        self.assertEqual(doc["commits"], 1)
        self.assertEqual(doc["changed_files"], ["a.txt"])
        self.assertEqual(doc["summary"], "1 commit(s) on work")

    def test_missing_start_stamp_is_created_and_reused(self) -> None:
        payload = {"session_id": "fresh", "cwd": str(self.sb.work)}
        self.sb.run(self.SCRIPT, payload)
        start = (self.sb.data / "sessions" / "fresh.start").read_text(encoding="utf-8").strip()
        self.assertRegex(start, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.sb.run(self.SCRIPT, payload)
        self.assertEqual(len(self._records()), 1)
        doc = json.loads(self._records()[0].read_text(encoding="utf-8"))
        self.assertEqual((doc["branch"], doc["commits"], doc["changed_files"]), ("no-git", 0, []))

    def test_keeps_the_newest_50_and_leaves_legacy_files(self) -> None:
        chron = self.sb.data / "chronicle"
        chron.mkdir()
        day0 = datetime.datetime(2020, 1, 1)
        seeds = []
        for i in range(60):
            name = f"{day0 + datetime.timedelta(days=i):%Y%m%dT%H%M%S}Z-seed{i:02d}.json"
            (chron / name).write_text("{}\n", encoding="utf-8")
            seeds.append(name)
        for legacy in ("2026-01-01-10-00.json", "notes.txt"):
            (chron / legacy).write_text("{}\n", encoding="utf-8")
        self.sb.run(self.SCRIPT, {"session_id": "prune", "cwd": str(self.sb.work)})
        names = {p.name for p in self._records()}
        self.assertEqual(len(names), 50)
        self.assertTrue(any(n.endswith("Z-prune.json") for n in names))
        self.assertEqual(names - {n for n in names if n.endswith("Z-prune.json")}, set(seeds[11:]))
        self.assertTrue((chron / "2026-01-01-10-00.json").exists())
        self.assertTrue((chron / "notes.txt").exists())

    def test_off_switch_writes_nothing(self) -> None:
        for value in ("false", "0", "off"):
            with self.subTest(value=value):
                proc = self.sb.run(self.SCRIPT, {"session_id": "s", "cwd": str(self.sb.work)},
                                   CLAUDE_PLUGIN_OPTION_SESSION_HISTORY=value)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(_tree(self.sb.data), {})

    def test_never_reads_transcript_or_reply(self) -> None:
        transcript = self.sb.base / "t.jsonl"
        transcript.write_text('{"message":"TRANSCRIPT-MARKER-7"}\n', encoding="utf-8")
        repo = self.sb.repo("proj")
        self.sb.git(repo, "commit", "-q", "--allow-empty", "-m", "Decided on plain files")
        (self.sb.data / "sessions").mkdir()
        (self.sb.data / "sessions" / "m.start").write_text("2000-01-01T00:00:00Z\n", encoding="utf-8")
        self.sb.run(self.SCRIPT, {"session_id": "m", "cwd": str(repo), "transcript_path": str(transcript),
                                  "last_assistant_message": "REPLY-MARKER-9"})
        written = _all_text(self.sb.data)
        self.assertIn("Decided on plain files", written)
        self.assertNotIn("TRANSCRIPT-MARKER-7", written)
        self.assertNotIn("REPLY-MARKER-9", written)

    def test_decision_commits_become_project_learnings_once(self) -> None:
        repo = self.sb.repo("proj")
        long_subject = "Decided to keep: " + "\u00e9" * 150   # odd prefix: the 240-byte cut splits a character
        for msg in ("Switched to plain bash helpers", "undecided on names", "Fix typo", long_subject):
            self.sb.git(repo, "commit", "-q", "--allow-empty", "-m", msg)
        (self.sb.data / "sessions").mkdir()
        (self.sb.data / "sessions" / "l.start").write_text("2000-01-01T00:00:00Z\n", encoding="utf-8")
        payload = {"session_id": "l", "cwd": str(repo)}
        self.sb.run(self.SCRIPT, payload)
        self.sb.run(self.SCRIPT, payload)
        key = hashlib.md5(str(repo).encode()).hexdigest()[:12]
        raw = (self.sb.data / "projects" / key / "learnings.jsonl").read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]   # strict UTF-8
        facts = sorted(r["fact"] for r in rows)
        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[1], "Switched to plain bash helpers")
        self.assertTrue(facts[0].startswith("Decided to keep: \u00e9"))
        self.assertLessEqual(len(facts[0].encode("utf-8")), 240)
        self.assertTrue(all(r["source"] == "git" and isinstance(r["ts"], int) for r in rows))

    def test_learnings_are_written_without_sbin_on_path(self) -> None:
        # macOS ships md5 only as /sbin/md5; hooks can run with PATH=/usr/bin:/bin.
        repo = self.sb.repo("proj")
        self.sb.git(repo, "commit", "-q", "--allow-empty", "-m", "Going with plain JSONL for notes")
        (self.sb.data / "sessions").mkdir()
        (self.sb.data / "sessions" / "p.start").write_text("2000-01-01T00:00:00Z\n", encoding="utf-8")
        path = ":".join(dict.fromkeys(([str(Path(_GIT).parent)] if _GIT else []) + ["/usr/bin", "/bin"]))
        self.sb.run(self.SCRIPT, {"session_id": "p", "cwd": str(repo)}, path=path)
        key = hashlib.md5(str(repo).encode()).hexdigest()[:12]
        rows = (self.sb.data / "projects" / key / "learnings.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(r)["fact"] for r in rows], ["Going with plain JSONL for notes"])

    def test_unsafe_session_id_is_ignored(self) -> None:
        self.sb.run(self.SCRIPT, {"session_id": "../../x", "cwd": str(self.sb.work)})
        self.assertEqual(_tree(self.sb.data), {})


class FormatTests(_SandboxCase):
    SCRIPT = "format.sh"
    ON = {"CLAUDE_PLUGIN_OPTION_AUTO_FORMAT": "true"}

    def setUp(self) -> None:
        super().setUp()
        self.sb.stub("gofmt", "[ \"$1\" = \"-w\" ] && printf 'package main\\n' > \"$2\"")
        self.sb.stub("prettier", "for a in \"$@\"; do f=$a; done\nprintf 'x\\n' >> \"$f\"")
        self.go = self.sb.work / "main.go"
        self.go.write_text("package  main\n\n\n", encoding="utf-8")

    def _payload(self, path: str, **extra) -> dict:
        return {"hook_event_name": "PostToolUse", "tool_name": "Write",
                "tool_input": {**extra, "file_path": path}}

    def test_off_by_default(self) -> None:
        proc = self.sb.run(self.SCRIPT, self._payload(str(self.go)))
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertEqual(self.sb.calls("gofmt"), [])
        self.assertEqual(self.go.read_text(encoding="utf-8"), "package  main\n\n\n")

    def test_reformat_is_reported_to_claude(self) -> None:
        before = self.sb.snapshot()
        proc = self.sb.run(self.SCRIPT, self._payload(str(self.go)), **self.ON)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"hookSpecificOutput"})
        self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        ctx = doc["hookSpecificOutput"]["additionalContext"]
        self.assertIn("gofmt", ctx)
        self.assertIn(str(self.go), ctx)
        self.assertIsNone(IMPERATIVE.search(ctx), ctx)
        self.assertEqual(self.sb.calls("gofmt"), [["-w", str(self.go)]])
        self.assertEqual(self.go.read_text(encoding="utf-8"), "package main\n")
        again = self.sb.run(self.SCRIPT, self._payload(str(self.go)), **self.ON)
        self.assertEqual(again.stdout, "")                      # formatted under 2 s ago: skipped
        self.assertEqual(len(self.sb.calls("gofmt")), 1)
        stamps = list((self.sb.data / "format-stamps").iterdir())
        self.assertEqual(len(stamps), 1, "one stamp per file path, under the plugin data folder")
        self.assertRegex(stamps[0].read_text(encoding="utf-8"), r"^[0-9]+\n$")
        self.assertEqual(_tree(self.sb.home), before[0])        # nothing stored outside the data folder
        self.assertEqual(_tree(self.sb.mag), before[2])
        stamps[0].write_text("1000000000\n", encoding="utf-8")  # the stamp is old: format again
        third = self.sb.run(self.SCRIPT, self._payload(str(self.go)), **self.ON)
        self.assertEqual(third.stdout, "")                      # already formatted: nothing to report
        self.assertEqual(len(self.sb.calls("gofmt")), 2)
        stamps[0].write_text("junk\n", encoding="utf-8")        # an unreadable stamp counts as old
        self.sb.run(self.SCRIPT, self._payload(str(self.go)), **self.ON)
        self.assertEqual(len(self.sb.calls("gofmt")), 3)

    def test_prettier_needs_its_own_option(self) -> None:
        md = self.sb.work / "notes.md"
        md.write_text("# t\n", encoding="utf-8")
        self.assertEqual(self.sb.run(self.SCRIPT, self._payload(str(md)), **self.ON).stdout, "")
        self.assertEqual(self.sb.calls("prettier"), [])
        proc = self.sb.run(self.SCRIPT, self._payload(str(md)), CLAUDE_PLUGIN_OPTION_AUTO_FORMAT_PRETTIER="true",
                           **self.ON)
        self.assertIn("prettier", json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.sb.calls("prettier"), [["--write", "--log-level", "silent", str(md)]])

    def test_only_existing_absolute_paths_and_never_a_decoy(self) -> None:
        txt = self.sb.work / "plain.txt"
        txt.write_text("x\n", encoding="utf-8")
        decoy = json.dumps({"file_path": str(self.go)})
        for payload in (self._payload("main.go"), self._payload(str(self.sb.work / "missing.go")),
                        self._payload(str(txt), content=decoy)):
            with self.subTest(payload=payload):
                proc = self.sb.run(self.SCRIPT, payload, **self.ON)
                self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertEqual(self.sb.calls("gofmt"), [])


class NotifyTests(_SandboxCase):
    SCRIPT = "notify.sh"
    ON = {"CLAUDE_PLUGIN_OPTION_DESKTOP_NOTIFICATIONS": "true"}

    def setUp(self) -> None:
        super().setUp()
        for name in ("osascript", "notify-send", "uname"):
            self.sb.stub(name)

    def _event(self, kind: str = "agent_completed", message: str = "Background run finished") -> dict:
        return {"hook_event_name": "Notification", "notification_type": kind, "message": message,
                "session_id": "n1"}

    def _seq(self, proc: subprocess.CompletedProcess) -> str:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"terminalSequence"})
        return doc["terminalSequence"]

    def test_off_by_default(self) -> None:
        proc = self.sb.run(self.SCRIPT, self._event(), TERM_PROGRAM="Apple_Terminal")
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertEqual(self.sb.calls("osascript"), [])

    def test_terminal_app_runs_no_applescript(self) -> None:
        """Hook scripts run no second language, so Terminal.app gets the OSC 777 fallback (which it ignores)."""
        before = self.sb.snapshot()
        hostile = 'done" & (do shell script "id") & "'
        seq = self._seq(self.sb.run(self.SCRIPT, self._event(message=hostile), TERM_PROGRAM="Apple_Terminal",
                                    **self.ON))
        self.assertEqual(seq, "\x1b]777;notify;Magician;" + hostile + "\x07")
        self.assertEqual((self.sb.calls("osascript"), self.sb.calls("notify-send")), ([], []))
        self.assertEqual(self.sb.snapshot(), before)

    def test_osc_777_strips_embedded_escape_sequences(self) -> None:
        msg = 'done "quoted" C:\\dir \x1b]52;c;SGVsbG8=\x07 ok\nnext'
        seq = self._seq(self.sb.run(self.SCRIPT, self._event(message=msg), TERM_PROGRAM="ghostty", **self.ON))
        self.assertTrue(seq.startswith("\x1b]777;notify;Magician;"), repr(seq))
        self.assertTrue(seq.endswith("\x07"), repr(seq))
        self.assertIsNone(re.search(r"[\x00-\x1f\x7f]", seq[1:-1]), repr(seq))
        self.assertEqual(seq[len("\x1b]777;notify;Magician;"):-1], 'done "quoted" C:\\dir  ]52;c;SGVsbG8=  ok next')
        self.assertEqual((self.sb.calls("osascript"), self.sb.calls("notify-send")), ([], []))

    def test_osc_9_and_99_terminals(self) -> None:
        cases = ({"TERM_PROGRAM": "iTerm.app"}, {"TERM_PROGRAM": "WezTerm"}, {"WT_SESSION": "1"})
        for extra in cases:
            with self.subTest(**extra):
                seq = self._seq(self.sb.run(self.SCRIPT, self._event(), **extra, **self.ON))
                self.assertEqual(seq, "\x1b]9;Magician: Background run finished\x07")
        seq = self._seq(self.sb.run(self.SCRIPT, self._event(), KITTY_WINDOW_ID="3", **self.ON))
        self.assertEqual(seq, "\x1b]99;;Magician: Background run finished\x1b\\")

    def test_every_other_terminal_gets_osc_777_and_no_program_runs(self) -> None:
        """Linux included: the hook runs no desktop notifier, so the scan of hook scripts has nothing
        further to follow."""
        seq = self._seq(self.sb.run(self.SCRIPT, self._event("agent_needs_input", "Waiting on you"),
                                    TERM_PROGRAM="gnome-terminal", **self.ON))
        self.assertEqual(seq, "\x1b]777;notify;Magician;Waiting on you\x07")
        seq = self._seq(self.sb.run(self.SCRIPT, self._event(), **self.ON))
        self.assertEqual(seq, "\x1b]777;notify;Magician;Background run finished\x07")
        for name in ("osascript", "notify-send", "uname"):
            self.assertEqual(self.sb.calls(name), [], f"notify.sh ran {name}")

    def test_plugin_notification_is_shown(self) -> None:
        seq = self._seq(self.sb.run(self.SCRIPT, self._event("plugin_notification", "Index refreshed"),
                                    TERM_PROGRAM="ghostty", **self.ON))
        self.assertEqual(seq, "\x1b]777;notify;Magician;Index refreshed\x07")
        seq = self._seq(self.sb.run(self.SCRIPT, self._event("plugin_notification", ""), TERM_PROGRAM="ghostty",
                                    **self.ON))
        self.assertEqual(seq, "\x1b]777;notify;Magician;plugin notice\x07")

    def test_other_notification_types_are_ignored(self) -> None:
        for kind in ("idle_prompt", "permission_prompt", "auth_success"):
            with self.subTest(kind=kind):
                proc = self.sb.run(self.SCRIPT, self._event(kind), TERM_PROGRAM="ghostty", **self.ON)
                self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_long_message_is_capped_without_splitting_utf8(self) -> None:
        seq = self._seq(self.sb.run(self.SCRIPT, self._event(message="x" + "\u00e9" * 400), TERM_PROGRAM="ghostty",
                                    **self.ON))
        text = seq[len("\x1b]777;notify;Magician;"):-1]
        self.assertNotIn("\ufffd", text)
        self.assertTrue(text.startswith("x"))
        self.assertEqual(set(text[1:]), {"\u00e9"})
        self.assertLessEqual(len(text.encode("utf-8")), 160)


class PatternDetectTests(_SandboxCase):
    SCRIPT = "pattern-detect.sh"
    REVIEW = "please review the changes in this pull request before we merge"

    def setUp(self) -> None:
        super().setUp()
        self.transcript = self.sb.base / "t.jsonl"
        self.transcript.write_text('{"message":"TRANSCRIPT-MARKER-3"}\n', encoding="utf-8")

    def _run(self, prompt: str, sid: str = "s1") -> subprocess.CompletedProcess:
        return self.sb.run(self.SCRIPT, {"session_id": sid, "hook_event_name": "UserPromptSubmit",
                                         "prompt": prompt, "cwd": str(self.sb.work),
                                         "transcript_path": str(self.transcript)})

    def _ctx(self, prompt: str, sid: str = "s1") -> str:
        proc = self._run(prompt, sid)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout:
            return ""
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"hookSpecificOutput"})
        self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        ctx = doc["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(ctx), BUDGET)
        self.assertIsNone(IMPERATIVE.search(ctx), ctx)
        return ctx

    def _enable_status_line(self) -> None:
        (self.sb.mag / "cli-ui.json").write_text('{"state": "enabled", "components": ["model"]}\n',
                                                 encoding="utf-8")

    def test_keyword_hints_are_single_and_factual(self) -> None:
        cases = {
            self.REVIEW: "magician:divine",
            "please do a security audit of the login handler": "magician:sentinel",
            "the checkout page is slow and latency keeps growing": "magician:accelerate",
            "we need to write up the incident from last night as a post-mortem": "/magician:autopsy",
        }
        for prompt, skill in cases.items():
            with self.subTest(prompt=prompt):
                ctx = self._ctx(prompt)
                self.assertIn(skill, ctx)
                self.assertEqual(ctx.count("Magician:"), 1)

    def test_no_hint_when_a_command_is_named_or_prompt_is_short(self) -> None:
        for prompt in ("/magician:divine review the changes in this PR", "run /divine on the changes in this pr",
                       "use magician:divine to review the changes in this pull request", "review PR",
                       "check my jira tickets for this sprint", "/jira show PROJ-123 and its subtasks",
                       "there are no security changes in this commit message wording"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self._ctx(prompt), "")

    def test_jira_and_confluence_only_when_named_as_commands(self) -> None:
        ctx = self._ctx("please use /jira to show PROJ-123 details")
        self.assertIn("mentions /jira", ctx)
        self.assertIn("bundled jira CLI", ctx)
        self.assertIn("If the user prefers another available Jira integration, use that.", ctx)
        ctx = self._ctx("could you /confluence search for the onboarding page on your-site.atlassian.net")
        self.assertIn("If the user prefers another available Confluence integration, use that.", ctx)

    def test_nothing_is_written_while_the_status_line_is_off(self) -> None:
        before = self.sb.snapshot()
        for prompt in (self.REVIEW, "let's switch on ultracode for this refactor", "exit ultracode now please"):
            self._run(prompt)
        self.assertEqual(self.sb.snapshot(), before)

    def test_status_line_markers_hold_no_prompt_text(self) -> None:
        self._enable_status_line()
        effort = self.sb.mag / "status" / "s1.effort.json"
        self._run("let's use ultracode for this refactor PROMPT-MARKER-5")
        self.assertEqual(json.loads(effort.read_text(encoding="utf-8"))["mode"], "ultracode")
        self._run("ok, exit ultracode now please")
        self.assertFalse(effort.exists())
        self._run(self.REVIEW + " PROMPT-MARKER-5")
        marker = json.loads((self.sb.mag / "status" / "s1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(marker), {"skill", "ts"})
        self.assertEqual(marker["skill"], "divine")
        for root in (self.sb.mag, self.sb.data, self.sb.home):
            text = _all_text(root)
            self.assertNotIn("PROMPT-MARKER-5", text)
            self.assertNotIn("TRANSCRIPT-MARKER-3", text)
        self.assertEqual(list(self.sb.base.rglob("patterns.json")), [])
        self.assertEqual(_tree(self.sb.data), {})

    def test_unsafe_session_id_writes_nothing(self) -> None:
        self._enable_status_line()
        before = self.sb.snapshot()
        for sid in ("../x", "a/b", "s 1"):
            with self.subTest(sid=sid):
                self._run("let's use ultracode for this refactor", sid)
                self._run(self.REVIEW, sid)
                self.assertEqual(self.sb.snapshot(), before)

    def test_large_payload_is_handled_quickly(self) -> None:
        proc = self._run("review the changes in this branch " + "x" * 3_000_000)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("magician:divine", proc.stdout)

    # ---- lazy lore: the pending list session-start.sh leaves in sessions/<id>.lore ----

    def _pending(self, cores: str, sid: str = "s1") -> Path:
        f = self.sb.data / "sessions" / f"{sid}.lore"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(cores + "\n", encoding="utf-8")
        return f

    def _lore(self, prompt: str, sid: str = "s1") -> tuple[str, list]:
        """(additionalContext, injected core names); the hook-authored lines are held to the wording
        rule, the lore cores themselves are bundled text and are not."""
        proc = self._run(prompt, sid)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout:
            return "", []
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        ctx = doc["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(ctx), BUDGET)
        own = [l for l in ctx.splitlines() if l.startswith(("Magician", "Deep-dive files"))]
        self.assertIsNone(IMPERATIVE.search("\n".join(own)), own)
        return ctx, re.findall(r"(?m)^\[([a-z0-9-]+)\] ", ctx)

    def test_lore_core_is_injected_once_when_the_prompt_names_its_stack(self) -> None:
        f = self._pending("python react postgres docker")
        ctx, cores = self._lore("the React component re-renders on every keystroke")
        self.assertEqual(cores, ["react"])
        self.assertIn("Magician lore (baseline guidance; this repository's own conventions take precedence):", ctx)
        self.assertIn((ROOT / "lore" / "react.md").read_text(encoding="utf-8").strip(), ctx)
        self.assertIn("Deep-dive files: lore/deep/<stack>.md under the plugin root", ctx)
        self.assertEqual(f.read_text(encoding="utf-8"), "python react postgres docker\n".replace("react ", ""))
        # the same stack again: nothing, the core is already in the context
        self.assertEqual(self._lore("more react work on the same component please"), ("", []))
        # the title line counts (PostgreSQL), and so does a program on the Commands: line (docker build)
        _, cores = self._lore("we store the sessions in PostgreSQL now")
        self.assertEqual(cores, ["postgres"])
        _, cores = self._lore("why does docker build fail on the second stage")
        self.assertEqual(cores, ["docker"])
        self.assertEqual(f.read_text(encoding="utf-8"), "python\n")
        # the hint and the core share one output
        ctx, cores = self._lore("there is a bug in the python parser, it crashes on empty input")
        self.assertEqual(cores, ["python"])
        self.assertIn("magician:unravel", ctx)
        self.assertEqual(ctx.count("Magician:"), 1)
        self.assertFalse(f.exists(), "an empty pending list is removed")

    def test_unknown_words_and_short_prompts_inject_nothing_and_write_nothing(self) -> None:
        f = self._pending("python react postgres")
        before = f.read_text(encoding="utf-8"), self.sb.snapshot()
        for prompt in ("rust traits are confusing", "hi", "rename the helper", "/divine the branch",
                       "typescript generics"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self._lore(prompt), ("", []))
        self.assertEqual((f.read_text(encoding="utf-8"), self.sb.snapshot()), before)
        self.assertEqual(self._lore("python one", "other"), ("", []), "another session has no pending list")

    def test_skill_invocation_injects_every_pending_core(self) -> None:
        for lead in ("/ward", "/magician:unravel", "/certify", "/accelerate the hot path"):
            with self.subTest(lead=lead):
                f = self._pending("python react", sid="k1")
                ctx, cores = self._lore(lead, "k1")
                self.assertEqual(cores, ["python", "react"])
                self.assertNotIn("Magician:", ctx)
                self.assertFalse(f.exists())
        f = self._pending("python react", sid="k2")
        self.assertEqual(self._lore("/divine the latest commit", "k2"), ("", []))
        self.assertTrue(f.exists())

    def test_lore_cap_leaves_the_rest_pending(self) -> None:
        big = [p.stem for p in sorted((ROOT / "lore").glob("*.md"))]
        f = self._pending(" ".join(big), sid="c1")
        ctx, cores = self._lore("/ward implement it", "c1")
        self.assertLessEqual(len(ctx), BUDGET)
        self.assertGreater(len(cores), 1)
        rest = f.read_text(encoding="utf-8").split()
        self.assertEqual(set(cores) | set(rest), set(big))
        self.assertFalse(set(cores) & set(rest))
        # a tampered list cannot name a file outside lore/
        f.write_text("../README ../../PRIVACY python\n", encoding="utf-8")
        ctx, cores = self._lore("/ward again", "c1")
        self.assertEqual(cores, ["python"])
        self.assertNotIn("# magician", ctx)


class CiWatchTests(_SandboxCase):
    SCRIPT = "ci-watch.sh"
    ALERT = "magician ci-watch: GitHub Actions run {} on the current branch finished with status failure."

    def _gh(self, *responses: str) -> None:
        """Stub gh: the n-th call prints responses[n-1] (the last one repeats); FAIL exits 1."""
        count = self.sb.base / "gh.count"
        cases = "".join(f"  {i}) r={shlex.quote(r)} ;;\n" for i, r in enumerate(responses[:-1], 1))
        self.sb.stub("gh", f"n=$(cat {shlex.quote(str(count))} 2>/dev/null); n=$((${{n:-0}} + 1))\n"
                           f"echo $n > {shlex.quote(str(count))}\n"
                           f"case $n in\n{cases}  *) r={shlex.quote(responses[-1])} ;;\nesac\n"
                           "[ \"$r\" = FAIL ] && exit 1\nprintf '%s\\n' \"$r\"")
        self.sb.stub("sleep")

    def _watch(self, cwd: Path) -> list:
        proc = self.sb.run(self.SCRIPT, cwd=cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    def _repo(self, name: str = "proj") -> Path:
        repo = self.sb.repo(name, branch="watch-branch")
        self.sb.git(repo, "remote", "add", "origin", "../origin.git")
        return repo

    def test_baseline_is_silent_and_new_failures_report_the_number_only(self) -> None:
        self._gh('[{"databaseId":100,"displayTitle":"TITLE-MARKER"}]', '[{"databaseId":100}]',
                 '[{"databaseId": 105, "displayTitle": "TITLE-MARKER"}]')
        before = self.sb.snapshot()
        self.assertEqual(self._watch(self._repo()), [self.ALERT.format(105)])
        calls = self.sb.calls("gh")
        self.assertEqual(len(calls), 120)
        self.assertEqual(calls[0], ["run", "list", "--branch", "watch-branch", "--status", "failure",
                                    "--limit", "1", "--json", "databaseId"])
        self.assertEqual(self.sb.calls("sleep"), [["90"]] * 119)
        self.assertEqual(self.sb.snapshot(), before)

    def test_gh_failure_never_counts_as_a_baseline(self) -> None:
        self._gh("FAIL", '[{"databaseId":100}]', '[{"databaseId":100}]', "FAIL", '[{"databaseId":101}]')
        self.assertEqual(self._watch(self._repo()), [self.ALERT.format(101)])

    def test_no_failures_yet_then_one(self) -> None:
        self._gh("[]", "[]", '[{"databaseId":7}]')
        self.assertEqual(self._watch(self._repo()), [self.ALERT.format(7)])

    def test_silent_without_gh_repo_remote_or_branch(self) -> None:
        empty = self.sb.base / "empty-path"
        empty.mkdir()
        proc = self.sb.run(self.SCRIPT, cwd=self._repo(), path=str(empty))
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self._gh('[{"databaseId":1}]')
        no_remote = self.sb.repo("bare-local")
        detached = self._repo("detached")
        self.sb.git(detached, "commit", "-q", "--allow-empty", "-m", "c")
        self.sb.git(detached, "checkout", "-q", "--detach")
        for cwd in (self.sb.work, no_remote, detached):
            with self.subTest(cwd=cwd.name):
                self.assertEqual(self._watch(cwd), [])
        self.assertEqual(self.sb.calls("gh"), [])


class PreCompactTests(_SandboxCase):
    SCRIPT = "pre-compact.sh"

    def _doc(self, payload) -> dict:
        proc = self.sb.run(self.SCRIPT, payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_asks_for_the_state_file_before_the_summary_and_reads_no_transcript(self) -> None:
        marker = "TRANSCRIPT-ONLY-MARKER-9c1d"
        transcript = self.sb.base / "t.jsonl"
        transcript.write_text(json.dumps({"type": "user", "message": marker}) + "\n", encoding="utf-8")
        before = self.sb.snapshot()
        for trigger in ("auto", "manual"):
            with self.subTest(trigger=trigger):
                doc = self._doc({"hook_event_name": "PreCompact", "trigger": trigger,
                                 "transcript_path": str(transcript), "session_id": "s"})
                self.assertEqual(set(doc), {"systemMessage", "hookSpecificOutput"})
                self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "PreCompact")
                ctx = doc["hookSpecificOutput"]["additionalContext"]
                self.assertIn(".workspace/local/session-state.md", ctx)
                self.assertIn("none is written yet", ctx)
                self.assertNotIn(marker, ctx + doc["systemMessage"])
                self.assertIsNone(IMPERATIVE.search(ctx), ctx)
                self.assertIn("/compact" if trigger == "manual" else "context is full", ctx)
        self.assertEqual(self.sb.snapshot(), before)
        self.assertEqual({p.name for p in self.sb.work.iterdir()}, set(), "the hook wrote into the project")

    def test_notes_an_existing_state_file_and_an_unknown_trigger(self) -> None:
        state = self.sb.work / ".workspace" / "local" / "session-state.md"
        state.parent.mkdir(parents=True)
        state.write_text("# state\n", encoding="utf-8")
        ctx = self._doc({"trigger": "weird"})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("one exists and gets the latest state", ctx)
        self.assertTrue(ctx.startswith("Claude Code is about to summarize this session."), ctx)


class SubagentStopTests(_SandboxCase):
    SCRIPT = "subagent-stop.sh"

    def setUp(self) -> None:
        super().setUp()
        (self.sb.work / ".workspace").mkdir()
        self.transcript = self.sb.base / "agent.jsonl"

    def _payload(self, agent: str = "magician:reviewer", key: str = "transcript_path") -> dict:
        return {"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "a1",
                key: str(self.transcript), "session_id": "s", "cwd": str(self.sb.work)}

    def _write(self, lines: list) -> None:
        self.transcript.write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")

    def _log(self) -> list:
        f = self.sb.work / ".workspace" / "local" / "obstacles.jsonl"
        if not f.exists():
            return []
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]

    def test_blocked_and_degraded_status_lines_are_recorded(self) -> None:
        self._write([{"type": "assistant", "text": "reading"},
                     {"type": "assistant", "text": "Report:\nSTATUS: BLOCKED - the staging DB refused the connection\nnext"}])
        proc = self.sb.run(self.SCRIPT, self._payload())
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        (rec,) = self._log()
        self.assertEqual(set(rec), {"ts", "agent", "status", "obstacle"})
        self.assertRegex(rec["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual((rec["agent"], rec["status"]), ("magician:reviewer", "BLOCKED"))
        self.assertEqual(rec["obstacle"], "the staging DB refused the connection")
        self._write([{"type": "assistant", "text": "STATUS: DEGRADED: no network, static review only"}])
        self.sb.run(self.SCRIPT, self._payload("magician:sentinel", "agent_transcript_path"))
        self.assertEqual([(r["agent"], r["status"], r["obstacle"]) for r in self._log()],
                         [("magician:reviewer", "BLOCKED", "the staging DB refused the connection"),
                          ("magician:sentinel", "DEGRADED", "no network, static review only")])

    def test_reads_only_the_last_4kib_and_keeps_records_under_1kb(self) -> None:
        old = "STATUS: BLOCKED early marker that must not count"
        self._write([{"type": "assistant", "text": old}, {"type": "assistant", "text": "x" * 5000},
                     {"type": "assistant", "text": "STATUS: DEGRADED " + "long " * 300}])
        self.sb.run(self.SCRIPT, self._payload())
        (rec,) = self._log()
        self.assertEqual(rec["status"], "DEGRADED")
        self.assertLess(len(json.dumps(rec)), 1024)
        self.assertTrue(rec["obstacle"].startswith("long long"))
        self._write([{"type": "assistant", "text": old}, {"type": "assistant", "text": "y" * 5000}])
        self.sb.run(self.SCRIPT, self._payload())
        self.assertEqual(len(self._log()), 1, "a marker outside the last 4 KiB was recorded")

    def test_control_characters_and_quotes_are_stripped(self) -> None:
        # raw bytes, as a transcript that is not JSON would carry them: the text ends at a quote or backslash
        self.transcript.write_text("STATUS: BLOCKED \u001b[31mred\u001b[0m\ttab \"q\" \\ back\n", encoding="utf-8")
        self.sb.run(self.SCRIPT, self._payload('magician:fix"er'))
        self.assertEqual(self._log(), [])          # an agent name outside the allowed characters is skipped
        self.sb.run(self.SCRIPT, self._payload())
        (rec,) = self._log()
        self.assertEqual(rec["obstacle"], "[31mred[0m tab")
        self.assertNotIn("\u001b", json.dumps(rec))
        # in a JSON transcript line the text ends at the first escape, so the record stays well-formed
        self._write([{"type": "assistant", "text": "STATUS: DEGRADED one\ntwo"}])
        self.sb.run(self.SCRIPT, self._payload())
        self.assertEqual(self._log()[-1]["obstacle"], "one")

    def test_silent_without_a_status_a_workspace_a_magician_agent_or_a_real_file(self) -> None:
        self._write([{"type": "assistant", "text": "all good, STATUS: OK"}])
        self.sb.run(self.SCRIPT, self._payload())
        self.assertEqual(self._log(), [])
        self._write([{"type": "assistant", "text": "STATUS: BLOCKED x"}])
        self.sb.run(self.SCRIPT, self._payload("reviewer"))
        self.sb.run(self.SCRIPT, self._payload("other:magician:x"))
        self.assertEqual(self._log(), [])
        missing = dict(self._payload(), transcript_path=str(self.sb.base / "nope.jsonl"))
        self.sb.run(self.SCRIPT, missing)
        relative = dict(self._payload(), transcript_path="agent.jsonl")
        self.sb.run(self.SCRIPT, relative)
        self.assertEqual(self._log(), [])
        shutil.rmtree(self.sb.work / ".workspace")
        proc = self.sb.run(self.SCRIPT, self._payload())
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertFalse((self.sb.work / ".workspace").exists(), "the hook created .workspace")


class ModelSwitchTests(_SandboxCase):
    PRE = "pre-model-switch.sh"
    POST = "post-model-switch.sh"
    EVENT = {"hook_event_name": "PreModelSwitch", "from_model": "claude-opus-5-5", "to_model": "claude-sonnet-5-5"}

    def test_pre_switch_is_silent_unless_a_scan_is_active(self) -> None:
        proc = self.sb.run(self.PRE, self.EVENT)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        for how in ("env", "marker"):
            with self.subTest(how=how):
                extra = {"MAGICIAN_PIN_MODEL": "1"} if how == "env" else {}
                if how == "marker":
                    marker = self.sb.work / ".workspace" / "local" / "security-scan.active"
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text("", encoding="utf-8")
                proc = self.sb.run(self.PRE, self.EVENT, **extra)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                doc = json.loads(proc.stdout)
                out = doc["hookSpecificOutput"]
                self.assertEqual(out["hookEventName"], "PreModelSwitch")
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("safety fallback would change tier mid-scan", out["permissionDecisionReason"])
                self.assertIn("claude-opus-5-5 to claude-sonnet-5-5", out["permissionDecisionReason"])
        proc = self.sb.run(self.PRE, {"from_model": "x\"y", "to_model": "z"}, MAGICIAN_PIN_MODEL="1")
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("mid-scan;", reason, "an odd model name is left out of the reason")
        self.assertNotIn("x", reason.split(";")[0])

    def test_post_switch_adds_one_plain_line_of_context(self) -> None:
        proc = self.sb.run(self.POST, self.EVENT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count("\n"), 1)
        self.assertIn("model changed from claude-opus-5-5 to claude-sonnet-5-5; re-check effort and cache assumptions",
                      proc.stdout)
        self.assertIsNone(IMPERATIVE.search(proc.stdout), proc.stdout)
        self.assertEqual(self.sb.run(self.POST, {"from_model": "a"}).stdout, "")
        self.assertIn("from the previous model to b;", self.sb.run(self.POST, {"to_model": "b"}).stdout)


class SetupInitTests(_SandboxCase):
    SCRIPT = "setup-init.sh"

    def test_creates_the_workspace_once_at_the_repo_root(self) -> None:
        repo = self.sb.repo("proj")
        (repo / ".gitignore").write_text("node_modules/", encoding="utf-8")   # no trailing newline
        proc = self.sb.run(self.SCRIPT, {"hook_event_name": "Setup", "trigger": "init"}, cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        msg = json.loads(proc.stdout)["systemMessage"]
        self.assertIn("created .workspace/shared/ and .workspace/local/", msg)
        self.assertIn(".gitignore now lists .workspace/local/", msg)
        for d in ("shared/decisions", "shared/specs", "shared/plans", "shared/research", "shared/postmortems", "local"):
            self.assertTrue((repo / ".workspace" / d).is_dir(), d)
        self.assertEqual((repo / ".gitignore").read_text(encoding="utf-8"),
                         "node_modules/\n# Magician workspace (local machine only)\n.workspace/local/\n")
        again = self.sb.run(self.SCRIPT, {}, cwd=repo)
        self.assertEqual((again.returncode, again.stdout), (0, ""))
        self.assertEqual((repo / ".gitignore").read_text(encoding="utf-8").count(".workspace/local/"), 1)

    def test_creates_gitignore_and_respects_an_existing_entry(self) -> None:
        repo = self.sb.repo("fresh")
        self.sb.run(self.SCRIPT, {}, cwd=repo)
        self.assertEqual((repo / ".gitignore").read_text(encoding="utf-8"),
                         "# Magician workspace (local machine only)\n.workspace/local/\n")
        private = self.sb.repo("private")
        (private / ".gitignore").write_text(".workspace/\n", encoding="utf-8")
        msg = json.loads(self.sb.run(self.SCRIPT, {}, cwd=private).stdout)["systemMessage"]
        self.assertIn("already covers .workspace/local/", msg)
        self.assertEqual((private / ".gitignore").read_text(encoding="utf-8"), ".workspace/\n")

    def test_silent_outside_a_repo_root(self) -> None:
        proc = self.sb.run(self.SCRIPT, {}, cwd=self.sb.work)        # no git
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertEqual(list(self.sb.work.iterdir()), [])
        repo = self.sb.repo("deep")
        sub = repo / "pkg"
        sub.mkdir()
        proc = self.sb.run(self.SCRIPT, {}, cwd=sub)                 # below the root
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertFalse((sub / ".workspace").exists())
        self.assertFalse((repo / ".workspace").exists())


class StopFailureTests(_SandboxCase):
    SCRIPT = "stop-failure.sh"

    def test_points_at_compact_and_the_state_file(self) -> None:
        proc = self.sb.run(self.SCRIPT, {"hook_event_name": "StopFailure", "error": "max_output_tokens"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"systemMessage"})
        self.assertIn("/compact", doc["systemMessage"])
        self.assertIn("written to .workspace/local/session-state.md survives", doc["systemMessage"])
        state = self.sb.work / ".workspace" / "local" / "session-state.md"
        state.parent.mkdir(parents=True)
        state.write_text("# s\n", encoding="utf-8")
        doc = json.loads(self.sb.run(self.SCRIPT, {}).stdout)
        self.assertIn("holds the running state", doc["systemMessage"])


class SteLintHookTests(_SandboxCase):
    """PostToolUse(Write|Edit) STE-lite check: off by default, on through env, .magician/ste or
    cli-ui.json (in that order), only for Markdown under .workspace/shared/ or an opted-in glob,
    findings returned as additionalContext, never a block, exit 0 on anything."""
    SCRIPT = "ste-lint-hook.sh"
    PROSE = "We utilize the cache prior to the build.\n"

    def setUp(self) -> None:
        super().setUp()
        self.proj = self.sb.work
        self.shared = self.proj / ".workspace" / "shared" / "specs"
        self.shared.mkdir(parents=True)
        self.spec = self.shared / "login.md"
        self.spec.write_text(self.PROSE, encoding="utf-8")
        self.other = self.proj / "docs"
        self.other.mkdir()
        self.note = self.other / "note.md"
        self.note.write_text(self.PROSE, encoding="utf-8")

    def _payload(self, path: Path, tool: str = "Write") -> dict:
        return {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": str(path)}}

    def _ctx(self, proc: subprocess.CompletedProcess) -> str:
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"hookSpecificOutput"})
        self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertNotIn("decision", doc)
        return doc["hookSpecificOutput"]["additionalContext"]

    def test_off_by_default(self) -> None:
        proc = self.sb.run(self.SCRIPT, self._payload(self.spec))
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertEqual(self.spec.read_text(encoding="utf-8"), self.PROSE)

    def test_on_and_under_shared_workspace_reports_findings(self) -> None:
        for tool in ("Write", "Edit"):
            proc = self.sb.run(self.SCRIPT, self._payload(self.spec, tool), MAGICIAN_STE="1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ctx = self._ctx(proc)
            self.assertTrue(ctx.startswith("STE-lite: fix these in the same turn"))
            self.assertIn(str(self.spec) + ":1: W4:", ctx)
            self.assertIn('"utilize"', ctx)
            self.assertIn('"prior to"', ctx)
            self.assertLessEqual(len(ctx), BUDGET)
        self.assertEqual(self.spec.read_text(encoding="utf-8"), self.PROSE, "the hook never edits the file")

    def test_on_but_outside_the_shared_workspace_is_silent(self) -> None:
        proc = self.sb.run(self.SCRIPT, self._payload(self.note), MAGICIAN_STE="1")
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        txt = self.proj / ".workspace" / "shared" / "plain.txt"
        txt.write_text(self.PROSE, encoding="utf-8")
        proc = self.sb.run(self.SCRIPT, self._payload(txt), MAGICIAN_STE="1")
        self.assertEqual((proc.returncode, proc.stdout), (0, ""), "only Markdown is checked")

    def test_ste_paths_globs_opt_a_folder_in(self) -> None:
        mag = self.proj / ".magician"
        mag.mkdir()
        (mag / "ste-paths").write_text("# project prose\n\ndocs/*.md\n", encoding="utf-8")
        proc = self.sb.run(self.SCRIPT, self._payload(self.note), MAGICIAN_STE="1")
        self.assertIn(str(self.note) + ":1: W4:", self._ctx(proc))
        elsewhere = self.proj / "README.md"
        elsewhere.write_text(self.PROSE, encoding="utf-8")
        proc = self.sb.run(self.SCRIPT, self._payload(elsewhere), MAGICIAN_STE="1")
        self.assertEqual(proc.stdout, "", "a file no glob names stays silent")

    def test_precedence_env_then_project_file_then_cli_ui(self) -> None:
        mag = self.proj / ".magician"
        mag.mkdir()
        (mag / "ste").write_text("on\n", encoding="utf-8")
        self.assertIn("W4", self._ctx(self.sb.run(self.SCRIPT, self._payload(self.spec))))
        proc = self.sb.run(self.SCRIPT, self._payload(self.spec), MAGICIAN_STE="0")
        self.assertEqual(proc.stdout, "", "env off wins over the project file")
        (mag / "ste").write_text("off\n", encoding="utf-8")
        (self.sb.mag / "cli-ui.json").write_text('{"ste": true}', encoding="utf-8")
        proc = self.sb.run(self.SCRIPT, self._payload(self.spec))
        self.assertEqual(proc.stdout, "", "the project file off wins over cli-ui.json")
        (mag / "ste").unlink()
        self.assertIn("W4", self._ctx(self.sb.run(self.SCRIPT, self._payload(self.spec))))
        (self.sb.mag / "cli-ui.json").write_text('{"ste": false}', encoding="utf-8")
        self.assertEqual(self.sb.run(self.SCRIPT, self._payload(self.spec)).stdout, "")

    def test_clean_prose_and_bad_events_are_silent(self) -> None:
        self.spec.write_text("Use the cache before the build.\n", encoding="utf-8")
        proc = self.sb.run(self.SCRIPT, self._payload(self.spec), MAGICIAN_STE="1")
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        for payload in ("", "not json", "{}", '{"tool_input":{"file_path":"relative.md"}}',
                        json.dumps(self._payload(self.shared / "missing.md"))):
            with self.subTest(payload=payload):
                proc = self.sb.run(self.SCRIPT, payload, MAGICIAN_STE="1")
                self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.assertFalse(self.sb.envfile.exists())


class CloudSessionTests(_SandboxCase):
    """CLAUDE_CODE_REMOTE=1: no launchers, no credential bridge, one note that commands run by full path."""

    def test_launcher_and_credential_hooks_write_nothing_in_the_cloud(self) -> None:
        opts = {"CLAUDE_PLUGIN_OPTION_JIRA_BASE_URL": "https://x.atlassian.net",
                "CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN": "tok-" + "s3cr3t"}
        for script in ("tools-path.sh", "userconfig-env.sh"):
            with self.subTest(script=script):
                proc = self.sb.run(script, {"session_id": "c", "source": "startup"}, CLAUDE_CODE_REMOTE="1", **opts)
                self.assertEqual((proc.returncode, proc.stdout), (0, ""))
                self.assertIn("cloud session", proc.stderr)
                self.assertIn("full path only", proc.stderr)
                self.assertNotIn("s3cr3t", proc.stderr)
        self.assertFalse(self.sb.envfile.exists())
        self.assertFalse((self.sb.data / "tools").exists())
        proc = self.sb.run("tools-path.sh", {}, CLAUDE_CODE_REMOTE="0")
        self.assertTrue((self.sb.data / "tools").exists(), "the launcher hook stays on outside the cloud")

    def test_session_start_names_the_cloud_branch(self) -> None:
        proc = self.sb.run("session-start.sh", {"session_id": "c", "source": "startup"}, CLAUDE_CODE_REMOTE="1")
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Cloud session (CLAUDE_CODE_REMOTE=1)", ctx)
        self.assertIn("run by full path only, as tools/<name> under the plugin root", ctx)
        self.assertEqual(ctx.count(str(ROOT)), 1)
        proc = self.sb.run("session-start.sh", {"session_id": "c", "source": "startup"})
        self.assertNotIn("Cloud session", json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()

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
               "gate.sh")
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
                       r"|agent-lifecycle|worktree-init|pre-compact|mcp-?nudge|fingerprint|session-start-time"
                       r"|\bctx\s+(?:capsule|hook|resume)\b|\bgreet|statusLine",
    "imperative wording": r"(?i:\binvoke\b|before responding|before doing any other work|\bdo not\b"
                          r"|AskUserQuestion|auto-activat|let the user know|\byou must\b|\bIMPORTANT:)",
}
TEXT_RULES = {   # applied to the whole file (comments included)
    "transcript field": r"transcript_path|last_assistant_message|agent_transcript_path",
}
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
        self.assertEqual(again.stdout, "")                      # already formatted: nothing to report
        self.assertEqual(len(self.sb.calls("gofmt")), 2)
        self.assertEqual(self.sb.snapshot(), before)            # nothing stored

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


if __name__ == "__main__":
    unittest.main()

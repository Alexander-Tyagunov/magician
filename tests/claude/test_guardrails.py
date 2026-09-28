"""Security-guardrails contract for the whole shipped plugin surface.

A plugin distributed to other teams IS a production security system: its own scripts, agents, and
skills must not carry secrets, must not over-grant tool authority, and must keep its one hard safety
control (the destructive guard) fail-open. These are the plugin-wide invariants that back the more
targeted hook/agent/skill gates — the "leak scan" and "least privilege" doctrine, made automatic.

The guard's download-and-run cases are generated from the guard's own DOWNLOADERS / RUNNERS token
lines rather than written out, so no runnable download-into-interpreter command appears in this file.
The literal scan for such commands builds its regex from word lists, and its samples fill in
placeholders at runtime, so this file passes its own scan.
"""
from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]

# The repository root is the plugin folder, so every tracked file ships. tests/ is left out of the
# secret scans because its fixtures hold credential-shaped samples on purpose.
UNSCANNED_DIRS = ("tests",)
# Used only when git is unavailable: dirs git never tracks. `plugins` is skipped only at the root,
# where .gitignore keeps the generated Codex package (.agents/plugins/ is tracked).
WALK_SKIP_ANY = {".git", "__pycache__"}
WALK_SKIP_TOP = {"plugins"}

# Concrete credential shapes — anchored to real token formats so they don't fire on prose.
SECRET_PATTERNS = {
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[posru]_[A-Za-z0-9]{36,}"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "atlassian-api-token": re.compile(r"\bATATT[A-Za-z0-9_\-=]{20,}"),
}

# Credential variable names from the pre-userConfig setup. The CLIs read only CLAUDE_PLUGIN_OPTION_*
# now; `\b` doesn't match inside CLAUDE_PLUGIN_OPTION_JIRA_BASE_URL because `_` is a word character.
LEGACY = re.compile(r"\b(?:JIRA|CONFLUENCE)_(?:BASE_URL|API_TOKEN|PAT|PROD_PAT|EMAIL)\b")

GUARD = ROOT / "scripts" / "destructive-guard.sh"
# Only plain command words make meaningful generated cases; `source` and `.` need a file argument.
PLAIN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
NOT_PIPE_RUNNERS = {"source", "."}

# The plugin directory flags any file that holds a complete download-and-run command. These word
# lists are joined into a regex at runtime; no line here holds a downloader and a pipe together.
DL_WORDS = ("curl", "wget", "fetch", "iwr", "irm", "Invoke-WebRequest", "Invoke-RestMethod")
RUN_WORDS = ("sh", "bash", "zsh", "dash", "ksh", "python", "python3", "perl", "ruby", "node",
             "iex", "Invoke-Expression", "pwsh", "powershell")
SOURCE_WORDS = ("source", "eval", ".")  # run a substitution's output in the current shell
PS_RUN_WORDS = ("iex", "Invoke-Expression")  # PowerShell also runs a bare `( … )` subexpression


def _download_and_run_pattern() -> re.Pattern[str]:
    def words(ws: tuple[str, ...]) -> str:
        return "|".join(re.escape(w) for w in ws)

    edge, end = r"(?<![\w.-])", r"(?![\w-])"
    path = r"(?:[\w.-]*/)*"  # an optional directory such as /usr/bin/
    wrap = rf"(?:{path}(?:sudo|doas|env|command|exec|nohup)(?:\s+(?:-\S+|\w+=\S*))*\s+)*"
    dl = rf"{edge}{path}(?:{words(DL_WORDS)}){end}"
    run = rf"{edge}{wrap}{path}(?:{words(RUN_WORDS)}){end}"
    shell = rf"{edge}{wrap}{path}(?:{words(RUN_WORDS + SOURCE_WORDS)}){end}"
    pipe = r"(?<!\|)\|(?!\|)&?"  # a single pipe or `|&`; `||` is "or else", not a pipe
    feed = r"(?:<<<\s*|<\s*)?"  # the substitution may also arrive as a redirect or a here-string
    forms = (
        rf"{dl}[^\n]*?{pipe}\s*{run}",  # downloader, then later a pipe into a runner
        rf"{shell}(?:\s+-\S+)*\s+{feed}[\"']?[<$]\(\s*{dl}",  # runner fed a substituted download
        rf"{edge}(?:{words(PS_RUN_WORDS)}){end}\s*[\"']?\$?\(\s*{dl}",  # iex on a bracketed download
    )
    return re.compile("|".join(f"(?:{f})" for f in forms), re.I)


DOWNLOAD_AND_RUN = _download_and_run_pattern()

# The plugin directory blocks a package launcher followed by a package with no exact version in the
# files it reads as code (Markdown prose isn't checked). No word below is followed by a package name.
LAUNCHER_WORDS = ("npx", "bunx", "uvx", "pnpx", "pnpm dlx", "yarn dlx", "pipx run", "npm exec")
UV_RUN_WORD = "uv run"


def _unpinned_launcher_pattern() -> re.Pattern[str]:
    words = "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in LAUNCHER_WORDS)
    pkg = r"(?:@[\w.-]+/)?[A-Za-z0-9][\w.-]*"  # name or @scope/name
    exact = r"\d+\.\d+\.\d+(?:-[\w.]+)?(?![\w.+/-]|\|\|)"  # 1.2.3 or 1.2.3-beta.1, not a range
    loose = rf"(?:@(?!{exact})\S*)?"  # no version, or one that isn't exact (latest, ^1.2.0, 1)
    # The name must end where it can't continue, so backtracking can't cut it short to dodge a pin.
    return re.compile(rf"(?<![\w.-])(?:{words})(?:\s+--?[\w-]+)*\s+(?:--package=)?{pkg}{loose}(?![\w./@-])")


UNPINNED_LAUNCHER = _unpinned_launcher_pattern()
# `uv run` starts a tool too; the directory accepts it with --locked or --frozen instead of a version.
UV_RUN = re.compile(r"(?<![\w.-])uv\s+run\s+[\w@.-]")
UV_LOCKED = re.compile(r"(?<!\S)--(?:locked|frozen)(?!\S)")


def holds_unpinned_launcher(line: str) -> bool:
    return bool(UNPINNED_LAUNCHER.search(line) or (UV_RUN.search(line) and not UV_LOCKED.search(line)))


def tracked_files(use_git: bool = True) -> list[Path]:
    """Every file git tracks, as it is in the working tree (a tracked file deleted locally is
    skipped). Walks the tree instead when git or the repository is unavailable."""
    rels: list[str] = []
    if use_git:
        try:
            out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                                 text=True, check=True, timeout=30).stdout
            rels = [r for r in out.split("\0") if r]
        except (OSError, subprocess.SubprocessError):
            rels = []
    if not rels:
        parts = [p.relative_to(ROOT).parts for p in ROOT.rglob("*") if p.is_file()]
        rels = ["/".join(ps) for ps in parts
                if ps[0] not in WALK_SKIP_TOP and not WALK_SKIP_ANY & set(ps)]
    return [ROOT / r for r in rels if (ROOT / r).is_file()]


def text_of(path: Path) -> str | None:
    """The file as UTF-8 text; None for binary files (images) and unreadable ones."""
    try:
        return path.read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def shipped_text_files() -> list[Path]:
    """Every tracked text file outside tests/."""
    return [p for p in tracked_files()
            if p.relative_to(ROOT).parts[0] not in UNSCANNED_DIRS and text_of(p) is not None]


def download_and_run_lines(text: str) -> list[int]:
    """1-based numbers of the lines that hold a complete download-and-run command."""
    return [n for n, line in enumerate(text.splitlines(), 1) if DOWNLOAD_AND_RUN.search(line)]


def download_and_run_hits(paths: list[Path]) -> list[str]:
    """`file:line` for each download-and-run line in the given files."""
    hits: list[str] = []
    for path in paths:
        text = text_of(path)
        if text is None:
            continue
        name = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        hits += [f"{name}:{n}" for n in download_and_run_lines(text)]
    return hits


def bin_clis() -> list[Path]:
    return sorted(p for p in (ROOT / "tools").glob("*") if p.is_file() and "__pycache__" not in p.parts)


def guard_tokens(name: str) -> list[str] | None:
    """The guard's `NAME="…"` token line, split into words; None when the line is absent."""
    if not GUARD.is_file():
        return None
    m = re.search(rf'^{name}="([^"]*)"$', GUARD.read_text(encoding="utf-8"), re.M)
    return m.group(1).split() if m else None


def _bash() -> str:
    return "/bin/bash" if Path("/bin/bash").exists() else (shutil.which("bash") or "bash")


class GuardrailsTests(unittest.TestCase):
    def test_no_hardcoded_secrets_in_shipped_surface(self) -> None:
        """Leak scan as a gate: no shipped file may contain a literal credential. A distributed plugin
        that carries a real token hands every downstream team the maintainer's keys. The scan covers
        every tracked text file outside tests/ (lore, monitors, the conjure JS and HTML included);
        `.claude-plugin` is part of it, so a token pasted into a userConfig default fails here."""
        for path in shipped_text_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for label, pat in SECRET_PATTERNS.items():
                with self.subTest(file=str(path.relative_to(ROOT)), pattern=label):
                    self.assertIsNone(pat.search(text), f"possible {label} literal in {path.name}")

    def test_atlassian_token_pattern_matches_the_token_shape(self) -> None:
        """Self-check for the pattern above; the sample is assembled at runtime, never stored whole."""
        pat = SECRET_PATTERNS["atlassian-api-token"]
        self.assertIsNotNone(pat.search("token: " + "ATATT" + "A1b2" * 8))
        self.assertIsNone(pat.search("ATATT is the Atlassian token prefix"))

    def test_bin_clis_read_credentials_from_user_config(self) -> None:
        """Every credentialed CLI must take its token from magician's userConfig (exported by the
        SessionStart bridge as CLAUDE_PLUGIN_OPTION_*), never from ambient credential variables and
        never baked in. This keeps secrets out of source and out of the package."""
        for cli in bin_clis():
            text = cli.read_text(encoding="utf-8", errors="ignore")
            if not re.search(r"TOKEN|PASSWORD|SECRET|API_KEY|PAT\b", text):
                continue  # not a credentialed CLI
            with self.subTest(cli=cli.name):
                self.assertIn("CLAUDE_PLUGIN_OPTION_", text,
                              f"{cli.name} handles credentials but doesn't read magician's userConfig")
                self.assertIsNone(LEGACY.search(text),
                                  f"{cli.name} still names a legacy credential variable")
                self.assertNotRegex(
                    text, r'(?i)(token|password|secret|api_key)\s*=\s*["\'][A-Za-z0-9/+_-]{16,}["\']',
                    f"{cli.name} appears to assign a literal credential",
                )

    def test_no_legacy_credential_env_names_on_shipped_surface(self) -> None:
        """The pre-userConfig credential variables are gone from everything that ships (the README,
        CHANGELOG and lore included), so no doc or script sends a user back to putting a token in
        settings.json or the shell."""
        for path in shipped_text_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            with self.subTest(file=str(path.relative_to(ROOT))):
                m = LEGACY.search(text)
                self.assertIsNone(m, f"legacy credential variable {m.group(0) if m else ''} in {path.name}")

    def test_scan_scope_is_every_tracked_text_file(self) -> None:
        """The two scans above read the file list from git, not from a list of dirs: a fixed list once
        missed lore/, monitors/ and the conjure JS and HTML helpers. tests/ stays out, binary files
        are skipped, and the no-git walk finds at least every file git tracks."""
        scanned = {p.relative_to(ROOT).as_posix() for p in shipped_text_files()}
        for rel in ("README.md", "lore/python.md", "monitors/monitors.json",
                    "skills/conjure/scripts/helper.js", "skills/conjure/scripts/server.cjs",
                    "skills/conjure/scripts/frame-template.html"):
            if (ROOT / rel).is_file():
                with self.subTest(file=rel):
                    self.assertIn(rel, scanned)
        self.assertTrue(any(r.startswith("lore/") for r in scanned), "lore/ is not scanned")
        self.assertFalse([r for r in scanned if r.startswith("tests/")], "tests/ is scanned")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "icon.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff\xfe")
            self.assertIsNone(text_of(image), "a binary file was read as text")
        tracked = {p.relative_to(ROOT).as_posix() for p in tracked_files()}
        walked = {p.relative_to(ROOT).as_posix() for p in tracked_files(use_git=False)}
        self.assertEqual(sorted(tracked - walked), [], "the no-git walk misses tracked files")

    def test_credentialed_clis_keep_secrets_out_of_process_arguments(self) -> None:
        """A token passed in a curl argv is visible to any process that can read `ps`/`/proc` — a
        classic secret-exposure (CWE-214). Credentialed CLIs must hand headers to curl over stdin
        (`-H @-` + `input=headers`), never build `Authorization: <token>` into the argv list."""
        for cli in bin_clis():
            text = cli.read_text(encoding="utf-8", errors="ignore")
            if '"curl"' not in text or "_auth()" not in text:
                continue  # not an HTTP CLI that carries an auth token
            with self.subTest(cli=cli.name):
                self.assertNotIn('"-H", "Authorization: " + _auth()', text,
                                 f"{cli.name} builds the auth header into curl argv (secret in ps)")
                self.assertIn('"-H", "@-"', text, f"{cli.name} does not read headers from stdin")
                self.assertIn("input=headers", text,
                              f"{cli.name} does not pass headers to curl via stdin")

    def test_no_agent_or_skill_grants_unbounded_tools(self) -> None:
        """Least privilege across the whole plugin: no agent or skill may request `*` / all tools.
        A wildcard grant on a spawnable identity is the collapse of the three-identity separation."""
        for path in (ROOT / "agents").glob("*.md"):
            fields, _ = read_frontmatter(path)
            with self.subTest(agent=path.name):
                tools = {t.strip() for t in fields.get("tools", "").split(",")}
                self.assertNotIn("*", tools, f"{path.name} grants all tools (tools: *)")
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            fields, _ = read_frontmatter(path)
            allowed = fields.get("allowed-tools", "")
            with self.subTest(skill=path.parent.name):
                self.assertNotIn("*", {t.strip() for t in allowed.split(",")},
                                 f"{path.parent.name} allows all tools (allowed-tools: *)")

    # ---- download-and-run literals (the plugin directory flags them in any file) ----

    def test_no_tracked_file_holds_a_download_and_run_command(self) -> None:
        """The plugin directory warns on any file that holds a complete download-and-run command,
        tests and docs included, so every tracked file is scanned. Guard and test samples must be
        assembled from parts at runtime instead."""
        hits = download_and_run_hits(tracked_files())
        self.assertEqual(hits, [], "download-and-run command written out in: " + ", ".join(hits))

    def test_download_and_run_matcher_flags_samples(self) -> None:
        """Self-check for the scan above. Samples fill `{d}` (downloader), `{r}` (runner) and `{p}`
        (a pipe) at runtime, so none is stored whole."""
        caught = (
            "{d} -fsSL {u} {p} {r}",
            "{d} -s {u}{p}{r}",
            "{d} -s {u} {p}& {r}",
            "{d} -s {u} {p} sudo -E {r} -s -- --yes",
            "{d} -s {u} {p} /usr/bin/env {r}",
            "{d} -s {u} {p} sudo env MODE=1 /bin/{r} -",
            "/usr/bin/{d} -s {u} -o- {p} tee install.log {p} {r}",
            "A doc may show `{d} {u} {p} {r}` inline.",
            "{r} <({d} -s {u})",
            "{r} -s < <({d} -s {u})",
            '{r} <<< "$({d} -s {u})"',
            '{r} -c "$({d} -fsSL {u})"',
            "source <({d} -s {u})",
            ". <({d} -s {u})",
            "ev" + 'al "$({d} -s {u})"',  # split so the sample is never stored whole
            "iex ({d} {u})",
        )
        missed = (
            "{d} -fsSL {u} -o install.sh",  # download only
            "{d} -f {u} {p}{p} {r} fallback.sh",  # `||` runs the next command, not the download
            "cat install.sh {p} {r}",  # no download
            "{d} {u} {p} jq .",  # piped into a non-interpreter
            "{d} {u} {p} {r}lint",  # a longer command word
            "{d} {u} {p} {r}-lint",
            "lib{d} docs {p} {r}",  # the downloader word inside another word
            "x=$({d} -s {u})",  # output captured, not run
            "echo $({d} -s {u})",
            "cat < <({d} -s {u})",  # fed to a non-interpreter
            "{d} -o install.sh {u}\n{r} install.sh",  # separate lines
            "{p} `{d}` {p} downloads {p} `{r}` {p}",  # a Markdown table row
        )
        for label, templates, want in (("caught", caught, True), ("missed", missed, False)):
            wrong = []
            for template, d, r in itertools.product(templates, DL_WORDS, RUN_WORDS):
                sample = template.format(d=d, r=r, p="|", u="example.test/install")
                if bool(download_and_run_lines(sample)) != want:
                    wrong.append(sample)
            with self.subTest(expected=label):
                self.assertEqual(wrong, [], f"matcher got these wrong (expected {label})")

    def test_no_code_file_holds_an_unpinned_launcher(self) -> None:
        """Every tracked file except Markdown, tests included: the directory reads them as code."""
        hits = []
        for path in tracked_files():
            text = text_of(path)
            if text is None or path.suffix == ".md":
                continue
            hits += [f"{path.relative_to(ROOT)}:{n}" for n, line in enumerate(text.splitlines(), 1)
                     if holds_unpinned_launcher(line)]
        self.assertEqual(hits, [], "unpinned package launcher written out in: " + ", ".join(hits))

    def test_unpinned_launcher_matcher_flags_samples(self) -> None:
        """Self-check for the scan above; `{l}` is filled with each launcher word at runtime."""
        caught = ("{l} tsc", "Bash({l} tsc *)", "{l} -y some-tool --flag", "run `{l} @scope/tool`",
                  "{l} tool@latest", "{l} tool@^1.2.0", "{l} tool@1", "{l} launcher\")",
                  "{l} tool@1.2.3||2.0.0", "{l} --package=tool bin", "{l} --yes --package=@scope/tool -- bin",
                  "{l} --package=tool@latest bin")
        missed = ("{l} tool@1.2.3", "{l} @scope/tool@1.2.3 --flag", "Bash({l} tool@1.2.3-beta.1 *)", '("{l}", "other")', "{l}\\s",
                  "a launcher ({l}) in a command", "no{l} tool", "{l}-cache tool", "Bash({l} tool@1.2.3:*)",
                  "[{l} tool@1.2.3, x]", "{l} tool@1.2.3; echo", "{l} tool@1.2.3&&x", "{l} --package=tool@1.2.3 bin")
        uv_caught = ("{u} ruff", "{u} --with tool script.py", "Bash({u} pytest:*)")
        uv_missed = ("{u} --locked ruff", "{u} --frozen pytest", '("{u}", "x")', "a{u} tool")
        for label, pairs, want in (
                ("caught", [(t, w) for t in caught for w in LAUNCHER_WORDS] + [(t, UV_RUN_WORD) for t in uv_caught], True),
                ("missed", [(t, w) for t in missed for w in LAUNCHER_WORDS] + [(t, UV_RUN_WORD) for t in uv_missed], False)):
            wrong = [s for s in (t.format(l=w, u=w) for t, w in pairs) if holds_unpinned_launcher(s) != want]
            with self.subTest(expected=label):
                self.assertEqual(wrong, [], f"matcher got these wrong (expected {label})")

    def test_download_and_run_scan_catches_a_planted_file(self) -> None:
        """The file scan reports `file:line` for a sample planted in a temp file (never the repo)."""
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "install.md"
            planted.write_text("# Install\n{d} -fsSL example.test/i {p} {r}\n".format(
                d=DL_WORDS[0], p="|", r=RUN_WORDS[1]), encoding="utf-8")
            clean = Path(tmp) / "notes.md"
            clean.write_text("Download the script, read it, then run it.\n", encoding="utf-8")
            self.assertEqual(download_and_run_hits([planted, clean]), [f"{planted}:2"])

    # ---- destructive guard (PreToolUse; exit 2 + stderr reason = block, exit 0 = allow) ----

    def _guard(self, stdin: str) -> subprocess.CompletedProcess:
        # Fully specified env: nothing inherited from the session running the suite.
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "PATH": "/usr/bin:/bin",
                "HOME": tmp,
                "LC_ALL": "C",
                "CLAUDE_PLUGIN_ROOT": str(ROOT),
                "CLAUDE_PLUGIN_DATA": os.path.join(tmp, "data"),
                "MAGICIAN_HOME": os.path.join(tmp, "magician"),
                "MAGICIAN_SETTINGS": os.path.join(tmp, "settings.json"),
                "CLAUDE_ENV_FILE": os.path.join(tmp, "session.env"),
            }
            return subprocess.run([_bash(), str(GUARD)], input=stdin, env=env, cwd=tmp,
                                  capture_output=True, text=True, timeout=20)

    @staticmethod
    def _bash_call(command: str) -> str:
        return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})

    def test_destructive_guard_fails_open_by_design(self) -> None:
        """The one hard safety control must never brick the shell: input it can't parse, or a benign
        command, has to exit 0 rather than block or crash."""
        self.assertTrue(GUARD.is_file(), "scripts/destructive-guard.sh is missing")
        for label, stdin in (("empty stdin", ""), ("not JSON", "{{ not json"),
                             ("no command", json.dumps({"tool_name": "Bash", "tool_input": {}})),
                             ("benign", self._bash_call("git status"))):
            with self.subTest(case=label):
                p = self._guard(stdin)
                self.assertEqual(p.returncode, 0, f"guard did not allow ({label}): {p.stderr[:200]}")

    def test_download_and_run_pipes_are_caught_by_the_guard(self) -> None:
        """Injection regression floor, asserted at the plugin level: a network download piped straight
        into an interpreter is blocked. Cases are built from the guard's own token lists so every
        DOWNLOADERS and RUNNERS word is exercised at least once (behaviour in depth lives in
        test_destructive_guard)."""
        downloaders, runners = guard_tokens("DOWNLOADERS"), guard_tokens("RUNNERS")
        if downloaders is None or runners is None:
            self.skipTest('scripts/destructive-guard.sh has no DOWNLOADERS="…" / RUNNERS="…" token lines '
                          "(the shared guard interface); generated download-and-run cases can't be built")
        downloaders = [d for d in downloaders if PLAIN_WORD.fullmatch(d)]
        runners = [r for r in runners if PLAIN_WORD.fullmatch(r) and r not in NOT_PIPE_RUNNERS]
        self.assertTrue(downloaders and runners, "guard token lists are empty")
        pairs = {(d, runners[i % len(runners)]) for i, d in enumerate(downloaders)}
        pairs |= {(downloaders[i % len(downloaders)], r) for i, r in enumerate(runners)}
        for d, r in sorted(pairs):
            segments = (f"{d} example.test/install", r)
            with self.subTest(downloader=d, runner=r):
                p = self._guard(self._bash_call(" | ".join(segments)))
                self.assertEqual(p.returncode, 2, f"guard allowed a download piped into {r} via {d}")
                self.assertTrue(p.stderr.strip(), "guard blocked without a reason on stderr")


if __name__ == "__main__":
    unittest.main()

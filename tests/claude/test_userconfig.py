"""userConfig + session-env bridge contract (Jira/Confluence credentials).

Claude Code keeps magician's userConfig values (tokens in the system credential store) and exports
them to hook processes as CLAUDE_PLUGIN_OPTION_<KEY>. The SessionStart hook scripts/userconfig-env.sh
copies the non-empty Jira/Confluence ones into the session env file so the bundled `jira` and
`confluence` CLIs, which run through the Bash tool, can read them. These tests pin the schema, the
bridge's quoting/privacy behaviour, the CLIs' connection-config block, and the CLIs' auth shapes.

Every subprocess gets a fully specified env built from temp dirs: nothing (least of all a real
CLAUDE_ENV_FILE from the session running the suite) is inherited from the parent process.
"""
from __future__ import annotations

import base64
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
USER_CONFIG = PLUGIN.get("userConfig", {})
BRIDGE = ROOT / "scripts" / "userconfig-env.sh"
BINS = {"jira": ROOT / "bin" / "jira", "confluence": ROOT / "bin" / "confluence"}
WHOAMI = {"jira": "myself", "confluence": "whoami"}
ALLOWED = {"type", "title", "description", "required", "default", "multiple", "sensitive", "min", "max"}
SECRETISH = re.compile(r"(token|secret|password|_pat)$", re.I)
BEGIN, END = "# ---- magician:connection-config begin", "# ---- magician:connection-config end ----"
CONTRACT = {"BASE", "TOKEN", "EMAIL", "CONFIG_LOADED", "SETUP_HINT", "BASE_URL_HINT"}
BRIDGE_LINE = "export MAGICIAN_USERCONFIG_BRIDGE=1"
# Only string options (the Jira/Confluence connection fields) are bridged; booleans are read by hooks.
BRIDGED = {f"CLAUDE_PLUGIN_OPTION_{k.upper()}" for k, v in USER_CONFIG.items() if v.get("type") == "string"}
# A dotenv filename used as a path: `.env`, optionally with suffixes (`.env.local`, `.env.*`) or a
# trailing `*` glob, after the line start, `/`, whitespace, a quote, `<`, `=`, `(`, `{` or `,`, and
# before whitespace, a quote, `;`, `)`, `|`, `&`, `,`, `}`, `>` or the line end. `.envrc`,
# `.environment`, `ENV_FILE` and a `.env/` directory don't match.
DOTENV = re.compile(r"""(?:^|(?<=[/\s"'`<=({,]))\.env(?:\.(?:\*|[\w-]+))*\*?(?=[\s"'`;)|&,}>]|$)""",
                    re.M)


def _bash() -> str:
    return "/bin/bash" if Path("/bin/bash").exists() else (shutil.which("bash") or "bash")


class _Stub(http.server.BaseHTTPRequestHandler):
    """Records each request's path and Authorization header; answers every GET with one JSON shape."""
    seen: list[tuple[str, str]] = []

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        type(self).seen.append((self.path, self.headers.get("Authorization", "")))
        body = json.dumps({"displayName": "Stub User", "emailAddress": "user@example.test",
                           "username": "stub", "total": 0, "issues": [], "results": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class _Sandbox(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.data = self.tmp / "plugin-data"
        self.env_file = self.tmp / "session.env"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def base_env(self, env_file: bool = True, **extra: str) -> dict[str, str]:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "LC_ALL": "C",
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "CLAUDE_PLUGIN_DATA": str(self.data),
            "MAGICIAN_HOME": str(self.tmp / "magician"),
            "MAGICIAN_SETTINGS": str(self.tmp / "settings.json"),
        }
        if env_file:
            env["CLAUDE_ENV_FILE"] = str(self.env_file)
        env.update(extra)
        return env

    def bridge(self, env_file: bool = True, extra: dict[str, str] | None = None,
               **opts: str) -> subprocess.CompletedProcess:
        env = self.base_env(env_file, **(extra or {}))
        env.update({f"CLAUDE_PLUGIN_OPTION_{k.upper()}": v for k, v in opts.items()})
        p = subprocess.run([_bash(), str(BRIDGE)], env=env, cwd=self.tmp,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "", "the bridge must never print to stdout")
        return p

    def source_and_print(self, shell: str, var: str) -> bytes:
        """Source the env file with `shell` in a clean env and print one variable, byte for byte."""
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home), "LC_ALL": "C"}
        p = subprocess.run([shell, "-c", '. "$1"; printf %s "${' + var + '}"', "sh", str(self.env_file)],
                           env=env, cwd=self.tmp, capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def lines(self) -> list[str]:
        return self.env_file.read_text(encoding="utf-8").splitlines()


class UserConfigSchemaTests(unittest.TestCase):
    def test_user_config_schema(self) -> None:
        """Only fields the strict manifest schema knows (no `options`, which needs a newer Claude
        Code), every option optional, and every secret-looking option sensitive with no default."""
        self.assertTrue(USER_CONFIG, "plugin.json has no userConfig")
        for key, opt in USER_CONFIG.items():
            with self.subTest(option=key):
                self.assertRegex(key, r"^[A-Za-z_][A-Za-z0-9_]*$")
                self.assertLessEqual(set(opt), ALLOWED, f"unknown fields {set(opt) - ALLOWED}")
                self.assertIn(opt.get("type"), {"string", "boolean"})
                for field in ("title", "description"):
                    self.assertIsInstance(opt.get(field), str)
                    self.assertTrue(opt[field].strip(), f"{key}.{field} is empty")
                self.assertIs(opt.get("required", False), False, f"{key} must stay optional")
                if SECRETISH.search(key):
                    self.assertIs(opt.get("sensitive"), True, f"{key} looks secret but isn't sensitive")
                    self.assertNotIn("default", opt, f"{key} looks secret but has a default")
                if opt["type"] == "boolean":
                    self.assertIsInstance(opt.get("default"), bool, f"{key} needs a boolean default")

    def test_boolean_defaults(self) -> None:
        """Opt-in behaviours default off; only the local session history defaults on."""
        booleans = {k: v["default"] for k, v in USER_CONFIG.items() if v.get("type") == "boolean"}
        self.assertEqual(booleans, {"auto_format": False, "auto_format_prettier": False,
                                    "desktop_notifications": False, "session_history": True})

    def test_connection_fields_are_declared(self) -> None:
        for product in ("jira", "confluence"):
            for field in ("base_url", "email", "api_token"):
                with self.subTest(option=f"{product}_{field}"):
                    self.assertEqual(USER_CONFIG.get(f"{product}_{field}", {}).get("type"), "string")

    def test_bridge_covers_every_option(self) -> None:
        """The bridge exports exactly the string (connection) options — no more, no fewer."""
        names = set(re.findall(r"CLAUDE_PLUGIN_OPTION_[A-Z0-9_]+", BRIDGE.read_text(encoding="utf-8")))
        self.assertEqual(names, BRIDGED)

    def test_connection_config_block_contract(self) -> None:
        """The Codex build swaps out exactly one marked block, so everything that ties a CLI to
        userConfig must live inside it, and the block must define every name the rest relies on."""
        for name, path in BINS.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(cli=name):
                self.assertEqual(text.count(BEGIN), 1)
                self.assertEqual(text.count(END), 1)
                start, stop = text.index(BEGIN), text.index(END)
                self.assertLess(start, stop)
                stop += len(END)
                for needle in ("CLAUDE_PLUGIN_OPTION_", "/plugin configure", "MAGICIAN_USERCONFIG_BRIDGE"):
                    for m in re.finditer(re.escape(needle), text):
                        self.assertTrue(start < m.start() < stop,
                                        f"{needle} outside the connection-config block at offset {m.start()}")
                assigned = {m.group(1) for line in text[start:stop].splitlines()
                            if (m := re.match(r"^(\w+)\s*=", line))}
                self.assertLessEqual(CONTRACT, assigned, f"block doesn't assign {CONTRACT - assigned}")


class BridgeTests(_Sandbox):
    def test_bridge_is_plain_shell(self) -> None:
        text = BRIDGE.read_text(encoding="utf-8")
        for pat in (r"python", r"\bnode\b", r"\bperl\b", r"\bruby\b", r"\bawk\b", r"\beval\b",
                    r"\bsource ", r"(?m)^\s*\. "):
            with self.subTest(pattern=pat):
                self.assertIsNone(re.search(pat, text), f"bridge uses {pat}")
        self.assertTrue(BRIDGE.stat().st_mode & stat.S_IXUSR, "bridge is not executable")

    def test_bridge_without_env_file_is_a_noop(self) -> None:
        before = sorted(p.name for p in self.tmp.iterdir())
        self.bridge(env_file=False, jira_api_token="tok-noop")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), before)

    def test_bridge_round_trips_hostile_value(self) -> None:
        canary = self.tmp / "CANARY"
        token = "ab'c$(touch " + str(canary) + ")\"d\\e `id` %s & '' end"
        self.bridge(jira_api_token=token)
        for shell in (_bash(), "/bin/sh"):
            with self.subTest(shell=shell):
                self.assertEqual(self.source_and_print(shell, "CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN"),
                                 token.encode())
        self.assertFalse(canary.exists(), "sourcing the env file executed part of the value")

    def test_bridge_exports_only_what_is_set(self) -> None:
        self.bridge(jira_base_url="site-url", jira_api_token="tok-set")
        exported = {line.split("=", 1)[0][len("export "):] for line in self.lines()}
        self.assertEqual(exported, {"CLAUDE_PLUGIN_OPTION_JIRA_BASE_URL", "CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN",
                                    "MAGICIAN_DATA", "MAGICIAN_USERCONFIG_BRIDGE"})
        self.assertEqual(self.lines()[-1], BRIDGE_LINE)

    def test_bridge_is_idempotent(self) -> None:
        opts = {"jira_base_url": "site-url", "jira_email": "user@example.test",
                "jira_api_token": "tok-idem", "confluence_base_url": "site-url/wiki"}
        self.bridge(**opts)
        first = self.lines()
        self.bridge(**opts)
        self.assertEqual(self.lines(), first)
        self.assertEqual(len(first), len(set(first)))

    def test_bridge_appends_after_a_line_without_newline(self) -> None:
        self.env_file.write_text("export OTHER_TOOL=1", encoding="utf-8")
        self.bridge(jira_api_token="tok-append")
        lines = self.lines()
        self.assertEqual(lines[0], "export OTHER_TOOL=1")
        self.assertIn("export CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN='tok-append'", lines)
        self.assertEqual(lines[-1], BRIDGE_LINE)

    def test_bridge_skips_empty_and_control_chars_without_leaking(self) -> None:
        self.bridge(jira_base_url="", jira_email="", jira_api_token="")
        self.assertFalse([line for line in self.lines() if "CLAUDE_PLUGIN_OPTION_" in line])
        self.assertIn(BRIDGE_LINE, self.lines())

        self.env_file.unlink()
        p = self.bridge(jira_api_token="leakhalfone\nleakhalftwo")
        self.assertIn("CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN", p.stderr)
        written = self.env_file.read_text(encoding="utf-8")
        for half in ("leakhalfone", "leakhalftwo"):
            self.assertNotIn(half, p.stderr)
            self.assertNotIn(half, written)

    def test_bridge_output_is_private_and_silent(self) -> None:
        self.bridge(jira_api_token="tok-private")  # asserts empty stdout itself
        self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)

    def test_bridge_exports_plugin_data_dir(self) -> None:
        odd = self.tmp / "data dir with 'quote'"
        self.bridge(extra={"CLAUDE_PLUGIN_DATA": str(odd)})
        self.assertEqual(self.source_and_print("/bin/sh", "MAGICIAN_DATA"), str(odd).encode())

        self.env_file.unlink()
        env = self.base_env()
        del env["CLAUDE_PLUGIN_DATA"]
        subprocess.run([_bash(), str(BRIDGE)], env=env, cwd=self.tmp, capture_output=True, timeout=10)
        self.assertFalse([line for line in self.lines() if line.startswith("export MAGICIAN_DATA=")])


class CliTests(_Sandbox):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        super().setUp()
        _Stub.seen = []

    def url(self, path: str = "", port: int | None = None) -> str:
        return f"http://127.0.0.1:{port or self.port}{path}"

    def cli(self, name: str, *args: str, bridged: bool = True, **opts: str) -> subprocess.CompletedProcess:
        env = self.base_env(JIRA_CACHE_TTL="0", JIRA_MIN_INTERVAL_MS="0", JIRA_RETRIES="0", JIRA_TIMEOUT="10",
                            CONFLUENCE_CACHE_TTL="0", CONFLUENCE_MIN_INTERVAL_MS="0",
                            CONFLUENCE_RETRIES="0", CONFLUENCE_TIMEOUT="10")
        if bridged:
            env["MAGICIAN_USERCONFIG_BRIDGE"] = "1"
        env.update({f"CLAUDE_PLUGIN_OPTION_{k.upper()}": v for k, v in opts.items()
                    if not k.isupper()})
        env.update({k: v for k, v in opts.items() if k.isupper()})
        return subprocess.run([sys.executable, str(BINS[name]), *args], env=env, cwd=self.tmp,
                              capture_output=True, text=True, timeout=30)

    def test_cli_errors_point_to_plugin_configure(self) -> None:
        for name, path in BINS.items():
            with self.subTest(cli=name, case="not loaded"):
                p = self.cli(name, WHOAMI[name], bridged=False)
                self.assertEqual(p.returncode, 1)
                self.assertIn("aren't loaded in this session", p.stderr)
                self.assertIn("/plugin configure magician", p.stderr)
                self.assertNotIn("settings.json", p.stderr)
            with self.subTest(cli=name, case="no token"):
                p = self.cli(name, WHOAMI[name], **{f"{name}_base_url": self.url()})
                self.assertEqual(p.returncode, 1)
                self.assertIn("API token configured", p.stderr)
                self.assertIn("/plugin configure magician", p.stderr)
                self.assertNotIn("settings.json", p.stderr)
        self.assertEqual(_Stub.seen, [])

    def test_cli_refuses_plain_http_to_a_remote_host(self) -> None:
        for name in BINS:
            with self.subTest(cli=name):
                p = self.cli(name, WHOAMI[name], **{f"{name}_base_url": "http://" + "remote." + "test",
                                                    f"{name}_api_token": "tok-http"})
                self.assertEqual(p.returncode, 1)
                self.assertIn("must start with https://", p.stderr)
                self.assertNotIn("tok-http", p.stderr)

    def test_cli_auth_header_shapes(self) -> None:
        p = self.cli("jira", "myself", jira_base_url=self.url(), jira_api_token="pat-server")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(_Stub.seen[-1], ("/rest/api/2/myself", "Bearer pat-server"))

        p = self.cli("jira", "myself", jira_base_url=self.url(), jira_email="user@example.test",
                     jira_api_token="tok-cloud")
        self.assertEqual(p.returncode, 0, p.stderr)
        basic = "Basic " + base64.b64encode(b"user@example.test:tok-cloud").decode()
        self.assertEqual(_Stub.seen[-1], ("/rest/api/3/myself", basic))

        p = self.cli("confluence", "whoami", confluence_base_url=self.url("/wiki"),
                     confluence_api_token="pat-conf")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(_Stub.seen[-1], ("/wiki/rest/api/user/current", "Bearer pat-conf"))
        self.assertIn("Stub User", p.stdout)

    def test_cli_max_flag(self) -> None:
        p = self.cli("jira", "search", "project = PROJ ORDER BY updated DESC", "--max", "7",
                     jira_base_url=self.url(), jira_api_token="pat-max")
        self.assertEqual(p.returncode, 0, p.stderr)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(_Stub.seen[-1][0]).query)
        self.assertEqual(query["maxResults"], ["7"])
        self.assertEqual(query["jql"], ["project = PROJ ORDER BY updated DESC"])

        p = self.cli("confluence", "children", "12345", "--max=9",
                     confluence_base_url=self.url("/wiki"), confluence_api_token="pat-max")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(_Stub.seen[-1][0], "/wiki/rest/api/content/12345/child/page?limit=9")

        for bad in ("0", "many"):
            with self.subTest(value=bad):
                p = self.cli("jira", "search", "project = PROJ", "--max", bad,
                             jira_base_url=self.url(), jira_api_token="pat-max")
                self.assertEqual(p.returncode, 1)
                self.assertIn("--max", p.stderr)

    def test_confluence_reuses_the_jira_cloud_token_only_on_the_same_origin(self) -> None:
        jira = {"jira_base_url": self.url(), "jira_email": "user@example.test", "jira_api_token": "tok-shared"}
        p = self.cli("confluence", "whoami", confluence_base_url=self.url("/wiki"), **jira)
        self.assertEqual(p.returncode, 0, p.stderr)
        basic = "Basic " + base64.b64encode(b"user@example.test:tok-shared").decode()
        self.assertEqual(_Stub.seen[-1][1], basic)

        with self.subTest(case="different port"):
            p = self.cli("confluence", "whoami", confluence_base_url=self.url("/wiki", port=self.port + 1),
                         **jira)
            self.assertEqual(p.returncode, 1)
            self.assertIn("API token configured", p.stderr)
        with self.subTest(case="Jira Server/DC (no email)"):
            p = self.cli("confluence", "whoami", confluence_base_url=self.url("/wiki"),
                         jira_base_url=self.url(), jira_api_token="pat-jira")
            self.assertEqual(p.returncode, 1)
            self.assertIn("API token configured", p.stderr)
        self.assertEqual(len(_Stub.seen), 1)

    def test_cli_keeps_its_data_in_magician_data(self) -> None:
        mdata = self.tmp / "magician-data"
        p = self.cli("jira", "myself", jira_base_url=self.url(), jira_api_token="pat-data",
                     MAGICIAN_DATA=str(mdata))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((mdata / "jira-last-call").is_file())
        self.assertFalse((self.data / "jira-last-call").exists())


class NeighbourContractTests(unittest.TestCase):
    def test_session_start_does_not_read_dotenv(self) -> None:
        """PRIVACY.md promises that stack detection never reads dotenv files: session-start.sh must
        not name one, bare, quoted or at the end of a path."""
        text = (ROOT / "scripts" / "session-start.sh").read_text(encoding="utf-8")
        m = DOTENV.search(text)
        self.assertIsNone(m, f"session-start.sh reads a project dotenv file: {m.group(0) if m else ''}")

    def test_hook_scripts_do_not_read_dotenv(self) -> None:
        """The same for every other script in hooks.json or monitors.json: credentials reach the
        session only through the userConfig bridge, never from a project's dotenv files. The guard is
        exempt because it names the file only to block commands that read it."""
        names = set()
        for config in (ROOT / "hooks" / "hooks.json", ROOT / "monitors" / "monitors.json"):
            names |= set(re.findall(r"/scripts/([\w-]+\.sh)", config.read_text(encoding="utf-8")))
        names -= {"session-start.sh", "destructive-guard.sh"}
        self.assertTrue(names, "no other hook scripts found")
        for name in sorted(names):
            with self.subTest(script=name):
                m = DOTENV.search((ROOT / "scripts" / name).read_text(encoding="utf-8"))
                self.assertIsNone(m, f"{name} reads a project dotenv file: {m.group(0) if m else ''}")

    def test_dotenv_pattern_matches_reads_not_lookalikes(self) -> None:
        """Self-check for DOTENV. The filename is filled in at runtime; the old pattern missed every
        quoted or path-qualified form in `reads`."""
        name = "." + "env"
        reads = ('. "$CWD/{f}"', 'grep -h KEY "$HERE/{f}"', 'done < "$DIR/{f}"', "source ./{f}",
                 'cat "{f}"', "cat {f}", "set -a; . {f}; set +a", "for x in {f}.*; do",
                 'cat "$ROOT/{f}.local"', "x=$(cat {f})", "v=`cat {f}`", "done <{f}", "{f}",
                 "cat {f}.production.local | wc -l", 'for x in "$CWD"/{f}*; do', "files=({f})",
                 "cat {{{f},{f}.local}}", "cat {f}>copy")
        lookalikes = ("cat {f}rc", "echo {f}ironment", "sort env", "ls venv",
                      "load dotenv files", "dotenv", 'ENV_FILE="$CLAUDE_ENV_FILE"', "echo $ENV_FILE",
                      "x{f}", "config{f}.js", '"$ROOT/{f}/bin/python"', "files=({f}rc)")
        for template in reads:
            with self.subTest(read=template):
                self.assertIsNotNone(DOTENV.search(template.format(f=name)))
        for template in lookalikes:
            with self.subTest(lookalike=template):
                self.assertIsNone(DOTENV.search(template.format(f=name)))

    def test_sentinel_secret_scan_prints_no_values(self) -> None:
        text = (ROOT / "skills" / "sentinel" / "SKILL.md").read_text(encoding="utf-8")
        scans = [line for line in text.splitlines() if line.lstrip().startswith("git log") and "-G" in line]
        self.assertTrue(scans, "sentinel has no git-history secret scan")
        for line in scans:
            with self.subTest(line=line[:60]):
                self.assertIn("--name-only", line)
                self.assertIsNone(re.search(r"(?<!\S)-p(?!\S)", line), "the scan prints diffs (-p)")


if __name__ == "__main__":
    unittest.main()

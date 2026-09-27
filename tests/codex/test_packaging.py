import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _main import main_source


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE_FILE = REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"
SENTINEL = "sentinel-token-7f3a"
FAKE_CURL = """#!/bin/sh
# Records argv (one per line) and stdin, then answers like curl with -w '\\n%{http_code}'.
: > "$FAKE_CURL_LOG/argv"
for arg in "$@"; do printf '%s\\n' "$arg" >> "$FAKE_CURL_LOG/argv"; done
cat > "$FAKE_CURL_LOG/stdin"
printf '{}\\n200'
"""


def _load_builder():
    path = REPOSITORY_ROOT / ".codex-plugin" / "scripts" / "build_package.py"
    spec = importlib.util.spec_from_file_location("magician_codex_build_package", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _regular_files(directory: Path) -> list:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name != ".DS_Store" and not path.name.endswith(".pyc")
    )


def _marketplace_plugin_root() -> Path:
    marketplace = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    entry = marketplace["plugins"][0]
    source = entry["source"]

    assert source["source"] == "local"
    assert source["path"] == "./plugins/magician"
    return (MARKETPLACE_FILE.parent.parent.parent / source["path"]).resolve()


class CodexPackagingTests(unittest.TestCase):
    def test_release_version_comes_from_main(self) -> None:
        main = main_source()
        template = json.loads(
            (REPOSITORY_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_manifest = json.loads(
            (main / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_marketplace = json.loads(
            (main / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        packaged_manifest = json.loads(
            (_marketplace_plugin_root() / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertNotIn(
            "version", template, "the Codex template must stay version-free; main is authoritative"
        )
        version = claude_manifest["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertNotIn(
            "version",
            claude_marketplace["plugins"][0],
            "Claude marketplace entry must stay version-free; plugin.json is authoritative",
        )
        self.assertEqual(packaged_manifest["version"], version)

        changelog = (main / "CHANGELOG.md").read_text(encoding="utf-8")
        changelog_version = re.search(r"(?m)^## \[([^]]+)\]", changelog)
        self.assertIsNotNone(changelog_version)
        self.assertEqual(changelog_version.group(1), version)

    def test_main_marketplace_points_at_this_branch(self) -> None:
        main = main_source()
        marketplace = json.loads(
            (main / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        repository = json.loads(
            (main / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["repository"]
        self.assertEqual(marketplace["name"], "magician")
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "magician")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        source = entry["source"]

        self.assertEqual(source["source"], "git-subdir")
        self.assertEqual(source["ref"], "codex-plugin")
        self.assertEqual(source["path"], "./plugins/magician")
        self.assertEqual(source["url"], repository + ".git")
        self.assertTrue((REPOSITORY_ROOT / source["path"]).is_dir())

    def test_codex_package_uses_codex_specific_model_lore(self) -> None:
        authoring_lore = REPOSITORY_ROOT / ".codex-plugin" / "lore"
        plugin_lore = _marketplace_plugin_root() / "lore"

        for name in ("models.md", "model-behavior.md"):
            with self.subTest(name=name):
                codex_source = (authoring_lore / name).read_text(encoding="utf-8")
                packaged = (plugin_lore / name).read_text(encoding="utf-8")
                claude_source = (main_source() / "lore" / name).read_text(encoding="utf-8")

                self.assertEqual(packaged, codex_source)
                self.assertNotEqual(codex_source, claude_source)

        models = (plugin_lore / "models.md").read_text(encoding="utf-8").lower()
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
            with self.subTest(model=model):
                self.assertIn(model, models)
        for claude_only_term in ("claude-", "opus 5", "fable 5", "ultracode"):
            with self.subTest(claude_only_term=claude_only_term):
                self.assertNotIn(claude_only_term, models)

    def test_marketplace_points_to_a_dedicated_package(self) -> None:
        plugin_root = _marketplace_plugin_root()

        self.assertEqual(plugin_root, REPOSITORY_ROOT / "plugins" / "magician")
        self.assertFalse(plugin_root.is_symlink())
        self.assertTrue((plugin_root / ".codex-plugin" / "plugin.json").is_file())

    def test_package_is_self_contained_and_has_no_symlinks(self) -> None:
        plugin_root = _marketplace_plugin_root()
        symlinks = [path for path in plugin_root.rglob("*") if path.is_symlink()]
        self.assertEqual(symlinks, [])

        for required in (
            "skills/almanac/SKILL.md",
            "skills/project-context/SKILL.md",
            "skills/project-context/scripts/detect_project_context.py",
            "source-skills/almanac/SKILL.md",
            "references/codex-adapter.md",
            "hooks/codex-hooks.json",
            "scripts/codex-destructive-guard.sh",
            "scripts/codex_destructive_guard.py",
            "bin/kg",
            "bin/ctx",
            "bin/jira",
            "bin/confluence",
        ):
            with self.subTest(required=required):
                self.assertTrue((plugin_root / required).is_file(), required)

    def test_manifest_components_are_cache_contained(self) -> None:
        plugin_root = _marketplace_plugin_root()
        manifest_file = plugin_root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        self.assertEqual(manifest["skills"], "./skills/")

        for field in ("skills", "hooks"):
            with self.subTest(field=field):
                component = (plugin_root / manifest[field]).resolve()
                self.assertTrue(
                    component.is_relative_to(plugin_root),
                    f"{field} resolves outside the cached plugin root: {component}",
                )
                self.assertTrue(
                    component.exists(), f"missing declared {field} component: {component}"
                )

        adapters = list((plugin_root / manifest["skills"]).glob("*/SKILL.md"))
        self.assertEqual(len(adapters), 26)
        source_skills = list((plugin_root / "source-skills").glob("*/SKILL.md"))
        self.assertEqual(len(source_skills), 25)

    def test_generated_package_is_synchronized(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPOSITORY_ROOT / ".codex-plugin" / "scripts" / "build_package.py"),
                "--source",
                str(main_source()),
                "--check",
            ],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_codex_clis_keep_secrets_out_of_process_arguments(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("jira", "confluence"):
            with self.subTest(name=name):
                text = (plugin_root / "bin" / name).read_text(encoding="utf-8")
                self.assertIn('os.environ.get("MAGICIAN_HOME")', text)
                self.assertIn('os.environ["CODEX_HOME"]', text)
                self.assertIn('".codex", "magician"', text)
                self.assertNotIn('os.environ.get("CLAUDE_PLUGIN_DATA")', text)
                # Structural (ast) check shared with the build: no secret can reach curl's argv.
                _load_builder().assert_stdin_secret(plugin_root / "bin" / name, text)

    def test_stdin_secret_check_rejects_every_argv_form(self) -> None:
        builder = _load_builder()
        text = (_marketplace_plugin_root() / "bin" / "jira").read_text(encoding="utf-8")
        anchor = '"-X", method, "-H", "@-"]'
        self.assertIn(anchor, text)
        mutations = {
            "f-string": '"-X", method, "-H", "@-", "-H", f"Authorization: {_auth()}"]',
            "percent": '"-X", method, "-H", "@-", "-H", "Authorization: %s" % _auth()]',
            "concat": '"-X", method, "-H", "@-", "-H", "Authorization: " + _auth()]',
            "token": '"-X", method, "-H", "@-", "-u", TOKEN]',
            "no-stdin": '"-X", method]',
        }
        for label, replacement in mutations.items():
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    builder.assert_stdin_secret(Path("jira"), text.replace(anchor, replacement))
        with self.assertRaises(RuntimeError):
            builder.assert_stdin_secret(Path("jira"), text.replace("input=headers", "input=None"))

    def _run_cli(self, name: str, env: dict, *args: str) -> tuple:
        """Run a packaged CLI against a fake curl; return (returncode, argv lines, stdin, stderr)."""
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            fake_bin = work / "fakebin"
            fake_bin.mkdir()
            curl = fake_bin / "curl"
            curl.write_text(FAKE_CURL, encoding="utf-8")
            curl.chmod(0o755)
            (work / "state").mkdir()
            clean = {
                "PATH": f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
                "HOME": str(work),
                "MAGICIAN_HOME": str(work / "state"),
                "FAKE_CURL_LOG": str(work),
                f"{name.upper()}_MIN_INTERVAL_MS": "0",
                f"{name.upper()}_CACHE_TTL": "0",
            }
            result = subprocess.run(
                [sys.executable, str(_marketplace_plugin_root() / "bin" / name), *args],
                env={**clean, **env},
                text=True,
                capture_output=True,
                check=False,
            )
            argv_file, stdin_file = work / "argv", work / "stdin"
            argv = argv_file.read_text(encoding="utf-8").splitlines() if argv_file.exists() else []
            stdin = stdin_file.read_text(encoding="utf-8") if stdin_file.exists() else ""
            return result.returncode, argv, stdin, result.stderr

    def test_packaged_clis_send_the_token_on_stdin_only(self) -> None:
        cases = {
            "jira": ({"JIRA_BASE_URL": "https://jira.example.test", "JIRA_API_TOKEN": SENTINEL}, ("raw", "GET", "myself")),
            "confluence": (
                {"CONFLUENCE_BASE_URL": "https://wiki.example.test", "CONFLUENCE_API_TOKEN": SENTINEL},
                ("raw", "GET", "user/current"),
            ),
        }
        for name, (env, args) in cases.items():
            with self.subTest(name=name):
                code, argv, stdin, stderr = self._run_cli(name, env, *args)
                self.assertEqual(code, 0, stderr)
                self.assertTrue(argv, "fake curl was not called")
                self.assertNotIn(SENTINEL, "\n".join(argv))
                self.assertIn(f"Authorization: Bearer {SENTINEL}", stdin)
                self.assertIn("@-", argv)

    def test_each_codex_credential_variable_maps_to_its_setting(self) -> None:
        def basic(email: str, token: str) -> str:
            return "Authorization: Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

        for prefix, name, args in (
            ("JIRA", "jira", ("raw", "GET", "myself")),
            ("CONFLUENCE", "confluence", ("raw", "GET", "user/current")),
        ):
            base = f"https://{name}-host.example.test"
            for token_var in (f"{prefix}_API_TOKEN", f"{prefix}_PAT", f"{prefix}_PROD_PAT"):
                with self.subTest(name=name, variable=token_var):
                    code, argv, stdin, stderr = self._run_cli(
                        name, {f"{prefix}_BASE_URL": base, token_var: SENTINEL}, *args
                    )
                    self.assertEqual(code, 0, stderr)
                    self.assertTrue(argv[-1].startswith(base + "/"), argv[-1])
                    self.assertIn(f"Authorization: Bearer {SENTINEL}", stdin)
            with self.subTest(name=name, variable=f"{prefix}_EMAIL"):
                code, argv, stdin, stderr = self._run_cli(
                    name,
                    {f"{prefix}_BASE_URL": base, f"{prefix}_API_TOKEN": SENTINEL, f"{prefix}_EMAIL": "me@example.test"},
                    *args,
                )
                self.assertEqual(code, 0, stderr)
                self.assertIn(basic("me@example.test", SENTINEL), stdin)
            with self.subTest(name=name, variable=f"{prefix}_BASE_URL missing"):
                code, argv, _stdin, stderr = self._run_cli(name, {f"{prefix}_API_TOKEN": SENTINEL}, *args)
                self.assertNotEqual(code, 0)
                self.assertEqual(argv, [])
                self.assertIn(f"{prefix}_BASE_URL", stderr)
                self.assertNotIn("/plugin configure", stderr)

        with self.subTest(name="confluence falls back to the Cloud Jira token and email"):
            code, argv, stdin, stderr = self._run_cli(
                "confluence",
                {
                    "CONFLUENCE_BASE_URL": "https://site.example.test/wiki",
                    "JIRA_BASE_URL": "https://site.example.test",
                    "JIRA_EMAIL": "me@example.test",
                    "JIRA_PAT": SENTINEL,
                },
                "raw", "GET", "user/current",
            )
            self.assertEqual(code, 0, stderr)
            self.assertTrue(argv[-1].startswith("https://site.example.test/wiki/"), argv[-1])
            self.assertIn(basic("me@example.test", SENTINEL), stdin)
        with self.subTest(name="no fallback to a Jira token on another host"):
            code, argv, _stdin, _stderr = self._run_cli(
                "confluence",
                {
                    "CONFLUENCE_BASE_URL": "https://wiki.example.test",
                    "JIRA_BASE_URL": "https://jira.example.test",
                    "JIRA_EMAIL": "me@example.test",
                    "JIRA_API_TOKEN": SENTINEL,
                },
                "raw", "GET", "user/current",
            )
            self.assertNotEqual(code, 0)
            self.assertEqual(argv, [])

    def test_packaged_executables_keep_their_exec_bit(self) -> None:
        plugin_root = _marketplace_plugin_root()
        executables = _regular_files(plugin_root / "bin") + _regular_files(plugin_root / "scripts")
        self.assertTrue(executables)
        for path in executables:
            with self.subTest(path=path.name):
                self.assertTrue(os.access(path, os.X_OK), f"{path} is not executable")

    def test_codex_stateful_clis_never_default_to_claude_state(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("jira", "confluence", "kg", "ctx"):
            with self.subTest(name=name):
                text = (plugin_root / "bin" / name).read_text(encoding="utf-8")
                self.assertIn("CODEX_HOME", text)
                self.assertNotIn('os.path.join(HOME, ".claude", "magician")', text)
                self.assertNotIn("$HOME/.claude/magician", text)
                self.assertNotIn("CLAUDE_PLUGIN_DATA", text)
                self.assertNotIn("MAGICIAN_DATA", text)

    def test_codex_clis_read_credentials_from_the_environment(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for path in _regular_files(plugin_root / "bin"):
            with self.subTest(bin=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("CLAUDE_PLUGIN_OPTION_", text)
                self.assertNotIn("/plugin configure", text)
                self.assertNotIn("MAGICIAN_USERCONFIG_BRIDGE", text)
        jira = (plugin_root / "bin" / "jira").read_text(encoding="utf-8")
        confluence = (plugin_root / "bin" / "confluence").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("JIRA_API_TOKEN")', jira)
        self.assertIn('os.environ.get("JIRA_PAT")', jira)
        self.assertIn('os.environ.get("CONFLUENCE_API_TOKEN")', confluence)
        self.assertIn('os.environ.get("CONFLUENCE_PAT")', confluence)
        for text in (jira, confluence):
            self.assertNotIn("CONFIG_LOADED", text)
            self.assertNotIn("settings aren't loaded", text)
            self.assertNotIn("the Codex build replaces", text)

    def test_codex_facing_docs_never_send_users_to_plugin_configure(self) -> None:
        plugin_root = _marketplace_plugin_root()
        documents = list((plugin_root / "skills").rglob("*.md")) + list((plugin_root / "references").glob("*.md"))
        self.assertTrue(documents)
        for document in documents:
            with self.subTest(document=document.relative_to(plugin_root).as_posix()):
                self.assertNotIn("/plugin configure", document.read_text(encoding="utf-8"))

    def test_claude_only_helpers_are_not_shipped(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("magician-ui", "magician-statusline"):
            with self.subTest(name=name):
                self.assertFalse((plugin_root / "bin" / name).exists())
        self.assertTrue((main_source() / "bin" / "kg").is_file())

    def test_jira_and_confluence_adapters_override_plugin_option_setup(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("jira", "confluence"):
            with self.subTest(name=name):
                text = (plugin_root / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(
                    "Ignore source instructions about plugin options/userConfig; in Codex, "
                    "credentials come only from the environment variables above.",
                    text,
                )


if __name__ == "__main__":
    unittest.main()

"""magician-scan must report credential findings without printing the secret value, answer
-h/--help with its usage, and refuse a path that does not exist instead of reporting it clean."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "tools" / "magician-scan"


def _run(args, home, cwd=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LC_ALL": "C"}
    return subprocess.run([str(SCAN), *args], capture_output=True, text=True, env=env, cwd=cwd, timeout=30)


class MagicianScanRedactionTests(unittest.TestCase):
    def test_credential_values_are_redacted(self):
        value = "placeholder" + "value" + "1234"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "settings.py").write_text(
                'api_key = "%s"\naws_secret_access_key=%s\n' % (value, value))
            proc = _run([tmp], tmp)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("hardcoded credential", proc.stdout)
        self.assertIn("AWS credential", proc.stdout)
        self.assertIn("<redacted>", proc.stdout)
        self.assertNotIn(value, proc.stdout)

    def test_clean_folder_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "app.py").write_text("print('hello')\n")
            proc = _run([tmp], tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No security issues found.", proc.stdout)

    def test_no_argument_scans_the_current_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "page.js").write_text("el.innerHTML = input;\n")
            proc = _run([], tmp, cwd=tmp)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("security scan of: .", proc.stdout)
        self.assertIn("innerHTML assignment", proc.stdout)


class MagicianScanCredentialSprawlTests(unittest.TestCase):
    """Keys harvested from Docker images, LiteLLM deployments and unpacked mobile bundles: the scan
    reports a key-named ENV/ARG, environment entry, api_key or bundle string with a literal value,
    names the file kind, and never prints the value; variable references and URLs are not keys."""

    KEY = "sk-" + "abcdefghijklmnopqrstuvwxyz0123"

    def _scan(self, files: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                Path(tmp, name).write_text(text)
            return _run([tmp], tmp)

    def test_dockerfile_and_compose_keys_are_reported_and_redacted(self):
        proc = self._scan({
            "Dockerfile": "FROM x\nENV OPENAI_API_KEY=%s\nARG DB_PASSWORD ${DB_PASSWORD}\n"
                          "ENV PATH=/usr/local/bin:/usr/bin:/bin\nENV TOKEN_URL=https://example.test/token/x\n" % self.KEY,
            "docker-compose.yml": "services:\n  api:\n    environment:\n      - API_TOKEN=%s\n"
                                  "      SECRET_KEY: ${SECRET_KEY}\n      PORT: 8080\n" % self.KEY,
        })
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.count("[key in Dockerfile ENV/ARG]"), 1)
        self.assertEqual(proc.stdout.count("[key in docker-compose environment]"), 1)
        self.assertIn("OPENAI_API_KEY = <redacted>", proc.stdout)
        self.assertIn("API_TOKEN = <redacted>", proc.stdout)
        self.assertNotIn(self.KEY, proc.stdout)
        for quiet in ("DB_PASSWORD", "TOKEN_URL", "SECRET_KEY", "PATH"):
            self.assertNotIn(quiet + " = ", proc.stdout, quiet)

    def test_litellm_config_literal_api_key(self):
        text = ("model_list:\n  - model_name: gpt\n    litellm_params:\n      api_key: %s\n"
                "  - litellm_params:\n      api_key: os.environ/OPENAI_API_KEY\n" % self.KEY)
        for name in ("litellm_config.yaml", "config.yaml"):
            with self.subTest(name=name):
                proc = self._scan({name: text})
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertEqual(proc.stdout.count("[key in LiteLLM config]"), 1)
                self.assertIn("api_key = <redacted>", proc.stdout)
                self.assertNotIn(self.KEY, proc.stdout)
        proc = self._scan({"settings.yaml": "api_key: %s\n" % self.KEY})
        self.assertNotIn("LiteLLM", proc.stdout, "only LiteLLM-named config files use the api_key rule")

    def test_unpacked_mobile_bundle_strings(self):
        proc = self._scan({
            "strings.xml": '<resources>\n<string name="app_name">Demo</string>\n'
                           '<string name="maps_api_key">%s</string>\n</resources>\n' % self.KEY,
            "Info.plist": "<plist><dict>\n<key>CFBundleName</key><string>Demo</string>\n"
                          "<key>StripeSecretKey</key>\n<string>%s</string>\n</dict></plist>\n" % self.KEY,
        })
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("[key in Android strings.xml]", proc.stdout)
        self.assertIn("maps_api_key = <redacted>", proc.stdout)
        self.assertIn("[key in iOS Info.plist]", proc.stdout)
        self.assertIn("StripeSecretKey = <redacted>", proc.stdout)
        self.assertNotIn(self.KEY, proc.stdout)
        self.assertNotIn("app_name", proc.stdout)
        self.assertNotIn("CFBundleName", proc.stdout)

    def test_clean_deployment_files_pass(self):
        proc = self._scan({
            "Dockerfile": "FROM x\nARG API_KEY\nENV API_KEY=${API_KEY}\nENV HOME=/root\n",
            "docker-compose.yml": "services:\n  api:\n    environment:\n      - API_KEY=${API_KEY}\n",
            "Info.plist": "<plist><dict><key>CFBundleName</key><string>Demo</string></dict></plist>\n",
        })
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No security issues found.", proc.stdout)


class MagicianScanArgumentTests(unittest.TestCase):
    def test_help_prints_usage_and_exits_zero(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                proc = _run([flag], tmp, cwd=tmp)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual(proc.stderr, "")
                self.assertIn("Usage: magician-scan [path]", proc.stdout)
                for section in ("Arguments:", "Options:", "Exit codes:", "-h, --help"):
                    self.assertIn(section, proc.stdout)
                self.assertNotIn("No security issues found.", proc.stdout)
                self.assertNotIn("security scan of:", proc.stdout)

    def test_missing_path_fails_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "no-such-dir")
            proc = _run([missing], tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("magician-scan: no such file or directory: " + missing, proc.stderr)

    def test_unknown_option_fails_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(["--json"], tmp, cwd=tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("magician-scan: unknown option '--json'", proc.stderr)
        self.assertIn("--help", proc.stderr)

    def test_existing_path_that_looks_like_an_option_is_still_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "-src").mkdir()
            Path(tmp, "-src", "app.py").write_text("print('hello')\n")
            proc = _run(["-src"], tmp, cwd=tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No security issues found.", proc.stdout)


if __name__ == "__main__":
    unittest.main()

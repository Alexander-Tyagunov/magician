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

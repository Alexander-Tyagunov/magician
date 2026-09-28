"""magician-scan must report credential findings without printing the secret value."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "bin" / "magician-scan"


class MagicianScanRedactionTests(unittest.TestCase):
    def test_credential_values_are_redacted(self):
        value = "placeholder" + "value" + "1234"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "settings.py").write_text(
                'api_key = "%s"\naws_secret_access_key=%s\n' % (value, value))
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp, "LC_ALL": "C"}
            proc = subprocess.run([str(SCAN), tmp], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("hardcoded credential", proc.stdout)
        self.assertIn("AWS credential", proc.stdout)
        self.assertIn("<redacted>", proc.stdout)
        self.assertNotIn(value, proc.stdout)

    def test_clean_folder_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "app.py").write_text("print('hello')\n")
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp, "LC_ALL": "C"}
            proc = subprocess.run([str(SCAN), tmp], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No security issues found.", proc.stdout)


if __name__ == "__main__":
    unittest.main()

"""Static contract for the experimental Claude Code mod (mods/register.js).

The mod is opt-in (MAGICIAN_MODS=1). It may add a person-decided `ask`, or a deny where the guard's
soft stage names a credential read or code execution that nothing denied; it never answers allow,
and it softens a deny only when the deny is the guard's own (`decided.hook`) and every reason the
guard reports in its all-soft mode (MAGICIAN_GUARD_ALL_SOFT=1, set only by the mod) is blast radius. These tests read files only (and run `node --check` when node is on
PATH); the behavior tests are mods/register.test.ts, run by `claude plugin test`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks" / "hooks.json"
MOD = ROOT / "mods" / "register.js"
MOD_TEST = ROOT / "mods" / "register.test.ts"
GUARD = ROOT / "scripts" / "destructive-guard.sh"
STATUSLINE = ROOT / "tools" / "magician-statusline"
README = ROOT / "README.md"


def _code(src: str) -> str:
    """The module without // line comments and /* */ blocks (string contents are kept)."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in src.splitlines())


def _js_list(src: str, name: str) -> list[str]:
    m = re.search(r"export const " + name + r" = \[(.*?)\n\]", src, flags=re.S)
    assert m, f"{name} not found in register.js"
    return re.findall(r"^\s*'((?:[^'\\]|\\.)*)',?\s*$", m.group(1), flags=re.M)


def _guard_soft_reasons() -> set[str]:
    text = GUARD.read_text(encoding="utf-8")
    reasons = set(re.findall(r'soft_block "([^"]*)"', text))
    reasons.discard("$GIT_SOFT")  # indirection: its values are the git_soft calls below
    reasons.discard("$_gs")  # all-soft mode replays the same git_soft values
    reasons |= set(re.findall(r'git_soft "([^"]+)"', text))
    return reasons


class ModWiringTests(unittest.TestCase):
    def test_hooks_json_names_the_module(self) -> None:
        config = json.loads(HOOKS.read_text(encoding="utf-8"))
        self.assertEqual(config.get("modules"), ["../mods/register.js"])
        target = (HOOKS.parent / config["modules"][0]).resolve()
        self.assertEqual(target, MOD.resolve())
        self.assertTrue(target.is_file())
        self.assertTrue(MOD_TEST.is_file(), "the claude plugin test file is missing")

    def test_module_is_an_es_module_exporting_register(self) -> None:
        src = MOD.read_text(encoding="utf-8")
        self.assertRegex(src, r"(?m)^export function register\(on\)", "register must be exported")
        self.assertNotRegex(_code(src), r"\brequire\(|\bimport\(", "ES module imports only")


class OptInTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = MOD.read_text(encoding="utf-8")

    def test_flag_is_read_with_the_env_api(self) -> None:
        self.assertIn("$.env.get('MAGICIAN_MODS')) === '1'", self.src)

    def test_every_hook_checks_the_flag(self) -> None:
        body = self.src.split("export function register(on) {", 1)[1]
        blocks = re.split(r"\n  on\('", body)[1:]
        self.assertGreaterEqual(len(blocks), 8)
        for block in blocks:
            with self.subTest(hook=block.split("'", 1)[0]):
                self.assertIn("isEnabled($)", block)


class NeverApprovesTests(unittest.TestCase):
    def test_no_allow_literal_in_code(self) -> None:
        code = _code(MOD.read_text(encoding="utf-8"))
        self.assertNotRegex(code, r"""['"`]allow['"`]""", "the mod must never answer allow")

    def test_every_own_decision_is_ask_with_person_decider_or_deny(self) -> None:
        code = _code(MOD.read_text(encoding="utf-8"))
        decisions = re.findall(r"decision: '([a-z]+)'", code)
        self.assertTrue(decisions)
        self.assertEqual(set(decisions), {"ask", "deny"})
        for m in re.finditer(r"decision: 'ask'", code):
            self.assertIn("decider: 'person'", code[m.end():m.end() + 40])

    def test_catch_keeps_a_prior_deny(self) -> None:
        code = _code(MOD.read_text(encoding="utf-8"))
        catch = code.split(".catch(", 1)[1].split("\n  })", 1)[0]
        self.assertIn("next.called", catch)
        self.assertIn("prior.decision === 'deny'", catch)


class AttributionTests(unittest.TestCase):
    """A deny is attributed to the guard by its origin field, never by matching reason text."""

    def setUp(self) -> None:
        self.code = _code(MOD.read_text(encoding="utf-8"))

    def test_origin_field_is_required(self) -> None:
        self.assertIn("decided.hook === 'PreToolUse'", self.code)

    def test_includes_is_list_membership_only(self) -> None:
        # Every `.includes(` call is on one of the two reason lists (exact membership) or on an
        # array literal; never on a string such as decided.reason.
        receivers = re.findall(r"([\w\]\)]+)\.includes\(", self.code)
        self.assertTrue(receivers)
        for r in receivers:
            with self.subTest(receiver=r):
                self.assertIn(r, {"CONFIRM_REASONS", "KEEP_DENY_REASONS", "]"})
        self.assertNotRegex(self.code, r"reason[\w.]*\)?\s*\.(includes|indexOf|startsWith|endsWith|search|match)\(decided")
        self.assertNotRegex(self.code, r"decided\.reason[^\n]*\.(includes|indexOf|search|match)\(")


class AllSoftModeTests(unittest.TestCase):
    """MAGICIAN_GUARD_ALL_SOFT=1 is set by the mod only, in the env of its own run of the guard."""

    SET = re.compile(r"""MAGICIAN_GUARD_ALL_SOFT['"]?\s*[:=]\s*['"]?1""")

    @staticmethod
    def _strip_comments(path: Path, text: str) -> str:
        if path.suffix in {".js", ".ts", ".mjs", ".tsx"}:
            return _code(text)
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))

    def test_only_the_mod_sets_it(self) -> None:
        setters = []
        for path in ROOT.rglob("*"):
            rel = path.relative_to(ROOT)
            if not path.is_file() or rel.parts[0] in {".git", "tests", "dist", "evals"} or path.suffix == ".md":
                continue
            if path == MOD_TEST:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "MAGICIAN_GUARD_ALL_SOFT" in text and self.SET.search(self._strip_comments(path, text)):
                setters.append(str(rel))
        self.assertEqual(setters, ["mods/register.js"])

    def test_mod_sets_it_in_the_guard_run_env(self) -> None:
        code = _code(MOD.read_text(encoding="utf-8"))
        run = re.search(r"\$\.process\.run\(\['bash', \$\.plugin\.root \+ '/scripts/destructive-guard\.sh'\], \{(.*?)\}\)", code, flags=re.S)
        self.assertIsNotNone(run, "the guard run was not found")
        self.assertIn("env: { MAGICIAN_GUARD_ALL_SOFT: '1' }", run.group(1))
        self.assertEqual(code.count("MAGICIAN_GUARD_ALL_SOFT"), 1)

    def test_hooks_json_does_not_set_it(self) -> None:
        self.assertNotIn("MAGICIAN_GUARD_ALL_SOFT", HOOKS.read_text(encoding="utf-8"))

    def test_guard_only_reads_it(self) -> None:
        text = GUARD.read_text(encoding="utf-8")
        code = self._strip_comments(GUARD, text)
        self.assertIn('[ "${MAGICIAN_GUARD_ALL_SOFT:-}" = 1 ] && ALL_SOFT=1', code)
        self.assertNotRegex(code, r"(export\s+)?MAGICIAN_GUARD_ALL_SOFT=")


class GuardParityTests(unittest.TestCase):
    def test_reason_lists_cover_the_guard_soft_set_exactly(self) -> None:
        src = MOD.read_text(encoding="utf-8")
        confirm, keep = set(_js_list(src, "CONFIRM_REASONS")), set(_js_list(src, "KEEP_DENY_REASONS"))
        self.assertFalse(confirm & keep, "a reason is in both lists")
        self.assertEqual(confirm | keep, _guard_soft_reasons())

    def test_confirm_set_is_the_blast_radius_class(self) -> None:
        confirm = _js_list(MOD.read_text(encoding="utf-8"), "CONFIRM_REASONS")
        for r in confirm:
            with self.subTest(reason=r):
                self.assertRegex(r, r"^(git push --force|git reset --hard|rm -rf|find -delete|truncate)")

    def test_rot_thresholds_match_the_statusline(self) -> None:
        sl = STATUSLINE.read_text(encoding="utf-8")
        rot = re.search(r"def _rot\(pct\):(.*?)\n\n", sl, flags=re.S).group(1)
        severe, warn = (int(x) for x in re.findall(r"pct >= (\d+)", rot))
        src = MOD.read_text(encoding="utf-8")
        self.assertIn(f"export const ROT_WARN = {warn}", src)
        self.assertIn(f"export const ROT_SEVERE = {severe}", src)


class DocsTests(unittest.TestCase):
    def test_readme_documents_the_opt_in(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("Mods (experimental)", text)
        self.assertIn("MAGICIAN_MODS=1", text)
        self.assertIn("2.1.304", text)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class NodeTests(unittest.TestCase):
    def test_node_check(self) -> None:
        r = subprocess.run(["node", "--check", str(MOD)], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pure_helpers(self) -> None:
        script = (
            "const m = await import(process.argv[1]);"
            "const out = {"
            " tf: !!m.extraConfirm('terraform -chdir=x apply'),"
            " kd: !!m.extraConfirm('kubectl -n prod delete pod x'),"
            " plan: !!m.extraConfirm('terraform plan'),"
            " get: !!m.extraConfirm('kubectl get pods'),"
            " st: m.parseSessionState('Phase 2: Planning\\nPhase 4: Implementation\\nWave 1/3'),"
            " rot: [m.rotWarning(79), m.rotWarning(80), m.rotWarning(92)] };"
            "console.log(JSON.stringify(out));"
        )
        r = subprocess.run(["node", "--input-type=module", "-e", script, MOD.as_uri()],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out["tf"] and out["kd"])
        self.assertFalse(out["plan"] or out["get"])
        self.assertEqual(out["st"], {"phase": "4 Implementation", "wave": "1/3"})
        self.assertEqual(out["rot"], ["", "⚠ context rot", "🔴 context rot"])


if __name__ == "__main__":
    unittest.main()

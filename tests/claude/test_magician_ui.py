"""magician-ui contract — settings change only on an explicit command, and cleanup is exact.

magician-ui is the one magician component that edits Claude Code's user settings. Since 4.15 no hook
calls it: `reconcile` is an inert stub, and `allow` / `automode` add nothing (with --off they are
aliases for `cleanup`). What remains must be exact and bounded:
  * `cleanup` removes magician's allow rules only when cli-ui.json records magician added them (matching
    rules with no record stay, and so do the broad jira/confluence grants when the record is from 4.4.0
    or later, since those versions stripped them), deletes `defaultMode: "auto"` only when cli-ui.json
    records magician set it (and never writes another mode), drops the obsolete env key, and deletes
    only the listed obsolete data files;
  * `enable` touches only `statusLine` and keeps the saved components unless --all, --only or a
    component list is given;
    `disable --purge` removes magician's files and nothing else, and refuses (changing nothing) while
    cleanup still needs cli-ui.json's record, unless --force;
  * a subcommand given an argument it doesn't take, `enable`/`set` naming no known component, or
    --help, changes nothing;
  * settings backups are mode 0600 and at most 3 are kept.
It also covers the renderer's status-folder pruning.

Isolation: every run gets a fully specified environment — HOME, MAGICIAN_HOME, MAGICIAN_SETTINGS,
CLAUDE_PLUGIN_DATA, MAGICIAN_DATA and CLAUDE_ENV_FILE all point into a temp dir (nothing is inherited
from os.environ except PATH), and tests assert the temp settings file is the one that changed while
$HOME/.claude/settings.json is never created.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "bin" / "magician-ui"
RENDERER = ROOT / "bin" / "magician-statusline"
UI_SRC = UI.read_text(encoding="utf-8")


def _list_const(name: str) -> list[str]:
    """Read a list constant from the CLI source without importing it (import would bind real paths)."""
    m = re.search(rf"^{name} = (\[.*?\n?\])$", UI_SRC, re.S | re.M)
    assert m, f"{name} not found in bin/magician-ui"
    return ast.literal_eval(m.group(1))


READONLY_ALLOW = _list_const("READONLY_ALLOW")
ALL = _list_const("ALL")
STALE_ALLOW = _list_const("STALE_ALLOW")
OURS = READONLY_ALLOW + STALE_ALLOW
AUTOMODE_ENV = "CLAUDE_CODE_ENABLE_AUTO_MODE"
# The check scripts/session-start.sh makes before showing its upgrade notice.
NOTICE_RECORD = re.compile(r'"(allow|automode)"\s*:\s*"on"')

# A statusLine entry magician-ui recognises as its own.
OUR_BAR = {"type": "command", "command": "python3 /x/magician/statusline.py", "padding": 0}

# Rules a user wrote — including near-neighbours of magician's entries that must NOT be matched.
USER_RULES = ["Bash(make:*)", "Bash(git status --short)", "WebFetch(domain:example.com)",
              "Bash(jira create:*)", "Read(./docs/**)"]

# Exact obsolete names `cleanup` may delete (relative to a data folder) …
LEGACY = ["access-patterns.json", "patterns.json", "session-start-time.txt",
          "projects/abc123/capsule.md", "projects/abc123/capsule.json",
          "ctx/s1.resume", "ctx/s1.kgnudge", "ctx/s1.mcpnudge", "ctx/s1-mcpnudge-count"]
# … and neighbours that must survive.
KEEP = ["projects/abc123/capsule.consumed", "projects/abc123/learnings.jsonl",
        "projects/abc123/observability.json", "projects/abc123/nested/capsule.md",
        "chronicle/2026-09-01.json", "references.md", "integration-prefs.json",
        "sessions/s1.start", "jira-cache/PROJ-123.json", "ctx/s1.other", "patterns.json.bak",
        "capsule.md"]


class UiCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mui-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.mh = self.tmp / "magician-home"
        self.settings = self.tmp / "cfg" / "settings.json"
        self.plugin_data = self.tmp / "plugin-data"
        self.magician_data = self.tmp / "magician-data"
        self.legacy_data = self.home / ".local" / "share" / "magician"
        self.home.mkdir()
        self.settings.parent.mkdir()
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "MAGICIAN_HOME": str(self.mh),
            "MAGICIAN_SETTINGS": str(self.settings),
            "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
            "MAGICIAN_DATA": str(self.magician_data),
            "CLAUDE_ENV_FILE": str(self.tmp / "env-file"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_COLOR": "1",
        }

    def tearDown(self) -> None:
        # The CLI must only ever touch the temp settings file, never the default path under HOME.
        self.assertFalse((self.home / ".claude" / "settings.json").exists(),
                         "magician-ui wrote $HOME/.claude/settings.json instead of MAGICIAN_SETTINGS")

    # ---- helpers ----
    def ui(self, *args: str, expect: int = 0) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, str(UI), *args], text=True, capture_output=True,
                           env=self.env, cwd=str(self.tmp), check=False, timeout=60)
        self.assertEqual(r.returncode, expect, f"magician-ui {' '.join(args)}: {r.stderr}{r.stdout}")
        return r

    def write_settings(self, data: dict) -> bytes:
        raw = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        self.settings.write_bytes(raw)
        return raw

    def read_settings(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def write_cfg(self, data: dict) -> None:
        self.mh.mkdir(parents=True, exist_ok=True)
        (self.mh / "cli-ui.json").write_text(json.dumps(data), encoding="utf-8")

    def read_cfg(self) -> dict:
        return json.loads((self.mh / "cli-ui.json").read_text(encoding="utf-8"))

    def backups(self) -> list[Path]:
        return sorted(self.settings.parent.glob(self.settings.name + ".bak-magician-ui-*"))

    def legacy_settings(self, default_mode: str | None = "auto") -> dict:
        """Settings an install last updated before 4.4 left: every rule on magician's old list, the
        broad jira/confluence grants included, interleaved with the user's own."""
        allow: list = []
        for i, r in enumerate(OURS):
            allow.append(r)
            if i < len(USER_RULES):
                allow.append(USER_RULES[i])
        perms: dict = {"allow": allow, "deny": ["Read(./.env)"], "ask": ["Bash(git push:*)"]}
        if default_mode is not None:
            perms["defaultMode"] = default_mode
        return {"model": "some-model", "env": {"FOO": "bar", AUTOMODE_ENV: "1"},
                "permissions": perms, "hooks": {"Stop": []}}


class RetiredCommandTests(UiCase):
    def test_help_describes_explicit_commands_only(self) -> None:
        out = self.ui("--help").stdout
        for word in ("cleanup", "disable [--purge [--force]]", "enable", "allow --off", "automode --off"):
            self.assertIn(word, out)
        self.assertIn("no hook calls it", out)
        self.assertFalse(self.mh.exists(), "--help must not create MAGICIAN_HOME")

    def test_reconcile_is_an_inert_stub(self) -> None:
        raw = self.write_settings(self.legacy_settings())
        r = self.ui("reconcile")
        self.assertIn("no longer used", r.stdout)
        self.assertIn("magician-ui cleanup", r.stdout)
        self.assertEqual(self.settings.read_bytes(), raw, "reconcile modified settings")
        self.assertEqual(self.backups(), [])
        self.assertFalse(self.mh.exists(), "reconcile installed a renderer or wrote cli-ui.json")

    def test_allow_and_automode_enable_paths_are_gone(self) -> None:
        raw = self.write_settings({"permissions": {"allow": ["Bash(make:*)"]}})
        for argv in (["allow"], ["allow", "on"], ["automode"], ["automode", "--available"]):
            with self.subTest(argv=argv):
                r = self.ui(*argv)
                self.assertIn("nothing was changed", r.stdout)
                self.assertEqual(self.settings.read_bytes(), raw, f"{argv} wrote settings")
                self.assertEqual(self.backups(), [])
                self.assertFalse((self.mh / "cli-ui.json").exists())

    def test_source_has_no_permission_writers(self) -> None:
        """No code path may add allow rules or set a permission mode."""
        self.assertNotIn("acceptEdits", UI_SRC)
        self.assertNotRegex(UI_SRC, r'\["defaultMode"\]\s*=')
        self.assertNotRegex(UI_SRC, r"allow\.append|_merge_readonly_allow|_set_default_auto")


class CleanupTests(UiCase):
    def test_cleanup_removes_exactly_magicians_entries(self) -> None:
        before = self.legacy_settings(default_mode="auto")
        self.write_settings(before)
        self.write_cfg({"state": "enabled", "voice": "warrior", "allow": "on", "allowVersion": "4.3.0",
                        "automode": "available", "automodeVersion": "4.14.0"})
        r = self.ui("cleanup")
        after = self.read_settings()
        self.assertEqual(after["permissions"]["allow"], USER_RULES, "user rules lost or reordered")
        self.assertEqual(after["permissions"]["deny"], before["permissions"]["deny"])
        self.assertEqual(after["permissions"]["ask"], before["permissions"]["ask"])
        # automode was never recorded as "on", so an "auto" default is the user's and must stay.
        self.assertEqual(after["permissions"].get("defaultMode"), "auto")
        self.assertEqual(after["env"], {"FOO": "bar"})
        for k in ("model", "hooks"):
            self.assertEqual(after[k], before[k])
        self.assertIn(f"removed {len(OURS)} allow rule(s)", r.stdout)
        cfg = self.read_cfg()
        self.assertFalse([k for k in cfg if k.startswith(("allow", "automode"))], cfg)
        self.assertEqual((cfg["state"], cfg["voice"]), ("enabled", "warrior"))
        self.assertIn("permissionsCleanedAt", cfg)

    def test_default_mode_removed_only_when_recorded(self) -> None:
        cases = [  # (recorded automode, defaultMode before, defaultMode expected after)
            ("on", "auto", None),
            ("on", "plan", "plan"),
            ("on", "acceptEdits", "acceptEdits"),
            ("available", "auto", "auto"),
            (None, "auto", "auto"),
            ("off", "auto", "auto"),
        ]
        for recorded, mode, expected in cases:
            with self.subTest(recorded=recorded, mode=mode):
                self.write_settings(self.legacy_settings(default_mode=mode))
                self.write_cfg({} if recorded is None else {"automode": recorded})
                self.ui("cleanup")
                after = self.read_settings()
                self.assertEqual(after["permissions"].get("defaultMode"), expected)
                if mode != "acceptEdits":
                    self.assertNotIn("acceptEdits", self.settings.read_text(encoding="utf-8"),
                                     "cleanup escalated the permission mode")

    def test_off_aliases_run_cleanup(self) -> None:
        for argv in (["allow", "--off"], ["automode", "--off"]):
            with self.subTest(argv=argv):
                self.write_settings(self.legacy_settings(default_mode="auto"))
                self.write_cfg({"allow": "on", "automode": "on", "automodeVersion": "4.14.0"})
                self.ui(*argv)
                after = self.read_settings()
                self.assertEqual(after["permissions"]["allow"], USER_RULES)
                self.assertNotIn("defaultMode", after["permissions"])
                self.assertNotIn("acceptEdits", self.settings.read_text(encoding="utf-8"))
                self.assertEqual(after["env"], {"FOO": "bar"})
                cfg = self.read_cfg()
                self.assertFalse([k for k in cfg if k.startswith(("allow", "automode"))], cfg)

    def test_cleanup_with_nothing_to_remove_writes_nothing(self) -> None:
        raw = self.write_settings({"permissions": {"allow": list(USER_RULES)}, "env": {"FOO": "bar"}})
        r = self.ui("cleanup")
        self.assertIn("not modified", r.stdout)
        self.assertEqual(self.settings.read_bytes(), raw)
        self.assertEqual(self.backups(), [])
        self.assertFalse((self.mh / "cli-ui.json").exists(), "cleanup created cli-ui.json from nothing")

    def test_cleanup_without_settings_file_creates_none(self) -> None:
        self.ui("cleanup")
        self.assertFalse(self.settings.exists())

    def test_backups_are_private_and_bounded(self) -> None:
        self.write_settings(self.legacy_settings())
        old = []
        for i in range(5):  # backups left by earlier versions: world-readable, never pruned
            p = Path(f"{self.settings}.bak-magician-ui-2025010{i}-000000")
            p.write_text("{}\n", encoding="utf-8")
            os.chmod(p, 0o644)
            old.append(p)
        pre = self.settings.read_text(encoding="utf-8")
        os.chmod(self.settings, 0o600)
        self.ui("cleanup")
        baks = self.backups()
        self.assertEqual(len(baks), 3, baks)
        for p in baks:
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600, p.name)
        for p in old[:3]:
            self.assertFalse(p.exists(), f"oldest backup {p.name} not pruned")
        self.assertEqual(baks[-1].read_text(encoding="utf-8"), pre, "newest backup is not the pre-edit file")
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode), 0o600, "settings mode not preserved")

    def test_repeated_edits_keep_at_most_three_backups(self) -> None:
        self.write_settings({"model": "some-model"})
        for _ in range(4):
            self.ui("enable", "--all")
            self.ui("disable")
        baks = self.backups()
        self.assertLessEqual(len(baks), 3)
        self.assertGreaterEqual(len(baks), 1)
        for p in baks:
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600, p.name)
        self.assertEqual(self.read_settings(), {"model": "some-model"})

    def test_invalid_settings_are_refused(self) -> None:
        self.settings.write_text("{not json", encoding="utf-8")
        for argv in (["cleanup"], ["enable", "--all"], ["disable"]):
            with self.subTest(argv=argv):
                self.ui(*argv, expect=1)
                self.assertEqual(self.settings.read_text(encoding="utf-8"), "{not json")
                self.assertEqual(self.backups(), [])

    def test_cleanup_removes_only_listed_legacy_data(self) -> None:
        bases = (self.plugin_data, self.magician_data, self.legacy_data)
        for base in bases:
            for rel in LEGACY + KEEP:
                p = base / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("x", encoding="utf-8")
            (base / "ctx" / "dir.resume").mkdir()          # a directory matching a pattern: kept
        elsewhere = self.tmp / "elsewhere"                   # not a data folder: never scanned
        elsewhere.mkdir()
        (elsewhere / "patterns.json").write_text("x", encoding="utf-8")

        st = self.ui("status").stdout
        self.assertIn(f"{len(LEGACY) * len(bases)} obsolete file(s)", st)

        r = self.ui("cleanup")
        for base in bases:
            for rel in LEGACY:
                with self.subTest(base=base.name, removed=rel):
                    self.assertFalse((base / rel).exists())
                    self.assertIn(str(base / rel), r.stdout, "removed file not reported")
            for rel in KEEP:
                with self.subTest(base=base.name, kept=rel):
                    self.assertTrue((base / rel).exists())
            self.assertTrue((base / "ctx" / "dir.resume").is_dir())
        self.assertTrue((elsewhere / "patterns.json").exists())
        self.assertNotIn("obsolete file", self.ui("status").stdout)

    def test_status_reports_leftovers_and_writes_nothing(self) -> None:
        raw = self.write_settings(self.legacy_settings(default_mode="auto"))
        self.write_cfg({"allow": "on", "automode": "on"})
        cfg_raw = (self.mh / "cli-ui.json").read_bytes()
        out = self.ui("status").stdout
        self.assertIn(f"{len(OURS)} allow rule(s)", out)
        self.assertIn('defaultMode "auto"', out)
        self.assertIn(AUTOMODE_ENV, out)
        self.assertIn("magician-ui cleanup", out)
        self.assertEqual(self.settings.read_bytes(), raw)
        self.assertEqual((self.mh / "cli-ui.json").read_bytes(), cfg_raw)
        self.assertEqual(self.backups(), [])
        self.ui("cleanup")
        self.assertIn("no entries from earlier magician versions", self.ui("status").stdout)

    # A user who answered "Yes, and don't ask again" to `git status` owns exactly Bash(git status:*).
    MATCHING = ["Read", "Bash(git status:*)", "Bash(npm test:*)"]

    def test_cleanup_without_record_keeps_matching_rules(self) -> None:
        for cfg in (None, {"state": "enabled", "voice": "bard"}, {"allow": "off", "allowVersion": "4.14.0"},
                    {"automode": "on"}):
            with self.subTest(cfg=cfg):
                if (self.mh / "cli-ui.json").exists():
                    (self.mh / "cli-ui.json").unlink()
                if cfg is not None:
                    self.write_cfg(cfg)
                raw = self.write_settings({"permissions": {"allow": self.MATCHING + ["Bash(mytool:*)"]}})
                st = self.ui("status").stdout
                self.assertNotIn("added by an earlier magician version", st)
                self.assertIn("3 allow rule(s) match magician's old list", st)
                self.assertIn("magician has no record of adding them", st)
                self.assertIn("`magician-ui cleanup` leaves them", st)

                r = self.ui("cleanup")
                self.assertEqual(self.settings.read_bytes(), raw, "cleanup removed rules magician has no record of")
                self.assertEqual(self.backups(), [])
                kept = [ln for ln in r.stdout.splitlines() if ln.startswith("Kept ")]
                self.assertEqual(len(kept), 1, r.stdout)
                for rule in self.MATCHING:
                    self.assertIn(rule, kept[0])
                self.assertNotIn("Bash(mytool:*)", kept[0])
                self.assertIn("no record of adding them", kept[0])
                self.assertIn("/permissions", kept[0])
                self.assertNotIn("removed", r.stdout)
                self.assertNotIn("no entries from earlier magician versions", r.stdout,
                                 "cleanup says there is nothing and then lists what it kept")

    def test_cleanup_with_record_removes_rules_and_clears_record(self) -> None:
        self.write_settings({"permissions": {"allow": self.MATCHING + ["Bash(mytool:*)"]}})
        self.write_cfg({"state": "enabled", "allow": "on", "allowVersion": "4.14.0"})
        st = self.ui("status").stdout
        self.assertIn("3 allow rule(s) added by an earlier magician version", st)
        self.assertNotIn("no record", st)

        r = self.ui("cleanup")
        self.assertEqual(self.read_settings()["permissions"]["allow"], ["Bash(mytool:*)"])
        self.assertIn("removed 3 allow rule(s): " + ", ".join(self.MATCHING), r.stdout)
        self.assertNotIn("Kept ", r.stdout)
        cfg_text = (self.mh / "cli-ui.json").read_text(encoding="utf-8")
        self.assertFalse([k for k in json.loads(cfg_text) if k.startswith("allow")], cfg_text)
        self.assertIsNone(NOTICE_RECORD.search(cfg_text), "record left: the session-start notice keeps showing")
        self.assertEqual(self.read_cfg()["state"], "enabled")
        self.assertIn("no entries from earlier magician versions", self.ui("status").stdout)

        # The record is gone, so a rule the user adds back later is theirs and a second cleanup keeps it.
        raw = self.write_settings({"permissions": {"allow": ["Bash(mytool:*)", "Bash(git status:*)"]}})
        r = self.ui("cleanup")
        self.assertEqual(self.settings.read_bytes(), raw)
        self.assertIn("Kept 1 allow rule(s)", r.stdout)

    def test_broad_jira_grants_are_kept_when_the_record_is_from_4_4_or_later(self) -> None:
        """4.2 and 4.3 added Bash(jira:*) and Bash(confluence:*); every merge from 4.4.0 on stripped them,
        so after such a merge they can only be the user's."""
        stale = ["Bash(jira:*)", "Bash(confluence:*)"]
        cases = [("4.2.0", []), ("4.3.1", []), ("4.4.0", stale), ("4.14.0", stale), (None, [])]
        for version, kept in cases:
            with self.subTest(allowVersion=version):
                self.write_settings({"permissions": {"allow": stale + ["Read", "Bash(mytool:*)"]}})
                cfg = {"allow": "on"}
                if version:
                    cfg["allowVersion"] = version
                self.write_cfg(cfg)
                st = self.ui("status").stdout
                self.assertIn(f"{3 - len(kept)} allow rule(s) added by an earlier magician version", st)
                self.assertEqual(bool(kept), f"{len(kept)} allow rule(s) match magician's old list" in st, st)
                r = self.ui("cleanup")
                self.assertEqual(self.read_settings()["permissions"]["allow"], kept + ["Bash(mytool:*)"])
                self.assertEqual(bool(kept), "Kept 2 allow rule(s)" in r.stdout, r.stdout)

    def test_purge_refuses_while_the_record_remains(self) -> None:
        """cleanup finds these entries only through cli-ui.json, so --purge keeps the record (and changes
        nothing) until cleanup has run, unless --force is given."""
        cases = [({"allow": "on", "allowVersion": "4.14.0"}, {"allow": list(self.MATCHING)}),
                 ({"automode": "on"}, {"defaultMode": "auto"})]
        for cfg, perms in cases:
            with self.subTest(cfg=cfg):
                raw = self.write_settings({"statusLine": OUR_BAR, "permissions": perms})
                self.write_cfg(cfg)
                cfg_raw = (self.mh / "cli-ui.json").read_bytes()
                backups = self.backups()
                r = self.ui("disable", "--purge", expect=1)
                self.assertIn("Run `magician-ui cleanup`, then `magician-ui disable --purge`", r.stderr)
                self.assertIn("--purge --force", r.stderr)
                self.assertIn("Nothing was changed", r.stderr)
                self.assertEqual(self.settings.read_bytes(), raw, "a refused purge edited settings.json")
                self.assertEqual((self.mh / "cli-ui.json").read_bytes(), cfg_raw, "a refused purge touched the record")
                self.assertEqual(self.backups(), backups)

                self.ui("cleanup")
                self.ui("disable", "--purge")
                self.assertEqual(self.read_settings().get("permissions"), {"allow": []} if "allow" in perms else {})
                self.assertNotIn("statusLine", self.read_settings())
                self.assertFalse((self.mh / "cli-ui.json").exists())

    def test_purge_force_drops_the_record_and_keeps_the_entries(self) -> None:
        self.write_settings({"statusLine": OUR_BAR, "permissions": {"allow": list(self.MATCHING)}})
        self.write_cfg({"allow": "on", "allowVersion": "4.14.0"})
        self.ui("disable", "--force", expect=1)
        self.assertIn("statusLine", self.read_settings(), "--force without --purge changed settings")
        self.ui("disable", "--purge", "--force")
        self.assertEqual(self.read_settings(), {"permissions": {"allow": self.MATCHING}})
        self.assertFalse((self.mh / "cli-ui.json").exists())

    def test_purge_is_not_stopped_by_what_cleanup_finds_without_the_record(self) -> None:
        """The env key and unrecorded rules don't depend on cli-ui.json, so deleting it strands nothing."""
        self.write_settings({"env": {AUTOMODE_ENV: "1"}, "permissions": {"allow": list(self.MATCHING)}})
        self.write_cfg({"state": "enabled"})
        self.ui("disable", "--purge")
        self.assertFalse((self.mh / "cli-ui.json").exists())


class ArgumentTests(UiCase):
    def test_help_and_unknown_arguments_change_nothing(self) -> None:
        """A flag a subcommand doesn't take (a hoped-for --dry-run, a --help after the subcommand) must
        not fall through to the real action: cleanup's deletions and backup pruning can't be undone."""
        raw = self.write_settings(dict(self.legacy_settings(), statusLine=OUR_BAR))
        self.write_cfg({"state": "enabled", "allow": "on", "allowVersion": "4.3.0", "automode": "on",
                        "lore": "disabled"})
        cfg_raw = (self.mh / "cli-ui.json").read_bytes()
        legacy = self.magician_data / "patterns.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("x", encoding="utf-8")
        help_runs = [("cleanup", "--help"), ("enable", "--help"), ("disable", "-h"), ("lore", "--help"),
                     ("disable", "--purge", "--help"), ("allow", "--off", "-h")]
        bad_runs = [("cleanup", "--dry-run"), ("cleanup", "now"), ("enable", "-x"), ("enable", "--everything"),
                    ("set", "--quiet", "rot"), ("disable", "--purgee"), ("disable", "--purge", "-n"),
                    ("lore", "maybe"), ("lore", "on", "off"), ("voice", "bard", "extra"), ("allow", "--off", "--dry-run"),
                    ("automode", "off", "now"), ("reconcile", "--x"), ("status", "--json"), ("default", "--all"),
                    ("enable", "help"), ("enable", "contxt"), ("enable", "--only=contxt"), ("enable", "--only"),
                    ("set", "contxt")]
        for args in help_runs + bad_runs:
            with self.subTest(args=args):
                r = self.ui(*args, expect=0 if args in help_runs else 1)
                if args in help_runs:
                    self.assertIn("Subcommands:", r.stdout)
                else:
                    self.assertIn("nothing was changed", r.stderr.lower())
                self.assertEqual(self.settings.read_bytes(), raw)
                self.assertEqual((self.mh / "cli-ui.json").read_bytes(), cfg_raw)
                self.assertTrue(legacy.exists())
                self.assertFalse((self.mh / "statusline.py").exists())
                self.assertEqual(self.backups(), [])

    def test_documented_arguments_still_work(self) -> None:
        self.write_settings({})
        self.ui("lore", "off")
        self.assertEqual(self.read_cfg()["lore"], "disabled")
        self.ui("lore")
        self.assertEqual(self.read_cfg()["lore"], "enabled")
        self.assertIn("lore injection:", self.ui("lore", "status").stdout)
        self.ui("voice", "warrior")
        self.assertIn("voice level:     warrior", self.ui("voice").stdout)
        self.assertIn("nothing was changed", self.ui("allow").stdout)
        self.ui("enable", "--only", "context,rot")
        self.ui("set", "--only=meta")
        self.assertEqual(self.read_cfg()["components"], ["meta"])


class StatusLineCommandTests(UiCase):
    def test_enable_writes_only_status_line(self) -> None:
        before = self.legacy_settings()
        self.write_settings(before)
        self.ui("enable", "--only", "context,rot")
        after = self.read_settings()
        sl = after.pop("statusLine")
        self.assertEqual(after, before, "enable changed keys other than statusLine")
        installed = self.mh / "statusline.py"
        self.assertIn(str(installed), sl["command"])
        self.assertEqual(installed.read_bytes(), RENDERER.read_bytes())
        self.assertTrue(os.access(installed, os.X_OK))
        cfg = self.read_cfg()
        self.assertEqual((cfg["state"], cfg["components"]), ("enabled", ["context", "rot"]))

    def test_plain_enable_keeps_saved_components(self) -> None:
        self.write_settings({"model": "some-model"})
        self.ui("enable", "--only", "context,meta")
        r = self.ui("enable")  # the refresh step after an update
        self.assertEqual(self.read_cfg()["components"], ["context", "meta"])
        self.assertIn("components: context, meta.", r.stdout)
        self.ui("set", "rot,skill")
        self.ui("enable")
        self.assertEqual(self.read_cfg()["components"], ["rot", "skill"])
        self.ui("enable", "--all")
        self.assertEqual(self.read_cfg()["components"], ALL)
        self.ui("enable", "--only=spark")
        self.assertEqual(self.read_cfg()["components"], ["spark"])
        # Nothing valid saved: plain enable falls back to every component.
        for saved, expected in ((["meta", "gone"], ["meta"]), (["gone"], ALL), ("context", ALL), (None, ALL)):
            with self.subTest(saved=saved):
                self.write_cfg({"state": "enabled"} if saved is None else {"components": saved})
                self.ui("enable")
                self.assertEqual(self.read_cfg()["components"], expected)
        self.assertIn("statusLine", self.read_settings())

    def test_disable_removes_only_magicians_status_line(self) -> None:
        self.write_settings({"model": "some-model"})
        self.ui("enable", "--all")
        self.ui("disable")
        self.assertEqual(self.read_settings(), {"model": "some-model"})
        self.assertEqual(self.read_cfg()["state"], "disabled")
        self.assertTrue((self.mh / "statusline.py").exists(), "plain disable must not purge")

        foreign = {"statusLine": {"type": "command", "command": "my-own-bar"}}
        raw = self.write_settings(foreign)
        r = self.ui("disable")
        self.assertIn("leaving it untouched", r.stdout)
        self.assertEqual(self.settings.read_bytes(), raw)

    def test_disable_purge_removes_renderer_status_and_config(self) -> None:
        self.write_settings({"model": "some-model"})
        self.ui("enable", "--all")
        status = self.mh / "status"
        status.mkdir()
        (status / "s1.lore.json").write_text("{}", encoding="utf-8")
        (status / "gitbranch-abc").write_text("main", encoding="utf-8")
        kg = self.mh / "knowledge-graph" / "repos" / "abc"
        kg.mkdir(parents=True)
        (kg / "index.json").write_text("{}", encoding="utf-8")

        r = self.ui("disable", "--purge")
        self.assertEqual(self.read_settings(), {"model": "some-model"})
        self.assertFalse((self.mh / "statusline.py").exists())
        self.assertFalse(status.exists())
        self.assertFalse((self.mh / "cli-ui.json").exists())
        self.assertTrue((kg / "index.json").exists(), "purge touched the knowledge-graph store")
        self.assertIn("removed", r.stdout)

    def test_disable_purge_keeps_a_foreign_status_line(self) -> None:
        foreign = {"statusLine": {"type": "command", "command": "my-own-bar"}}
        raw = self.write_settings(foreign)
        self.write_cfg({"state": "disabled"})
        self.ui("disable", "--purge")
        self.assertEqual(self.settings.read_bytes(), raw)
        self.assertFalse((self.mh / "cli-ui.json").exists())


class RendererPruneTests(UiCase):
    def render(self) -> subprocess.CompletedProcess:
        payload = json.dumps({"session_id": "s-now", "context_window": {
            "used_percentage": 42, "context_window_size": 200000,
            "total_input_tokens": 84000, "total_output_tokens": 0}, "cwd": str(self.tmp)})
        r = subprocess.run([sys.executable, str(RENDERER)], input=payload, text=True,
                           capture_output=True, env=self.env, cwd=str(self.tmp), check=False, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("42%", r.stdout)
        return r

    def age(self, p: Path, seconds: float) -> None:
        t = time.time() - seconds
        os.utime(p, (t, t))

    def test_status_files_older_than_seven_days_are_pruned_hourly(self) -> None:
        status = self.mh / "status"
        status.mkdir(parents=True)
        old = ["s-old.json", "s-old.lore.json", "s-old.voice.json", "s-old.effort.json",
               "s-old.spark", "gitbranch-0123456789ab"]
        fresh = ["s-new.json", "s-new.spark"]
        for n in old + fresh + ["notes.txt"]:
            (status / n).write_text("{}", encoding="utf-8")
        for n in old + ["notes.txt"]:
            self.age(status / n, 8 * 86400)

        self.render()
        for n in old:
            self.assertFalse((status / n).exists(), f"{n} not pruned")
        for n in fresh + ["notes.txt"]:
            self.assertTrue((status / n).exists(), f"{n} wrongly pruned")
        marker = status / ".pruned"
        self.assertTrue(marker.exists())

        late = status / "s-late.json"      # goes stale after the pass: waits for the next hourly pass
        late.write_text("{}", encoding="utf-8")
        self.age(late, 8 * 86400)
        self.render()
        self.assertTrue(late.exists(), "prune ran again within the hour")

        self.age(marker, 2 * 3600)
        self.render()
        self.assertFalse(late.exists(), "hourly prune pass did not run")

    def test_renderer_never_reads_the_transcript(self) -> None:
        src = RENDERER.read_text(encoding="utf-8")
        self.assertNotIn("transcript_path", src)
        self.assertIn("never opens the session transcript", src)


if __name__ == "__main__":
    unittest.main()

"""SessionStart hook contract (scripts/session-start.sh).

The hook detects the project's stack, injects the bundled lore cores and a few per-project notes as
`hookSpecificOutput.additionalContext`, and shows user-only notices as a top-level `systemMessage`.
It is plain bash: it runs no interpreter and no other plugin file, never writes Claude Code settings
or the session env file, and writes only under the plugin data dir (plus the status-bar markers when
the user enabled the status line). These tests run it for real under /bin/bash in temp project
directories and pin that behaviour, the 9,500-character budget and the factual wording.

Every run gets a fully specified env built from temp dirs (HOME, CLAUDE_PLUGIN_DATA, MAGICIAN_HOME,
MAGICIAN_SETTINGS, CLAUDE_ENV_FILE): nothing is inherited from os.environ, so the real
~/.claude/settings.json and ~/.claude/magician are never read or touched.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts" / "session-start.sh"
BASH = "/bin/bash"
BUDGET = 9500

FIRST_RUN = "Magician: run /almanac to set up this project (optional)."
MIGRATION = ("magician 4.15 no longer manages Claude Code permissions. An earlier version recorded adding "
             "allow rules or defaultMode=auto to ~/.claude/settings.json; run magician-ui cleanup to remove "
             "the entries it recorded adding.")

# Steering phrases that must never appear in text the hook itself writes into Claude's context.
IMPERATIVE = re.compile(
    r"before doing any other work|\bdo not\b|\bdon't\b|\bmust\b|\bnever\b|\binvoke\b|AskUserQuestion"
    r"|\byou should\b|\balways\b|\bmake sure\b|\bIMPORTANT\b|\binstead of\b|\bavoid\b", re.I)

_GIT = shutil.which("git")
_PATH = ":".join(dict.fromkeys(
    ([str(Path(_GIT).parent)] if _GIT else []) + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]))


class Sandbox:
    """Temp HOME / plugin data / magician home / settings / env-file paths plus project dirs."""

    def __init__(self, tmp: str) -> None:
        self.base = Path(tmp)
        self.home = self.base / "home"
        self.data = self.base / "data"
        self.mag = self.base / "maghome"
        self.settings = self.home / ".claude" / "settings.json"
        self.envfile = self.base / "session.env"
        for d in (self.home, self.data, self.mag):
            d.mkdir(parents=True)

    def env(self, **extra: str) -> dict:
        env = {
            "PATH": _PATH, "HOME": str(self.home), "LANG": "C",
            "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PLUGIN_DATA": str(self.data),
            "MAGICIAN_HOME": str(self.mag), "MAGICIAN_SETTINGS": str(self.settings),
            "CLAUDE_ENV_FILE": str(self.envfile),
        }
        env.update(extra)
        return env

    def project(self, name: str, files: dict | None = None, git: bool = False) -> Path:
        p = self.base / name
        p.mkdir(parents=True)
        for rel, text in (files or {}).items():
            f = p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        if git:
            self.git(p, "init", "-q", ".")
        return p

    def git(self, cwd: Path, *args: str) -> None:
        subprocess.run([_GIT, "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                       cwd=str(cwd), env=self.env(), check=True, capture_output=True, timeout=60)

    def run(self, cwd: Path, payload: str | dict = "", **extra: str) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([BASH, str(HOOK)], input=stdin, encoding="utf-8", errors="replace",
                              capture_output=True, cwd=str(cwd), env=self.env(**extra), timeout=120,
                              check=False)

    def out(self, cwd: Path, payload: str | dict = "", **extra: str) -> dict:
        proc = self.run(cwd, payload, **extra)
        if proc.returncode != 0:
            raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
        return json.loads(proc.stdout)


def _ctx(doc: dict) -> str:
    return doc["hookSpecificOutput"]["additionalContext"]


def _proj_hash(path: Path) -> str:
    return hashlib.md5(os.path.realpath(path).encode()).hexdigest()[:12]


def _tree(root: Path) -> dict:
    """path -> (size, mtime_ns) for every file under root (a snapshot to diff)."""
    snap = {}
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                st = p.stat()
                snap[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return snap


PY_FILES = {"requirements.txt": "Django==4.2\npsycopg2-binary\n", "tests/.keep": ""}


class OutputShapeTests(unittest.TestCase):
    def test_every_source_emits_sessionstart_json_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES, git=True)
            for source in ("startup", "resume", "clear", "compact", "fork"):
                with self.subTest(source=source):
                    proc = sb.run(proj, {"session_id": f"s-{source}", "source": source,
                                         "hook_event_name": "SessionStart"})
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stderr, "")
                    doc = json.loads(proc.stdout)
                    self.assertLessEqual(set(doc), {"hookSpecificOutput", "systemMessage"})
                    self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "SessionStart")
                    self.assertEqual(set(doc["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
                    self.assertLessEqual(len(_ctx(doc)), BUDGET)

    def test_fails_open_on_bad_or_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            for payload in ("", "not json", "{", '{"source": 7}', '{"session_id":"../../x","source":"startup"}'):
                with self.subTest(payload=payload):
                    proc = sb.run(proj, payload)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertFalse((sb.base / "x.start").exists())
            self.assertEqual(list(sb.data.glob("sessions/*.start")), [])

    def test_budget_holds_when_every_note_is_large(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", {**PY_FILES, "package.json": '{"dependencies":{"next":"1","react":"1",'
                                      '"mongoose":"1","express":"1","tailwindcss":"1"}}',
                                      "tsconfig.json": "{}", "go.mod": "module x\ngorm.io/gorm v1\n"})
            h = _proj_hash(proj)
            (sb.data / "references.md").write_text(("- a saved reference line with some words\n" * 400),
                                                   encoding="utf-8")
            learn = sb.data / "projects" / h / "learnings.jsonl"
            learn.parent.mkdir(parents=True)
            # Odd offsets put both cuts (300-byte summary, 240-byte fact) inside a multibyte character.
            learn.write_text("".join(json.dumps({"fact": "decided " + "€" * 300}, ensure_ascii=False) + "\n"
                                     for _ in range(5)), encoding="utf-8")
            chron = sb.data / "chronicle"
            chron.mkdir()
            (chron / "20260101T000000Z-old.json").write_text(json.dumps(
                {"working_dir": os.path.realpath(proj), "summary": "a" + "é" * 900}, ensure_ascii=False), encoding="utf-8")
            doc = sb.out(proj, {"session_id": "big", "source": "compact"})
            ctx = _ctx(doc)
            self.assertLessEqual(len(ctx), BUDGET)
            self.assertLessEqual(len(ctx.encode("utf-8")), BUDGET)
            self.assertIn("[security] ", ctx)
            self.assertIn("Previous magician session in this directory: ", ctx)
            self.assertIn("decided €", ctx)
            self.assertIn("a" + "é" * 149, ctx)          # 299 bytes: the whole characters that fit are kept
            self.assertNotIn("a" + "é" * 150, ctx)
            self.assertNotIn("\ufffd", ctx)  # byte-level truncation never splits a UTF-8 sequence

    def test_trunc_keeps_a_character_that_ends_at_the_cut(self) -> None:
        """_trunc drops only an incomplete trailing sequence: a character ending exactly at the cut stays,
        so the result is always the longest whole-character prefix that fits."""
        src = HOOK.read_text(encoding="utf-8")
        start = src.index("_trunc() {")
        fn = src[start:src.index("\n}\n", start) + 3]
        for text in ("\u00e9" * 900, "a" + "\u00e9" * 900, "\u20ac" * 100, "x" + "\u20ac" * 100, "xx" + "\u20ac" * 100,
                     "\U0001f600" * 100, "a" + "\U0001f600" * 100, "ab" + "\U0001f600" * 100,
                     "abc" + "\U0001f600" * 100, "plain ascii " * 40):
            for cut in (240, 300):
                with self.subTest(text=text[:4], cut=cut):
                    r = subprocess.run(["bash", "-c", fn + '_trunc "$1" "$2"', "_", str(cut), text],
                                       capture_output=True, env={"LC_ALL": "C", "PATH": _PATH}, timeout=10)
                    want = text.encode("utf-8")[:cut].decode("utf-8", "ignore").encode("utf-8")
                    self.assertEqual(r.stdout, want)

    def test_plugin_root_and_notes_are_json_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            odd = sb.base / 'we"ird\\root\tdir'
            odd.symlink_to(ROOT)
            proj = sb.project("app", PY_FILES)
            chron = sb.data / "chronicle"
            chron.mkdir()
            (chron / "20260101T000000Z-prev.json").write_text(json.dumps(
                {"working_dir": os.path.realpath(proj), "summary": 'said "hi" \\ back'}), encoding="utf-8")
            doc = sb.out(proj, {"session_id": "esc", "source": "startup"}, CLAUDE_PLUGIN_ROOT=str(odd))
            ctx = _ctx(doc)
            self.assertIn(f"(plugin root: {odd})", ctx)
            self.assertIn('said "hi" \\ back', ctx)


class NoSideEffectTests(unittest.TestCase):
    def test_never_writes_settings_or_the_session_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES, git=True)
            (sb.mag / "cli-ui.json").write_text('{"allow": "on", "automode": "on"}', encoding="utf-8")
            before_home, before_mag = _tree(sb.home), _tree(sb.mag)
            for source in ("startup", "resume", "compact"):
                sb.run(proj, {"session_id": "s1", "source": source})
            self.assertFalse(sb.settings.exists(), "the hook created a settings file")
            self.assertFalse(sb.envfile.exists(), "session-start.sh wrote CLAUDE_ENV_FILE")
            self.assertEqual(_tree(sb.home), before_home)
            self.assertEqual(_tree(sb.mag), before_mag)
            self.assertEqual({p.name for p in proj.iterdir()} - {".git"}, {"requirements.txt", "tests"})

    def test_existing_settings_and_env_file_are_left_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            sb.settings.parent.mkdir(parents=True)
            sb.settings.write_text('{"permissions": {"allow": []}}\n', encoding="utf-8")
            sb.envfile.write_text("export KEEP=1\n", encoding="utf-8")
            (sb.home / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
            snap = _tree(sb.home)
            env_before = sb.envfile.read_bytes()
            sb.out(proj, {"session_id": "s2", "source": "startup"})
            self.assertEqual(_tree(sb.home), snap)
            self.assertEqual(sb.envfile.read_bytes(), env_before)

    def test_status_markers_only_when_status_line_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            sb.out(proj, {"session_id": "m1", "source": "startup"})
            self.assertFalse((sb.mag / "status").exists())
            (sb.mag / "cli-ui.json").write_text('{"state": "enabled"}', encoding="utf-8")
            sb.out(proj, {"session_id": "m1", "source": "startup"})
            lore = json.loads((sb.mag / "status" / "m1.lore.json").read_text(encoding="utf-8"))
            voice = json.loads((sb.mag / "status" / "m1.voice.json").read_text(encoding="utf-8"))
            self.assertTrue(lore["enabled"])
            self.assertIn("python", lore["cores"])
            self.assertEqual(lore["count"], len(lore["cores"]))
            self.assertEqual(voice["level"], "scribe")
            self.assertFalse((sb.mag / "statusline.py").exists())


class WordingTests(unittest.TestCase):
    def _hook_text(self, sb: Sandbox, proj: Path, source: str) -> str:
        return _ctx(sb.out(proj, {"session_id": f"w-{source}", "source": source}, MAGICIAN_LORE="0"))

    def test_hook_authored_text_is_factual(self) -> None:
        """With lore off, everything left in additionalContext is written by the hook itself."""
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            files = {**PY_FILES, **{f"src/m{i}.py": "" for i in range(160)}}
            proj = sb.project("app", files, git=True)
            sb.git(proj, "add", "-A")
            h = _proj_hash(proj)
            learn = sb.data / "projects" / h / "learnings.jsonl"
            learn.parent.mkdir(parents=True)
            learn.write_text(json.dumps({"fact": "chose pgx over lib/pq"}) + "\n", encoding="utf-8")
            (sb.data / "chronicle").mkdir()
            (sb.data / "chronicle" / "20260101T000000Z-p.json").write_text(json.dumps(
                {"working_dir": os.path.realpath(proj), "summary": "2 commit(s) on main"}), encoding="utf-8")
            (sb.data / "references.md").write_text("- repo: example/tooling\n", encoding="utf-8")
            texts = [self._hook_text(sb, proj, s) for s in ("startup", "compact", "resume")]
            joined = "\n".join(texts)
            for needle in ("Previous magician session", "Recent project learnings", "knowledge-graph",
                           "No log platform is recorded", "re-stated after compact", "User-curated references",
                           "Magician lore is disabled"):
                self.assertIn(needle, joined)
            for text in texts:
                m = IMPERATIVE.search(text)
                self.assertIsNone(m, f"steering phrase {m and m.group(0)!r} in hook context")
                self.assertNotIn("settings.json", text)
                self.assertNotIn("CLAUDE_ENV_FILE", text)

    def test_voice_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            self.assertIn("(voice: scribe)", _ctx(sb.out(proj, {"source": "startup"})))
            self.assertIn("Warrior level", _ctx(sb.out(proj, {"source": "startup"}, MAGICIAN_VOICE="warrior")))
            self.assertNotIn("Output style selected", _ctx(sb.out(proj, {"source": "startup"}, MAGICIAN_VOICE="bard")))


class LoreTests(unittest.TestCase):
    def test_detected_stack_gets_lore_and_one_deep_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            ctx = _ctx(sb.out(proj, {"session_id": "l1", "source": "startup"}))
            self.assertIn("Detected stack: python,django,tdd,databases,postgres.", ctx)
            for core in ("security", "python", "databases", "postgres", "django"):
                self.assertIn(f"[{core}] ", ctx)
            self.assertTrue((ROOT / "lore" / "deep" / "python.md").is_file())
            self.assertEqual(ctx.count("Deep-dive files: "), 1)
            self.assertIn("Deep-dive files: lore/deep/<stack>.md under the plugin root", ctx)
            self.assertEqual(ctx.count(str(ROOT)), 1, "the plugin root is written once, in the first line")

    def test_specific_cores_are_kept_when_notes_leave_little_room(self) -> None:
        """Language, framework and engine outrank the generic cores (databases, logging, tdd)."""
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            learn = sb.data / "projects" / _proj_hash(proj) / "learnings.jsonl"
            learn.parent.mkdir(parents=True)
            learn.write_text("".join(json.dumps({"fact": "decided " + "x" * 600}) + "\n" for _ in range(3)),
                             encoding="utf-8")
            (sb.data / "chronicle").mkdir()
            (sb.data / "chronicle" / "20260101T000000Z-p.json").write_text(json.dumps(
                {"working_dir": os.path.realpath(proj), "summary": "y" * 600}), encoding="utf-8")
            ctx = _ctx(sb.out(proj, {"session_id": "tight", "source": "compact"}))
            self.assertLessEqual(len(ctx.encode("utf-8")), BUDGET)
            self.assertIn("Detected stack: python,django,tdd,databases,postgres.", ctx)
            injected = set(re.findall(r"(?m)^\[([a-z0-9-]+)\] ", ctx))
            detected = {"security", "python", "django", "tdd", "databases", "postgres", "logging"}
            self.assertLessEqual({"security", "python", "django", "postgres"}, injected)
            dropped = detected - injected
            self.assertTrue(dropped, "the notes must leave too little room for every core")
            self.assertLessEqual(dropped, {"databases", "logging", "tdd"})

    def test_lore_off_switches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            off_env = _ctx(sb.out(proj, {"source": "startup"}, MAGICIAN_LORE="off"))
            (sb.mag / "cli-ui.json").write_text('{"lore": "disabled"}', encoding="utf-8")
            off_global = _ctx(sb.out(proj, {"source": "startup"}))
            (sb.mag / "cli-ui.json").unlink()
            (proj / ".magician").mkdir()
            (proj / ".magician" / "lore.off").write_text("", encoding="utf-8")
            off_proj = _ctx(sb.out(proj, {"source": "startup"}))
            for ctx in (off_env, off_global, off_proj):
                self.assertNotIn("[python] ", ctx)
                self.assertNotIn("Deep-dive files: ", ctx)
                self.assertIn("Magician lore is disabled for this session", ctx)

    def test_kubernetes_detection_survives_odd_yaml_names(self) -> None:
        """File names with spaces, quotes or a leading `--` must neither hide a manifest nor be read as options."""
        manifest = "apiVersion: apps/v1\nkind: Deployment\n"
        cases = {"plain": {"deploy.yaml": manifest},
                 "space": {"k8s deploy.yaml": manifest},
                 "dash": {"--x.yaml": "a: 1\n", "deploy.yaml": manifest},
                 "quote": {"it's.yml": "a: 1\n", "svc.yml": "kind: Service\n"}}
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            for name, files in cases.items():
                with self.subTest(name):
                    ctx = _ctx(sb.out(sb.project(name, files), {"source": "startup"}))
                    self.assertRegex(ctx, r"Detected stack: [a-z0-9,-]*kubernetes")
            ctx = _ctx(sb.out(sb.project("none", {"config.yaml": "kind: ConfigMap\n"}), {"source": "startup"}))
            self.assertNotRegex(ctx, r"Detected stack: [a-z0-9,-]*kubernetes")

    def test_empty_directory_reports_no_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("empty")
            doc = sb.out(proj, {"session_id": "e1", "source": "startup"})
            self.assertIn("No stack markers were found in this directory.", _ctx(doc))
            self.assertNotIn("systemMessage", doc)

    def test_budget_literal_and_exact_lore_file_names(self) -> None:
        script = HOOK.read_text(encoding="utf-8")
        self.assertRegex(script, r"(?m)^MAX_LORE=8100$")
        self.assertIn('LORE_FILE="${PLUGIN_ROOT}/lore/${TECH}.md"', script)
        self.assertNotRegex(script, r"lore/\$\{?TECH\}?\*|lore/\*")
        self.assertIn('$(<"$LORE_FILE")', script)


class NoticeTests(unittest.TestCase):
    def test_first_run_notice_once_per_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            first = sb.out(proj, {"session_id": "f1", "source": "startup"})
            self.assertEqual(first.get("systemMessage"), FIRST_RUN)
            self.assertNotIn("/almanac", _ctx(first))
            again = sb.out(proj, {"session_id": "f2", "source": "startup"})
            self.assertNotIn("systemMessage", again)

    def test_migration_notice_weekly_while_permission_flags_are_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("empty")
            cfg = sb.mag / "cli-ui.json"
            cfg.write_text('{"allow":"off","automode":"off"}', encoding="utf-8")
            self.assertNotIn("systemMessage", sb.out(proj, {"source": "startup"}))
            for flags in ('{"allow": "on"}', '{"automode" : "on", "allow": "off"}'):
                with self.subTest(flags=flags):
                    marker = sb.data / "migration-4.15-notice"
                    if marker.exists():
                        marker.unlink()
                    cfg.write_text(flags, encoding="utf-8")
                    doc = sb.out(proj, {"source": "startup"})
                    self.assertEqual(doc.get("systemMessage"), MIGRATION)
                    self.assertNotIn("magician-ui cleanup", _ctx(doc))
                    self.assertNotIn("systemMessage", sb.out(proj, {"source": "resume"}))
                    old = time.time() - 8 * 86400
                    os.utime(marker, (old, old))
                    self.assertEqual(sb.out(proj, {"source": "startup"}).get("systemMessage"), MIGRATION)

    def test_both_notices_join_in_one_system_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            (sb.mag / "cli-ui.json").write_text('{"allow":"on"}', encoding="utf-8")
            self.assertEqual(sb.out(proj, {"source": "startup"}).get("systemMessage"), FIRST_RUN + "\n" + MIGRATION)


class SessionStampTests(unittest.TestCase):
    ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n$")

    def test_stamp_written_on_new_sessions_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("empty")
            stamps = sb.data / "sessions"
            for source in ("startup", "clear", "fork"):
                sb.out(proj, {"session_id": f"new-{source}", "source": source})
                self.assertRegex((stamps / f"new-{source}.start").read_text(encoding="utf-8"), self.ISO)
            for source in ("resume", "compact", ""):
                sb.out(proj, {"session_id": f"old-{source or 'none'}", "source": source})
                self.assertFalse((stamps / f"old-{source or 'none'}.start").exists())

    def test_existing_stamp_kept_and_old_stamps_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("empty")
            stamps = sb.data / "sessions"
            stamps.mkdir()
            (stamps / "keep.start").write_text("2026-01-01T00:00:00Z\n", encoding="utf-8")
            stale = stamps / "stale.start"
            stale.write_text("2025-01-01T00:00:00Z\n", encoding="utf-8")
            old = time.time() - 40 * 86400
            os.utime(stale, (old, old))
            sb.out(proj, {"session_id": "keep", "source": "startup"})
            self.assertEqual((stamps / "keep.start").read_text(encoding="utf-8"), "2026-01-01T00:00:00Z\n")
            self.assertFalse(stale.exists())


class PreviousSessionTests(unittest.TestCase):
    def _record(self, sb: Sandbox, name: str, wd: str, summary: str, age: int) -> None:
        d = sb.data / "chronicle"
        d.mkdir(exist_ok=True)
        p = d / name
        p.write_text(json.dumps({"working_dir": wd, "summary": summary}), encoding="utf-8")
        t = time.time() - age
        os.utime(p, (t, t))

    def test_only_records_for_this_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            other = sb.project("other")
            self._record(sb, "20260103T000000Z-cur.json", os.path.realpath(proj), "CURRENT-SESSION", 10)
            self._record(sb, "20260102T000000Z-oth.json", os.path.realpath(other), "OTHER-DIR", 20)
            self._record(sb, "20260101T000000Z-mine.json", os.path.realpath(proj), "THIS-DIR", 30)
            ctx = _ctx(sb.out(proj, {"session_id": "cur", "source": "startup"}))
            self.assertIn("Previous magician session in this directory: THIS-DIR", ctx)
            self.assertNotIn("OTHER-DIR", ctx)
            self.assertNotIn("CURRENT-SESSION", ctx)
            none = _ctx(sb.out(other / "..", {"session_id": "x", "source": "startup"}))
            self.assertNotIn("Previous magician session", none)

    def test_session_history_option_turns_it_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", PY_FILES)
            self._record(sb, "20260101T000000Z-a.json", os.path.realpath(proj), "THIS-DIR", 30)
            for value in ("false", "False", "0"):
                with self.subTest(value=value):
                    ctx = _ctx(sb.out(proj, {"source": "startup"}, CLAUDE_PLUGIN_OPTION_SESSION_HISTORY=value))
                    self.assertNotIn("THIS-DIR", ctx)
            self.assertIn("THIS-DIR", _ctx(sb.out(proj, {"source": "startup"},
                                                  CLAUDE_PLUGIN_OPTION_SESSION_HISTORY="true")))


class ProjectNoteTests(unittest.TestCase):
    def test_knowledge_graph_index_note_and_throttled_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("repo", {f"f{i}.txt": "" for i in range(160)}, git=True)
            sb.git(proj, "add", "-A")
            ctx = _ctx(sb.out(proj, {"source": "startup"}))
            self.assertIn("(160 tracked files) has no magician knowledge-graph index", ctx)
            self.assertNotIn("magician knowledge-graph index", _ctx(sb.out(proj, {"source": "startup"})))
            h = hashlib.sha256(os.path.realpath(proj).encode()).hexdigest()[:12]
            meta = sb.mag / "knowledge-graph" / "repos" / h / "meta.json"
            meta.parent.mkdir(parents=True)
            meta.write_text("{}", encoding="utf-8")
            self.assertIn("has a magician knowledge-graph index", _ctx(sb.out(proj, {"source": "startup"})))

    def test_knowledge_graph_suggestion_respects_opt_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("repo", {f"f{i}.txt": "" for i in range(160)}, git=True)
            sb.git(proj, "add", "-A")
            (sb.data / "integration-prefs.json").write_text('{"knowledge-graph": "disabled"}', encoding="utf-8")
            self.assertNotIn("magician knowledge-graph index", _ctx(sb.out(proj, {"source": "startup"})))

    def test_log_platform_record_and_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            proj = sb.project("app", {"requirements.txt": "fastapi\ngoogle-cloud-logging\n"})
            self.assertIn("Log platform for this project: gcp-logging (detected)", _ctx(sb.out(proj, {})))
            rec = sb.data / "projects" / _proj_hash(proj) / "observability.json"
            rec.parent.mkdir(parents=True, exist_ok=True)
            rec.write_text('{"platform": "Splunk"}', encoding="utf-8")
            self.assertIn("Log platform for this project: splunk (recorded)", _ctx(sb.out(proj, {})))
            rec.write_text('{"platform": "unknown-tool"}', encoding="utf-8")
            self.assertIn("(detected)", _ctx(sb.out(proj, {})))


class StaticContractTests(unittest.TestCase):
    """The script itself: plain bash, no interpreters, no other plugin files, no settings/env writes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = HOOK.read_text(encoding="utf-8")
        code = []
        for line in cls.text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)      # blank quoted literals (stack names are data)
            line = re.sub(r"'[^']*'", "''", line)
            code.append(re.sub(r"\s#\s.*$", "", line))
        cls.code = "\n".join(code)

    def test_runs_under_bin_bash(self) -> None:
        self.assertTrue(self.text.startswith("#!/usr/bin/env bash\n"))
        proc = subprocess.run([BASH, "-n", str(HOOK)], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.access(HOOK, os.X_OK))
        self.assertIn("export LC_ALL=C", self.text)
        self.assertTrue(self.text.rstrip().endswith("exit 0"))

    def test_no_interpreters_eval_source_or_plugin_file_calls(self) -> None:
        cmd = r"(?:^|[;&|({]|\$\(|\bthen|\bdo|\belse)\s*"
        for word in ("python3?", "node", "nodejs", "perl", "ruby", "awk", "php", "deno", "bun", "npx",
                     "uvx", "pipx", "pip3?", "npm", "eval", "source", "exec", "sh", "bash", "zsh", "jq",
                     "stat", "shasum"):
            with self.subTest(word=word):
                self.assertNotRegex(self.code, re.compile(cmd + word + r"(?:\s|$)", re.M))
        self.assertNotRegex(self.code, re.compile(r"(?m)(?:^|[;&|])\s*\.\s+\S"))
        self.assertNotRegex(self.text, r"\$\{?(?:CLAUDE_)?PLUGIN_ROOT\}?\"?/(?:bin|scripts)/")
        self.assertNotRegex(self.code, r"\b(?:python3?|node|perl|ruby|bash|sh|zsh)\s+-[ce]\b")  # inline programs
        self.assertNotRegex(self.text, r"(?m)^\s*set\s+(?:-[a-z]*[eu]|-o\s+pipefail)")

    def test_no_env_file_settings_or_dotenv_access(self) -> None:
        self.assertNotIn("CLAUDE_ENV_FILE", self.text)
        self.assertNotIn("MAGICIAN_SETTINGS", self.text)
        self.assertNotRegex(self.text, r"(?<![\w./-])\.env(?:\.\*)?(?=\s|$)")
        self.assertNotRegex(self.text, r"\.env\b")
        # the only settings.json mention is the user-facing migration notice text
        lines = [l for l in self.text.splitlines() if "settings.json" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("no longer manages Claude Code permissions", self.text)
        self.assertIn("run magician-ui cleanup", lines[0])
        self.assertNotRegex(self.text, r"magician-ui\s+(?:enable|reconcile|allow|automode|init)")

    def test_no_removed_features(self) -> None:
        for needle in ("capsule", "transcript", ".resume", "session-start-time", "kg-nudge", "access-tracker",
                       "greeting", "statusline.py", "patterns.json"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, self.text)


if __name__ == "__main__":
    unittest.main()

"""Compaction contract (scripts/compact-context.sh, SessionStart matcher "compact").

After a compaction the plugin restates working-state *pointers* for the current directory: the git
branch, uncommitted files, this session's commits (bounded by the `sessions/<sid>.start` stamp that
session-start.sh writes) and the `.workspace/shared/` artifacts. It reads nothing from the
conversation: the hook input carries a transcript path, and none of that file's content may ever reach
the output. It is plain bash, writes nothing, fails open, and its text is factual.

Each run gets a fully specified env built from temp dirs (HOME, CLAUDE_PLUGIN_DATA, MAGICIAN_HOME,
MAGICIAN_SETTINGS, CLAUDE_ENV_FILE); nothing is inherited from os.environ, so the real
~/.claude/settings.json and ~/.claude/magician are never read or touched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts" / "compact-context.sh"
BASH = "/bin/bash"
BUDGET = 9500
MARKER = "TRANSCRIPT-ONLY-MARKER-7f3a"   # appears only inside the transcript file

_GIT = shutil.which("git")
_PATH = ":".join(dict.fromkeys(
    ([str(Path(_GIT).parent)] if _GIT else []) + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
IMPERATIVE = re.compile(r"\bdo not\b|\bdon't\b|\bmust\b|\bnever\b|\balways\b|\bmake sure\b|\binvoke\b"
                        r"|\bIMPORTANT\b|\byou should\b|\bcontinue with\b|\bresume\b", re.I)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tree(root: Path) -> dict:
    snap = {}
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            st = p.stat()
            snap[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return snap


@unittest.skipUnless(_GIT, "git is required")
class CompactContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.home, self.data, self.mag = base / "home", base / "data", base / "maghome"
        for d in (self.home, self.data, self.mag):
            d.mkdir()
        self.settings = self.home / ".claude" / "settings.json"
        self.envfile = base / "session.env"
        self.repo = base / "repo"
        self.repo.mkdir()
        self.transcript = base / "transcript.jsonl"
        self.transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": (
            f"{MARKER}: never touch the production database")}}) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def env(self, **extra: str) -> dict:
        env = {"PATH": _PATH, "HOME": str(self.home), "LANG": "C",
               "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PLUGIN_DATA": str(self.data),
               "MAGICIAN_HOME": str(self.mag), "MAGICIAN_SETTINGS": str(self.settings),
               "CLAUDE_ENV_FILE": str(self.envfile),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        env.update(extra)
        return env

    def git(self, *args: str, when: datetime | None = None) -> None:
        extra = {}
        if when is not None:
            stamp = when.strftime("%Y-%m-%dT%H:%M:%S%z")
            extra = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        subprocess.run([_GIT, "-c", "user.email=t@example.com", "-c", "user.name=t",
                        "-c", "commit.gpgsign=false", *args],
                       cwd=str(self.repo), env=self.env(**extra), check=True, capture_output=True, timeout=60)

    def make_repo(self, branch: str = "feature/compact-test") -> None:
        now = datetime.now(timezone.utc)
        self.git("init", "-q", "-b", branch)
        (self.repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial import from last week", when=now - timedelta(days=2))
        (self.repo / "helpers.sh").write_text("true\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "switch to bash 3.2 helpers", when=now - timedelta(minutes=30))
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")   # uncommitted change
        plans = self.repo / ".workspace" / "shared" / "plans"
        plans.mkdir(parents=True)
        (plans / "plan.md").write_text("# plan\n", encoding="utf-8")
        (self.data / "sessions").mkdir()
        (self.data / "sessions" / "t.start").write_text(_iso(now - timedelta(hours=1)) + "\n", encoding="utf-8")

    def run_hook(self, payload: str | dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([BASH, str(HOOK)], input=stdin, encoding="utf-8", errors="replace",
                              capture_output=True, cwd=str(cwd or self.repo), env=self.env(),
                              timeout=60, check=False)

    def context(self, payload: str | dict, cwd: Path | None = None) -> str:
        proc = self.run_hook(payload, cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"hookSpecificOutput"})
        self.assertEqual(doc["hookSpecificOutput"]["hookEventName"], "SessionStart")
        return doc["hookSpecificOutput"]["additionalContext"]

    def payload(self, sid: str = "t") -> dict:
        return {"session_id": sid, "source": "compact", "hook_event_name": "SessionStart",
                "transcript_path": str(self.transcript)}

    # ── behaviour ─────────────────────────────────────────────────────────────────────────────
    def test_restates_branch_changes_session_commits_and_artifacts(self) -> None:
        self.make_repo()
        proc = self.run_hook(self.payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(ctx.startswith("Context was compacted. Working-state pointers for this directory"))
        self.assertIn("Branch: feature/compact-test", ctx)
        self.assertIn("Uncommitted changes vs HEAD:\n- app.py", ctx)
        self.assertIn("Commits since this session started (", ctx)
        self.assertIn("switch to bash 3.2 helpers", ctx)
        self.assertNotIn("initial import from last week", ctx)   # older than the session stamp
        self.assertIn("Shared artifacts in .workspace/shared:\n- .workspace/shared/plans/plan.md", ctx)
        self.assertLessEqual(len(ctx), BUDGET)

    def test_transcript_content_never_reaches_output(self) -> None:
        self.make_repo()
        proc = self.run_hook(self.payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for stream in (proc.stdout, proc.stderr):
            self.assertNotIn(MARKER, stream)
            self.assertNotIn("production database", stream)
            self.assertNotIn(str(self.transcript), stream)

    def test_without_a_stamp_falls_back_to_recent_commits(self) -> None:
        self.make_repo()
        for sid in ("unknown-session", "bad/../sid"):
            with self.subTest(sid=sid):
                ctx = self.context(self.payload(sid))
                self.assertIn("Recent commits:", ctx)
                self.assertIn("initial import from last week", ctx)
                self.assertNotIn("Commits since this session started", ctx)

    def test_malformed_stamp_is_ignored(self) -> None:
        self.make_repo()
        (self.data / "sessions" / "t.start").write_text("$(touch pwned) yesterday\n", encoding="utf-8")
        ctx = self.context(self.payload())
        self.assertIn("Recent commits:", ctx)
        self.assertNotIn("pwned", ctx)
        self.assertFalse((self.repo / "pwned").exists())

    def test_long_lists_are_bounded(self) -> None:
        self.make_repo()
        for i in range(40):
            (self.repo / f"new{i:02d}.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "-A")   # staged new files show in `git diff HEAD`
        ctx = self.context(self.payload())
        self.assertIn("- (+27 more)", ctx)   # 42 changed (40 new, app.py, the staged plan), 15 listed
        self.assertLessEqual(len(ctx), BUDGET)

    def test_artifacts_without_git(self) -> None:
        plain = Path(self._tmp.name) / "plain"
        (plain / ".workspace" / "shared" / "specs").mkdir(parents=True)
        (plain / ".workspace" / "shared" / "specs" / "feature.md").write_text("# spec\n", encoding="utf-8")
        ctx = self.context(self.payload(), cwd=plain)
        self.assertIn("- .workspace/shared/specs/feature.md", ctx)
        self.assertNotIn("Branch:", ctx)

    def test_fails_open_and_stays_silent_with_nothing_to_say(self) -> None:
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        for payload in ("", "not json", "{", '{"session_id": 5}', json.dumps(self.payload())):
            with self.subTest(payload=payload):
                proc = self.run_hook(payload, cwd=empty)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout, "")
        self.make_repo()
        for payload in ("", "not json", "{"):
            with self.subTest(payload=payload, repo=True):
                self.assertIn("Branch: ", self.context(payload))

    def test_text_is_factual(self) -> None:
        self.make_repo()
        ctx = self.context(self.payload())
        # commit subjects are data; check the hook's own lines
        own = [l for l in ctx.splitlines() if not l.startswith("- ")]
        for line in own:
            m = IMPERATIVE.search(line)
            self.assertIsNone(m, f"steering phrase {m and m.group(0)!r} in {line!r}")

    def test_writes_nothing(self) -> None:
        self.make_repo()
        base = Path(self._tmp.name)
        before = _tree(base)
        self.context(self.payload())
        self.assertEqual(_tree(base), before)
        self.assertFalse(self.settings.exists())
        self.assertFalse(self.envfile.exists())

    def test_json_escaping_of_branch_and_paths(self) -> None:
        self.make_repo(branch='fix/say-"hi"')
        odd = self.repo / ".workspace" / "shared" / "decisions"
        odd.mkdir(parents=True)
        (odd / 'say "hi" \\ back.md').write_text("x\n", encoding="utf-8")
        ctx = self.context(self.payload())
        self.assertIn('Branch: fix/say-"hi"', ctx)
        self.assertIn('- .workspace/shared/decisions/say "hi" \\ back.md', ctx)

    # ── static contract ───────────────────────────────────────────────────────────────────────
    def test_script_is_plain_bash_and_reads_no_conversation(self) -> None:
        text = HOOK.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env bash\n"))
        self.assertTrue(os.access(HOOK, os.X_OK))
        self.assertIn("export LC_ALL=C", text)
        self.assertTrue(text.rstrip().endswith("exit 0"))
        proc = subprocess.run([BASH, "-n", str(HOOK)], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for needle in ("transcript_path", "last_assistant_message", "agent_transcript_path", "CLAUDE_ENV_FILE",
                       "settings.json", "capsule", "PLUGIN_ROOT"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotRegex(code, r"(?m)(?:^|[;&|(]|\$\()\s*(?:python3?|node|perl|ruby|awk|jq|eval|source|exec"
                                  r"|sh|bash|zsh|stat|shasum)(?:\s|$)")
        self.assertNotRegex(code, r"(?m)(?:^|[;&|])\s*\.\s+\S")
        self.assertNotRegex(code, r"(?m)^\s*set\s+(?:-[a-z]*[eu]|-o\s+pipefail)")

    def test_wiring_replaces_the_precompact_capsule(self) -> None:
        self.assertFalse((ROOT / "scripts" / "pre-compact.sh").exists())
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertNotIn("PreCompact", hooks)
        groups = [g for g in hooks.get("SessionStart", []) if g.get("matcher") == "compact"]
        self.assertEqual(len(groups), 1)
        self.assertEqual([h.get("command") for h in groups[0]["hooks"]],
                         ['"${CLAUDE_PLUGIN_ROOT}"/scripts/compact-context.sh'])


if __name__ == "__main__":
    unittest.main()

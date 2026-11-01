"""scripts/plan-watch.sh — the plugin monitor behind the live plan review (monitors.json, on-skill-invoke:blueprint).

It follows the newest `.workspace/local/plans/*/state/events.jsonl` under the working folder (or the
folder `MAGICIAN_PLAN_STATE` names), prints each line appended after it started as one
`plan-event: ` line with control characters removed and the payload cut at 2,048 bytes, keeps its
byte offset in `plan-watch.offset` next to the log so a later watch resumes there, picks up a log that
appears while it waits from its first line, waits for a complete line, stops when state.json says
the plan is approved or rejected, and otherwise exits 0 at its time cap
(`MAGICIAN_PLAN_WATCH_MAX_SECONDS`, 3 h by default). It prints nothing else and writes nothing but
that offset file. The static rules for every hook and monitor script are in test_hook_scripts.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "plan-watch.sh"
BASH = "/bin/bash" if os.path.exists("/bin/bash") else (shutil.which("bash") or "bash")
PATH = ":".join(dict.fromkeys(["/usr/bin", "/bin", "/usr/sbin", "/sbin"]))


class _Watch:
    def __init__(self, cwd: Path, max_seconds: int = 20, env: dict | None = None) -> None:
        e = {"PATH": PATH, "HOME": str(cwd), "LANG": "C", "MAGICIAN_PLAN_WATCH_MAX_SECONDS": str(max_seconds)}
        e.update(env or {})
        self.proc = subprocess.Popen([BASH, str(SCRIPT)], cwd=cwd, env=e, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)

    def finish(self, timeout: float = 30) -> tuple:
        try:
            out, err = self.proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, err = self.proc.communicate()
            raise AssertionError(f"plan-watch.sh did not exit within {timeout}s; output so far:\n{out}")
        return self.proc.returncode, out, err


class PlanWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        self.state = self.cwd / ".workspace" / "local" / "plans" / "2026-11-01-demo" / "state"
        self.state.mkdir(parents=True)
        self.log = self.state / "events.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _append(self, text: str) -> None:
        with self.log.open("a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

    def _approve(self) -> None:
        (self.state / "state.json").write_text(json.dumps({"version": 1, "status": "approved", "steps": {}}), encoding="utf-8")

    def test_prints_new_lines_only_and_stops_on_approved(self) -> None:
        self._append('{"id":"old-1","type":"step.review"}\n{"id":"old-2","type":"step.review"}\n')
        w = _Watch(self.cwd)
        time.sleep(1)
        self._append('{"id":"new-1","type":"step.change_request","step":"T1","text":"x"}\n')
        time.sleep(2.5)
        self._append('{"id":"new-2","type":"plan.approved"}\n')
        time.sleep(0.5)
        self._approve()
        rc, out, err = w.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.splitlines(), [
            'plan-event: {"id":"new-1","type":"step.change_request","step":"T1","text":"x"}',
            'plan-event: {"id":"new-2","type":"plan.approved"}'])
        self.assertEqual((self.state / "plan-watch.offset").read_text().strip(), str(self.log.stat().st_size))
        extra = sorted(p.name for p in self.state.iterdir())
        self.assertEqual(extra, ["events.jsonl", "plan-watch.offset", "state.json"])

    def test_stops_on_rejected_and_exits_0_at_the_cap(self) -> None:
        self._append('{"id":"a"}\n')
        (self.state / "state.json").write_text('{"version": 1, "status": "rejected"}', encoding="utf-8")
        rc, out, _ = _Watch(self.cwd).finish(timeout=15)
        self.assertEqual((rc, out), (0, ""))
        (self.state / "state.json").write_text('{"version": 1, "status": "in_review"}', encoding="utf-8")
        t0 = time.monotonic()
        rc, out, err = _Watch(self.cwd, max_seconds=3).finish(timeout=15)
        self.assertEqual((rc, out, err), (0, "", ""))
        self.assertLess(time.monotonic() - t0, 10)

    def test_control_characters_are_stripped_and_lines_cut_at_2_kb(self) -> None:
        self._append("")
        w = _Watch(self.cwd)
        time.sleep(1)
        long = '{"type":"plan.change_request","text":"' + "x" * 3000 + '"}'
        self._append('{"t":"a\x07b\x1b[31mc\td\x7fe"}\n' + long + "\n")
        time.sleep(3)
        self._approve()
        rc, out, _ = w.finish()
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'plan-event: {"t":"ab[31mcde"}')
        self.assertEqual(lines[1], "plan-event: " + long[:2048])
        self.assertEqual(len(lines[1].encode()), len("plan-event: ") + 2048)

    def test_waits_for_a_complete_line_and_never_prints_a_fragment(self) -> None:
        self._append("")
        w = _Watch(self.cwd)
        time.sleep(1)
        self._append('{"id":"half')
        time.sleep(3)
        self._append('","done":true}\n')
        time.sleep(3)
        self._approve()
        rc, out, _ = w.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ['plan-event: {"id":"half","done":true}'])

    def test_a_log_that_appears_while_waiting_is_read_from_its_first_line(self) -> None:
        shutil.rmtree(self.state.parent)
        w = _Watch(self.cwd)
        time.sleep(1)
        self.state.mkdir(parents=True)
        self._append('{"id":"first"}\n')
        time.sleep(3)
        self._approve()
        rc, out, _ = w.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ['plan-event: {"id":"first"}'])

    def test_a_recorded_offset_resumes_where_the_last_watch_stopped(self) -> None:
        self._append('{"id":"seen"}\n')
        (self.state / "plan-watch.offset").write_text(f"{self.log.stat().st_size}\n")
        self._append('{"id":"missed-while-away"}\n')
        self._approve()
        rc, out, _ = _Watch(self.cwd).finish(timeout=15)
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ['plan-event: {"id":"missed-while-away"}'])

    def test_pinned_state_folder_and_newest_plan_selection(self) -> None:
        older = self.cwd / ".workspace" / "local" / "plans" / "2026-10-01-old" / "state"
        older.mkdir(parents=True)
        (older / "events.jsonl").write_text('{"id":"old-plan"}\n', encoding="utf-8")
        past = time.time() - 3600
        os.utime(older / "events.jsonl", (past, past))
        self._append('{"id":"current"}\n')
        self._approve()
        # the newest log wins: it is already finished, so the watch prints nothing and exits
        rc, out, _ = _Watch(self.cwd).finish(timeout=15)
        self.assertEqual((rc, out), (0, ""))
        # MAGICIAN_PLAN_STATE pins the folder, wherever the working directory is
        (older / "state.json").write_text('{"status":"in_review"}', encoding="utf-8")
        with tempfile.TemporaryDirectory() as elsewhere:
            w = _Watch(Path(elsewhere), env={"MAGICIAN_PLAN_STATE": str(older)})
            time.sleep(1)
            with (older / "events.jsonl").open("a", encoding="utf-8") as f:
                f.write('{"id":"pinned"}\n')
            time.sleep(3)
            (older / "state.json").write_text('{"status":"approved"}', encoding="utf-8")
            rc, out, _ = w.finish()
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ['plan-event: {"id":"pinned"}'])

    def test_no_plan_folder_prints_nothing_and_exits_0_at_the_cap(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            rc, out, err = _Watch(Path(empty), max_seconds=2).finish(timeout=15)
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_monitor_wiring(self) -> None:
        monitors = json.loads((ROOT / "monitors" / "monitors.json").read_text(encoding="utf-8"))
        (mon,) = [m for m in monitors if m["name"] == "plan-watch"]
        self.assertEqual(mon["command"], '"${CLAUDE_PLUGIN_ROOT}"/scripts/plan-watch.sh')
        self.assertEqual(mon["when"], "on-skill-invoke:blueprint")
        self.assertTrue((ROOT / "skills" / "blueprint" / "SKILL.md").is_file())
        self.assertEqual(set(mon), {"name", "command", "description", "when"})
        self.assertIn("events.jsonl", mon["description"])
        self.assertNotRegex(mon["description"].lower(), r"\bpings? claude\b")
        self.assertTrue(os.access(SCRIPT, os.X_OK))


if __name__ == "__main__":
    unittest.main()

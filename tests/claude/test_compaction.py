"""Compaction-integrity contract — compaction is a security/continuity boundary.

Context compaction can silently drop a negative constraint ("never touch prod") or an open thread,
and the model that wakes up on the far side never knows it lost them. The plugin's answer is the
PreCompact hook: it CAPTURES a resume capsule (goal, open threads, decisions, changed files) before
compaction and re-injects it afterward. This gate proves that chain end-to-end on an isolated store:
the hook fails open, it actually writes a capsule, and a load-bearing negative constraint survives
capture AND re-injection. If this regresses, the boundary leaks constraints — so it is graded here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PRE_COMPACT = ROOT / "scripts" / "pre-compact.sh"
CTX = ROOT / "bin" / "ctx"

# A goal carrying a NEGATIVE constraint — exactly the kind of instruction compaction tends to lose.
GOAL = ("Implement the payment retry logic. Absolute constraint: never touch the production "
        "database directly — all writes go through the staging queue.")
CONSTRAINT_MARKER = "never touch the production database"
THREAD_MARKER = "wire the exponential backoff"


def _transcript(path: Path) -> None:
    """Write a minimal transcript JSONL the ctx capsule builder can parse."""
    lines = [
        {"type": "user", "message": {"role": "user", "content": GOAL}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": f"- next step: {THREAD_MARKER}\n- waiting on: staging queue creds"}
        ], "usage": {"input_tokens": 1234}}},
    ]
    path.write_text("\n".join(json.dumps(o) for o in lines) + "\n", encoding="utf-8")


def _env(store: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_DATA"] = str(store)          # isolate the capsule store from the real one
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    return env


class CompactionIntegrityTests(unittest.TestCase):
    def test_pre_compact_hook_fails_open_on_bad_input(self) -> None:
        """A PreCompact hook that errored could BLOCK compaction and wedge the session. It must exit 0
        no matter what it is fed — empty stdin, junk, or a valid event."""
        with tempfile.TemporaryDirectory() as tmp:
            for payload in ("", "not json", "{}"):
                with self.subTest(payload=payload):
                    result = subprocess.run(
                        ["bash", str(PRE_COMPACT)], input=payload, text=True,
                        capture_output=True, cwd=str(ROOT), env=_env(Path(tmp)), check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_pre_compact_hook_captures_a_capsule(self) -> None:
        """The full hook → ctx → capsule chain: firing PreCompact with a real transcript must leave a
        capsule on disk that preserves the goal's negative constraint and an open thread."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            tpath = store / "transcript.jsonl"
            _transcript(tpath)
            event = json.dumps({
                "session_id": "gate-test",
                "transcript_path": str(tpath),
                "trigger": "auto",
                "hook_event_name": "PreCompact",
            })
            result = subprocess.run(
                ["bash", str(PRE_COMPACT)], input=event, text=True,
                capture_output=True, cwd=str(ROOT), env=_env(store), check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            capsules = list(store.glob("projects/*/capsule.md"))
            self.assertTrue(capsules, "PreCompact produced no capsule")
            body = capsules[0].read_text(encoding="utf-8")
            self.assertIn(CONSTRAINT_MARKER, body,
                          "negative constraint did not survive capture into the capsule")
            self.assertIn(THREAD_MARKER, body, "open thread did not survive into the capsule")

    def test_constraint_survives_re_injection_across_the_boundary(self) -> None:
        """Capture is only half the boundary — the constraint must come BACK on resume. Build a capsule,
        then run `ctx resume` and assert the negative constraint is re-emitted for the far-side model."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            tpath = store / "transcript.jsonl"
            _transcript(tpath)
            cap = subprocess.run(
                [sys.executable, str(CTX), "capsule", "--session", "gate", "--transcript", str(tpath),
                 "--trigger", "auto"],
                text=True, capture_output=True, cwd=str(ROOT), env=_env(store), check=False,
            )
            self.assertEqual(cap.returncode, 0, cap.stderr)

            resume = subprocess.run(
                [sys.executable, str(CTX), "resume"],
                text=True, capture_output=True, cwd=str(ROOT), env=_env(store), check=False,
            )
            self.assertEqual(resume.returncode, 0, resume.stderr)
            self.assertIn(CONSTRAINT_MARKER, resume.stdout,
                          "negative constraint was not re-injected on resume — boundary leaked it")


if __name__ == "__main__":
    unittest.main()

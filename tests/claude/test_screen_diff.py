"""Behavior contract for `skills/conjure/scripts/screen-diff.cjs`.

The script compares two folders of evidence screenshots (see `skills/conjure/references/capture.md`).
Its header documents the exit codes: 0 when every shared screenshot is within `--max-ratio`, 1 when
at least one is not, 2 for a usage error (for example, a folder that does not exist). These tests
build tiny PNGs with the standard library (zlib + struct, 8-bit RGBA) so no image library is needed,
and run the script with `--engine stdlib` so the result does not depend on whether Playwright is
installed. One extra test runs the Playwright engine when Playwright can be found. All tests skip
when `node` is not on PATH.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "conjure" / "scripts" / "screen-diff.cjs"
NODE = shutil.which("node")

WIDTH, HEIGHT = 16, 16
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def make_png(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Encode rows of RGBA tuples as an 8-bit RGBA, non-interlaced PNG (filter 0 on every row)."""
    height, width = len(pixels), len(pixels[0])
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def canvas(block: int = 0) -> list[list[tuple[int, int, int, int]]]:
    """A white WIDTH x HEIGHT image; when block > 0, a black block x block square at the top left."""
    return [[BLACK if (x < block and y < block) else WHITE for x in range(WIDTH)] for y in range(HEIGHT)]


@unittest.skipUnless(NODE, "node is not on PATH; screen-diff.cjs is a Node script")
class ScreenDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="screen-diff-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _folder(self, name: str, images: dict[str, bytes]) -> Path:
        d = self.tmp / name
        d.mkdir()
        for fname, data in images.items():
            (d / fname).write_bytes(data)
        return d

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [NODE, str(SCRIPT), *args], cwd=self.tmp, capture_output=True, text=True, timeout=60,
        )

    def test_script_passes_node_check(self) -> None:
        r = subprocess.run([NODE, "--check", str(SCRIPT)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_identical_folders_exit_zero(self) -> None:
        # Two separately encoded copies of the same image, so the byte-equal shortcut is not the
        # only path: one copy uses a different zlib level and is decoded and compared pixel by pixel.
        pixels = canvas()
        same = make_png(pixels)
        raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)
        relevel = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 6, 0, 0, 0))
                   + _chunk(b"IDAT", zlib.compress(raw, 1)) + _chunk(b"IEND", b""))
        a = self._folder("a", {"light-desktop.png": same, "dark-desktop.png": same})
        b = self._folder("b", {"light-desktop.png": same, "dark-desktop.png": relevel})
        r = self._run(str(a), str(b), "--engine", "stdlib", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual({x["status"] for x in report["results"]}, {"same"})

    def test_changed_block_exits_one_and_reports_count_and_ratio(self) -> None:
        a = self._folder("a", {"light-desktop.png": make_png(canvas())})
        b = self._folder("b", {"light-desktop.png": make_png(canvas(block=4))})
        r = self._run(str(a), str(b), "--engine", "stdlib", "--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        (entry,) = json.loads(r.stdout)["results"]
        self.assertEqual(entry["status"], "changed")
        self.assertEqual(entry["engine"], "stdlib")
        self.assertEqual(entry["pixels"], 16)
        self.assertEqual(entry["total"], WIDTH * HEIGHT)
        self.assertAlmostEqual(entry["ratio"], 16 / (WIDTH * HEIGHT), places=6)

    def test_changed_block_text_output_shows_percentage(self) -> None:
        a = self._folder("a", {"light-desktop.png": make_png(canvas())})
        b = self._folder("b", {"light-desktop.png": make_png(canvas(block=4))})
        r = self._run(str(a), str(b), "--engine", "stdlib")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("6.25% of pixels", r.stdout)
        self.assertIn("engine: stdlib", r.stdout)

    def test_missing_folder_is_a_usage_error(self) -> None:
        a = self._folder("a", {"light-desktop.png": make_png(canvas())})
        r = self._run(str(a), str(self.tmp / "does-not-exist"))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not a folder", r.stderr)

    def test_unknown_engine_is_a_usage_error(self) -> None:
        a = self._folder("a", {})
        b = self._folder("b", {})
        r = self._run(str(a), str(b), "--engine", "pixelmatch")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_playwright_engine_writes_diff_image_when_available(self) -> None:
        a = self._folder("a", {"light-desktop.png": make_png(canvas())})
        b = self._folder("b", {"light-desktop.png": make_png(canvas(block=4))})
        out = self.tmp / "out"
        r = self._run(str(a), str(b), "--engine", "playwright", "--out", str(out), "--json")
        if r.returncode == 2 and "Playwright not found" in r.stderr:
            self.skipTest("Playwright is not installed in the project or globally")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        (entry,) = json.loads(r.stdout)["results"]
        self.assertEqual(entry["engine"], "playwright")
        self.assertGreater(entry["pixels"], 0)
        self.assertTrue((out / "light-desktop.diff.png").is_file(), "no <name>.diff.png written")
        # Identical folders under the Playwright engine still exit 0.
        r = self._run(str(a), str(a), "--engine", "playwright")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

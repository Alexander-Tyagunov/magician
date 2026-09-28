"""SessionStart hook scripts/tools-path.sh: the bundled commands on the Bash tool's PATH.

The commands ship in tools/ (a top-level bin/ keeps a plugin out of Claude chat and Cowork), so Claude
Code no longer puts them on PATH. The hook writes one launcher per command into a folder per plugin
root under CLAUDE_PLUGIN_DATA/tools and appends one line to the session env file that puts that
folder first on PATH. These tests pin the launchers, the line, its dedup, updates and concurrent
versions, what else may be in the folder, and the paths it refuses.

Every subprocess gets a fully specified env built from temp dirs; nothing (least of all the session
env file of the session running the suite) is inherited from the parent process.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

import _strict_frontmatter as S


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts" / "tools-path.sh"
ENV_KEY = "CLAUDE_" + "ENV_FILE"
# Every launcher shadows a command of the same name in Claude's shell, so a new bundled command is a
# reviewed change to this set, never a side effect of adding a file to tools/.
SHIPPED = ["confluence", "ctx", "jira", "kg", "magician-scan", "magician-statusline", "magician-ui"]


def _bash() -> str:
    return "/bin/bash" if Path("/bin/bash").exists() else (shutil.which("bash") or "bash")


def _tool(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _key(root: Path | str) -> str:
    return str(root).replace("=", "=3D").replace("/", "=2F").replace(":", "=3A")


class ToolsPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.data = self.tmp / "plugin-data"
        self.env_file = self.tmp / "session.env"
        self.root = self.tmp / "root"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(self, root: Path | str = ROOT, data: Path | str | None = None, env_file: bool = True,
                 path: str = "/usr/bin:/bin") -> subprocess.CompletedProcess:
        env = {"PATH": path, "HOME": str(self.tmp), "LC_ALL": "C",
               "CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_DATA": str(data or self.data)}
        if env_file:
            env[ENV_KEY] = str(self.env_file)
        p = subprocess.run([_bash(), str(HOOK)], env=env, cwd=self.tmp,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "", "the hook must never print to stdout")
        return p

    def launchers(self, root: Path | str = ROOT, data: Path | None = None) -> Path:
        return (data or self.data) / "tools" / _key(root)

    def path_line(self, root: Path | str = ROOT) -> str:
        return "export PATH='" + str(self.launchers(root)) + "'${PATH:+:\"$PATH\"}"

    def lines(self) -> list[str]:
        return self.env_file.read_text(encoding="utf-8").splitlines()

    def resolve(self, shell: str, name: str, *args: str, path: str = "/usr/bin:/bin",
                ) -> subprocess.CompletedProcess:
        """Source the env file in a clean shell, then report where `name` resolves and run it."""
        script = '. "$1"; shift; command -v "$1"; "$@"'
        return subprocess.run([shell, "-c", script, "sh", str(self.env_file), name, *args],
                              env={"PATH": path, "HOME": str(self.tmp), "LC_ALL": "C"},
                              capture_output=True, text=True, timeout=20)

    # ------------------------------------------------------------ the real plugin
    def test_every_bundled_command_gets_a_launcher_and_one_path_line(self) -> None:
        self.assertEqual(sorted(p.name for p in (ROOT / "tools").iterdir() if p.is_file()), SHIPPED)
        self.assertTrue(all(os.access(ROOT / "tools" / n, os.X_OK) for n in SHIPPED))
        self.run_hook()
        self.run_hook()   # resume, clear and compact run SessionStart again
        launchers = self.launchers()
        self.assertEqual(sorted(p.name for p in launchers.iterdir()), SHIPPED)
        for name in SHIPPED:
            with self.subTest(command=name):
                launcher = launchers / name
                self.assertTrue(launcher.stat().st_mode & stat.S_IXUSR)
                self.assertEqual(launcher.read_text(encoding="utf-8"),
                                 f"#!/bin/sh\nexec '{ROOT / 'tools' / name}' \"$@\"\n")
        self.assertEqual(self.lines(), [self.path_line()])
        self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(launchers.stat().st_mode), 0o700)

    def test_the_path_line_puts_the_launchers_first_in_bash_and_sh(self) -> None:
        root = self.tmp / "plugin 'root' =x"
        _tool(root / "tools", "kg", 'printf "%s|" "$@"')
        shadow = self.tmp / "shadow"
        _tool(shadow, "kg", "echo shadowed")
        self.run_hook(root)
        for shell in (_bash(), "/bin/sh"):
            with self.subTest(shell=shell):
                p = self.resolve(shell, "kg", "a b", "c'd", "$HOME", path=f"{shadow}:/usr/bin:/bin")
                self.assertEqual(p.returncode, 0, p.stderr)
                where, out = p.stdout.split("\n", 1)
                self.assertEqual(where, str(self.launchers(root) / "kg"))
                self.assertEqual(out, "a b|c'd|$HOME|")

    def test_an_empty_path_does_not_become_the_current_folder(self) -> None:
        _tool(self.root / "tools", "kg", "true")
        self.run_hook(self.root)
        p = subprocess.run(["/bin/sh", "-c", 'PATH=; . "$1"; printf %s "$PATH"', "sh", str(self.env_file)],
                           env={"HOME": str(self.tmp)}, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stdout, str(self.launchers(self.root)))

    # ------------------------------------------------------------ versions and leftovers
    def test_an_update_adds_a_line_that_wins_and_keeps_the_old_launchers(self) -> None:
        old, new = self.tmp / "4.16.0", self.tmp / "4.16.1"
        _tool(old / "tools", "kg", "echo old")
        _tool(old / "tools", "retired", "echo retired")
        _tool(new / "tools", "kg", "echo new")
        self.run_hook(old)
        self.run_hook(new)
        self.run_hook(new)
        self.assertEqual(self.lines(), [self.path_line(old), self.path_line(new)])
        self.assertEqual(self.resolve(_bash(), "kg").stdout.splitlines()[-1], "new")
        # A session still on the old version keeps its own launchers.
        self.assertEqual(sorted(p.name for p in self.launchers(old).iterdir()), ["kg", "retired"])
        self.assertEqual(sorted(p.name for p in self.launchers(new).iterdir()), ["kg"])

    def test_sessions_on_two_versions_do_not_repoint_each_other(self) -> None:
        a, b = self.tmp / "a", self.tmp / "b"
        _tool(a / "tools", "kg", "echo a")
        _tool(b / "tools", "kg", "echo b")
        _tool(b / "tools", "newcmd", "echo b")
        env_a, env_b = self.tmp / "a.env", self.tmp / "b.env"
        self.env_file = env_b
        self.run_hook(b)
        self.env_file = env_a
        self.run_hook(a)   # a compact in the older session
        self.env_file = env_b
        self.assertEqual(self.resolve(_bash(), "kg").stdout.splitlines()[-1], "b")
        self.assertEqual(self.resolve(_bash(), "newcmd").stdout.splitlines()[-1], "b")

    def test_folders_of_removed_versions_are_removed(self) -> None:
        old, new = self.tmp / "4.16.0", self.tmp / "4.16.1"
        _tool(old / "tools", "kg", "true")
        _tool(new / "tools", "kg", "true")
        self.run_hook(old)
        shutil.rmtree(old)
        (self.data / "tools" / "not-a-root").mkdir()
        self.run_hook(new)
        self.assertEqual(sorted(p.name for p in (self.data / "tools").iterdir()),
                         sorted(["not-a-root", _key(new)]))

    def test_it_never_runs_a_bundled_command(self) -> None:
        marker = self.tmp / "ran"
        _tool(self.root / "tools", "kg", f"touch '{marker}'")
        self.run_hook(self.root)
        self.assertFalse(marker.exists())

    def test_non_commands_and_odd_names_are_skipped(self) -> None:
        tools = self.root / "tools"
        _tool(tools, "kg", "true")
        (tools / "notes.txt").write_text("not executable\n")
        (tools / "__pycache__").mkdir()
        _tool(tools, "bad name", "true")
        _tool(tools, "bad\nname", "true")
        self.run_hook(self.root)
        self.assertEqual(sorted(p.name for p in self.launchers(self.root).iterdir()), ["kg"])

    def test_a_command_that_lost_its_exec_bit_loses_its_launcher(self) -> None:
        kg = _tool(self.root / "tools", "kg", "true")
        _tool(self.root / "tools", "ctx", "true")
        self.run_hook(self.root)
        kg.chmod(0o644)
        self.run_hook(self.root)
        self.assertEqual(sorted(p.name for p in self.launchers(self.root).iterdir()), ["ctx"])

    def test_a_folder_in_the_way_is_left_alone_with_a_note(self) -> None:
        _tool(self.root / "tools", "kg", "true")
        (self.launchers(self.root) / "kg").mkdir(parents=True)
        p = self.run_hook(self.root)
        self.assertIn("kg not added to PATH", p.stderr)
        self.assertEqual(list((self.launchers(self.root) / "kg").iterdir()), [])
        self.assertFalse(self.env_file.exists(), "no launcher written, so no PATH line")

    # ------------------------------------------------------------ what else is in the folder
    def test_anything_but_the_launchers_is_removed_without_touching_link_targets(self) -> None:
        _tool(self.root / "tools", "kg", "echo launcher")
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep\n")
        launchers = self.launchers(self.root)
        launchers.mkdir(parents=True)
        _tool(launchers, "python3", "echo planted")
        (launchers / "git").symlink_to(self.tmp / "nowhere")          # dangling
        (launchers / ".kg.4242").symlink_to(outside / "keep")         # a temporary name
        (launchers / ".hidden").write_text("x\n")
        (launchers / "kg").symlink_to(outside)                        # a linked folder
        self.run_hook(self.root)
        self.assertEqual(sorted(p.name for p in launchers.iterdir()), ["kg"])
        self.assertFalse((launchers / "kg").is_symlink())
        self.assertEqual(self.resolve(_bash(), "kg").stdout.splitlines()[-1], "launcher")
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["keep"])
        self.assertEqual((outside / "keep").read_text(), "keep\n")

    def test_a_link_at_the_temporary_name_is_never_written_through(self) -> None:
        _tool(self.root / "tools", "kg", "echo launcher")
        victim = self.tmp / "settings.json"
        victim.write_text("{}\n")
        mode = stat.S_IMODE(victim.stat().st_mode)
        launchers = self.launchers(self.root)
        launchers.mkdir(parents=True)
        # exec keeps the PID, so the link sits at exactly the hook's temporary name .kg.$$
        wrapper = 'ln -s "$1" "$2/.kg.$$" && exec "$3" "$4"'
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "LC_ALL": "C", ENV_KEY: str(self.env_file),
               "CLAUDE_PLUGIN_ROOT": str(self.root), "CLAUDE_PLUGIN_DATA": str(self.data)}
        p = subprocess.run(["/bin/sh", "-c", wrapper, "sh", str(victim), str(launchers), _bash(), str(HOOK)],
                           env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual((p.returncode, p.stdout), (0, ""), p.stderr)
        self.assertEqual(victim.read_text(), "{}\n")
        self.assertEqual(stat.S_IMODE(victim.stat().st_mode), mode)
        self.assertEqual(sorted(p.name for p in launchers.iterdir()), ["kg"])
        self.assertEqual(self.resolve(_bash(), "kg").stdout.splitlines()[-1], "launcher")

    def test_linked_launcher_folders_are_refused(self) -> None:
        _tool(self.root / "tools", "kg", "true")
        target = self.tmp / "my-bin"
        _tool(target, "mine", "true")
        for link in (self.data / "tools", self.launchers(self.root)):
            with self.subTest(link=link.name):
                shutil.rmtree(self.data, ignore_errors=True)
                link.parent.mkdir(parents=True)
                link.symlink_to(target)
                p = self.run_hook(self.root)
                self.assertIn("not added to PATH", p.stderr)
                self.assertEqual(sorted(p.name for p in target.iterdir()), ["mine"])
                self.assertFalse(self.env_file.exists())

    # ------------------------------------------------------------ the env file
    def test_an_existing_file_keeps_its_mode_and_gets_a_line_of_its_own(self) -> None:
        self.env_file.write_text("export A=1")
        self.env_file.chmod(0o640)
        self.run_hook()
        self.assertEqual(self.lines(), ["export A=1", self.path_line()])
        self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o640)

    def test_a_data_path_with_quotes_and_dollars_is_written_literally(self) -> None:
        data = self.tmp / "da'ta $HOME `x`"
        _tool(self.root / "tools", "kg", "echo ran")
        self.run_hook(self.root, data=data)
        for shell in (_bash(), "/bin/sh"):
            with self.subTest(shell=shell):
                p = self.resolve(shell, "kg")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.splitlines(),
                                 [str(self.launchers(self.root, data) / "kg"), "ran"])

    def test_windows_paths_are_converted_with_cygpath(self) -> None:
        _tool(self.root / "tools", "kg", "echo ran")
        stubs = self.tmp / "stubs"
        _tool(stubs, "cygpath", f"""[ "$1" = -u ] || exit 1
case "$2" in
  'C:\\root') printf '%s\\n' '{self.root}' ;;
  'C:\\data') printf '%s\\n' '{self.data}' ;;
  *) exit 1 ;;
esac""")
        p = self.run_hook("C:\\root", data="C:\\data", path=f"{stubs}:/usr/bin:/bin")
        self.assertEqual(p.stderr, "")
        self.assertEqual(self.lines(), [self.path_line(self.root)])
        self.assertEqual(self.resolve(_bash(), "kg").stdout.splitlines()[-1], "ran")

    def test_paths_path_cannot_carry_are_refused(self) -> None:
        _tool(self.root / "tools", "kg", "true")
        _tool(self.tmp / "ro\not" / "tools", "kg", "true")
        cases = [(self.root, self.tmp / "da:ta"), (self.root, self.tmp / "da\nta"),
                 (self.tmp / "ro\not", self.data), (self.root, "C:\\data")]   # no cygpath on PATH
        for root, data in cases:
            with self.subTest(root=str(root), data=str(data)):
                p = self.run_hook(root, data=data)
                self.assertIn("not added to PATH", p.stderr)
                self.assertFalse(self.env_file.exists())
                self.assertFalse(Path(data).exists())

    def test_nothing_happens_without_an_env_file_data_folder_tools_or_absolute_paths(self) -> None:
        _tool(self.root / "tools", "kg", "true")
        self.run_hook(self.root, env_file=False)
        self.assertFalse(self.data.exists())
        self.run_hook(self.tmp / "no-tools")
        self.run_hook("root")
        self.run_hook(self.root, data="plugin-data")
        self.assertFalse(self.env_file.exists())
        self.assertFalse(self.data.exists())


class SkillFallbackTests(unittest.TestCase):
    """A skill that pre-approves a bundled command says where it lives when PATH doesn't have it
    (the hook didn't run, or Claude chat, which ships no plugin tools). The Codex build strips these
    lines by their fixed prefix."""

    PREFIX = "> **Bundled command:** if `{cli}` is not found, run it as `${{CLAUDE_PLUGIN_ROOT}}/tools/{cli}`"

    def test_every_granted_bundled_command_has_one_fallback_line(self) -> None:
        granting = 0
        for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
            fields, _, body = S.parse_strict(skill)
            clis = sorted({g[len("Bash("):].split()[0].split(":")[0].rstrip(")")
                           for g in S.split_tools(fields.get("allowed-tools", ""))
                           if g.startswith("Bash(")} & set(SHIPPED))
            notes = [line for line in body.splitlines() if line.startswith("> **Bundled command:**")]
            with self.subTest(skill=skill.parent.name):
                self.assertEqual([n[:len(self.PREFIX.format(cli=c))] for c, n in zip(clis, notes)],
                                 [self.PREFIX.format(cli=c) for c in clis])
                self.assertEqual(len(notes), len(clis))
            granting += bool(clis)
        self.assertGreaterEqual(granting, 17)


if __name__ == "__main__":
    unittest.main()

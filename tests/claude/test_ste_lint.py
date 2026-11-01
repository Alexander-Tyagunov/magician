"""Contract for `tools/ste-lint`, the STE-lite checker for Markdown prose.

Each rule has a positive sample (one finding, the right rule) and a negative sample (no finding);
the exclusions (frontmatter, fenced and inline code, URLs, tables, blockquotes, quoted text) never
produce a finding; STE word counting (inline code, a path, a number with its unit, a hyphenated
group and a parenthetical count as one word); the per-project allow-list; `--max`; the `--json`
shape; exit codes; `-h`; and the tool file itself: executable, stdlib-only Python, under 200 KiB.
The tool runs as a subprocess with a fully specified environment, as the hook runs it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "ste-lint"

# The rule ids the tool documents, by level. The table in the module docstring is the contract.
ERRORS = ("S1", "S2", "P1", "V2", "V3", "W2", "W3", "W4", "W6", "C1")
WARNS = ("S3", "S4", "S5", "V1", "V4", "W1", "N1", "L1")


def run(args, stdin: str | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "HOME": cwd or "/", "LC_ALL": "C"}
    return subprocess.run([str(TOOL), *args], input=stdin, capture_output=True, text=True, env=env,
                          cwd=cwd, timeout=60, check=False)


def lint(text: str, *args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return run(["--stdin", "--max", "0", *args], stdin=text, cwd=cwd)


def rules(text: str, *args: str, cwd: str | None = None) -> list:
    """The (level, rule) pairs the tool reports for TEXT, in output order."""
    out = []
    for line in lint(text, *args, cwd=cwd).stdout.splitlines():
        m = re.match(r"<stdin>:\d+: (warn )?([A-Z]\d): ", line)
        if m:
            out.append(("warn" if m.group(1) else "error", m.group(2)))
    return out


def words(n: int, word: str = "word") -> str:
    return " ".join(word for _ in range(n))


class RuleSamples(unittest.TestCase):
    """One positive and one negative sample per rule."""

    def assert_rule(self, rule: str, level: str, positive: str, negative: str) -> None:
        with self.subTest(rule=rule, sample="positive"):
            found = rules(positive)
            self.assertIn((level, rule), found, (positive, found))
        with self.subTest(rule=rule, sample="negative"):
            found = rules(negative)
            self.assertNotIn((level, rule), found, (negative, found))

    def test_S1_descriptive_sentence_over_25_words(self) -> None:
        self.assert_rule("S1", "error", "The " + words(25) + " end.\n", "The " + words(23) + " end.\n")

    def test_S2_procedural_sentence_over_20_words(self) -> None:
        self.assert_rule("S2", "error", "1. Run the " + words(19) + " end.\n", "1. Run the " + words(17) + " end.\n")
        # An unnumbered sentence that starts with an imperative verb is a step too.
        self.assertIn(("error", "S2"), rules("Open the " + words(19) + " end.\n"))
        # A descriptive sentence of 21 words is not a step and is within its own limit.
        self.assertEqual(rules("The " + words(19) + " end.\n"), [])

    def test_P1_more_than_6_sentences_per_paragraph(self) -> None:
        seven = " ".join("The cat sits." for _ in range(7)) + "\n"
        six = " ".join("The cat sits." for _ in range(6)) + "\n"
        self.assert_rule("P1", "error", seven, six)

    def test_V2_perfect_and_progressive_tenses(self) -> None:
        self.assert_rule("V2", "error", "The build has finished.\n", "The build finished.\n")
        self.assertIn(("error", "V2"), rules("The job is running now.\n"))
        self.assertEqual(rules("The job runs now.\n"), [])
        self.assertEqual(rules("We have three tests.\n"), [], "have + noun is not a perfect tense")
        self.assertEqual(rules("The thing is something.\n"), [], "-ing nouns are not progressive forms")

    def test_V3_gerund_headed_sentence(self) -> None:
        self.assert_rule("V3", "error", "Running the tests takes a minute.\n", "The tests take a minute.\n")
        self.assertEqual(rules("Nothing happens here.\n"), [])

    def test_W2_semicolon(self) -> None:
        self.assert_rule("W2", "error", "Run it; then stop.\n", "Run it. Then stop.\n")
        self.assertEqual(rules("Use the &amp; entity here.\n"), [], "an HTML entity is not a semicolon")

    def test_W3_contractions(self) -> None:
        self.assert_rule("W3", "error", "It doesn't work.\n", "It does not work.\n")
        self.assertIn(("error", "W3"), rules("It’s broken.\n"), "a curly apostrophe counts")
        self.assertEqual(rules("The user's file is kept.\n"), [], "a possessive is not a contraction")
        out = lint("We don't stop.\n").stdout
        self.assertIn('contraction "don\'t"; write "do not"', out)

    def test_W4_word_list(self) -> None:
        self.assert_rule("W4", "error", "We utilize the cache.\n", "We use the cache.\n")
        self.assertIn(("error", "W4"), rules("Check it prior to the build.\n"), "a phrase on the list")
        self.assertIn(("error", "W4"), rules("The job modifies the file.\n"), "an inflected verb on the list")
        self.assertEqual(rules("Validate the schema and execute the command.\n"), [],
                         "software technical verbs are not on the list")
        out = lint("We utilize the cache.\n").stdout
        self.assertIn('"utilize"; use "use"', out)

    def test_W6_latin_abbreviations(self) -> None:
        self.assert_rule("W6", "error", "Use a tool, e.g. a linter.\n", "Use a tool, for example a linter.\n")
        for abbr in ("i.e.", "etc.", "vs."):
            with self.subTest(abbr=abbr):
                self.assertIn(("error", "W6"), rules("Tools " + abbr + " linters.\n"))

    def test_C1_identifiers_outside_backticks(self) -> None:
        self.assert_rule("C1", "error", "Read the file_path value.\n", "Read the `file_path` value.\n")
        for ident in ("fooBar", "src/app.py", "--max", "-h", ".workspace/shared/", "/etc/hosts", "MAGICIAN_STE"):
            with self.subTest(ident=ident):
                self.assertIn(("error", "C1"), rules("Use " + ident + " here.\n"))
        for plain in ("I/O", "PR/MR", "v1.2.3", "Node.js", "a well-known word", "an em-dash -- here"):
            with self.subTest(plain=plain):
                self.assertNotIn(("error", "C1"), rules("Use " + plain + " here.\n"))

    def test_S3_one_instruction_per_sentence(self) -> None:
        self.assert_rule("S3", "warn", "1. Open the file and then run the tests.\n",
                         "1. Open the file.\n2. Run the tests.\n")
        self.assertEqual(rules("1. Hold the key and press the button at the same time.\n"), [])

    def test_S4_imperative_form_in_steps(self) -> None:
        self.assert_rule("S4", "warn", "1. You should run the tests.\n", "1. Run the tests.\n")

    def test_S5_condition_before_command(self) -> None:
        self.assert_rule("S5", "warn", "1. Run the tests if the build passes.\n",
                         "1. If the build passes, run the tests.\n")

    def test_V1_passive_voice(self) -> None:
        self.assert_rule("V1", "warn", "1. The file is written by the job.\n", "1. The job writes the file.\n")
        self.assertEqual(rules("The file is written to disk.\n"), [],
                         "a descriptive passive with no agent is left alone")
        self.assertIn(("warn", "V1"), rules("The file is written by the job.\n"))

    def test_V4_verbs_not_nominalisations(self) -> None:
        self.assert_rule("V4", "warn", "Perform a validation of the input.\n", "Validate the input.\n")

    def test_W1_noun_cluster(self) -> None:
        self.assert_rule("W1", "warn", "Clear the Static Site Build Cache Layer first.\n",
                         "Clear the cache layer of the static site build first.\n")

    def test_N1_warning_lines(self) -> None:
        self.assert_rule("N1", "warn", "WARNING: this " + words(20) + " end.\n", "WARNING: Stop the pump first.\n")
        self.assertIn(("warn", "N1"), rules("CAUTION: The data goes away.\n"), "starts with no command or condition")
        self.assertEqual(rules("**CAUTION**: If the disk is full, stop the job.\n"), [])

    def test_L1_series_and_mixed_list_capitalisation(self) -> None:
        self.assert_rule("L1", "warn", "Check the logs, the disk, the queue, and the cache.\n",
                         "Check these:\n\n- the logs\n- the disk\n- the queue\n- the cache\n")
        self.assertIn(("warn", "L1"), rules("- Capital item\n- lowercase item\n"))
        self.assertEqual(rules("- Capital item\n- Other item\n"), [])

    def test_every_documented_rule_has_a_sample_here(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("Deterministic rules (errors): " + " ".join(ERRORS) + ".", src)
        self.assertIn("Heuristic rules (warnings): " + " ".join(WARNS) + ".", src)
        names = {n[5:7] for n in dir(self) if re.match(r"test_[A-Z]\d_", n)}
        self.assertEqual(names, set(ERRORS) | set(WARNS))


class Exclusions(unittest.TestCase):
    DIRTY = "don't utilize this; e.g. file_path has finished running"

    def test_excluded_regions_never_produce_findings(self) -> None:
        samples = {
            "frontmatter": "---\ntitle: " + self.DIRTY + "\n---\n\nClean prose here.\n",
            "fenced code": "Clean prose here.\n\n```\n" + self.DIRTY + "\n```\n",
            "tilde fence": "~~~\n" + self.DIRTY + "\n~~~\n",
            "inline code": "Use `" + self.DIRTY + "` here.\n",
            "indented code": "Clean prose here.\n\n    " + self.DIRTY + "\n",
            "url": "See https://example.test/" + self.DIRTY.replace(" ", "_") + " now.\n",
            "link target": "See [the page](https://example.test/x;y?e.g.=don't) now.\n",
            "table": "| a | b |\n|---|---|\n| " + self.DIRTY + " | x |\n",
            "blockquote": "> " + self.DIRTY + "\n",
            "quoted text": 'The label says "' + self.DIRTY + '" on screen.\n',
            "curly quotes": "The label says “" + self.DIRTY + "” on screen.\n",
            "heading": "## " + self.DIRTY + "\n",
            "html comment": "<!-- " + self.DIRTY + " -->\n",
        }
        for name, text in samples.items():
            with self.subTest(region=name):
                proc = lint(text)
                self.assertEqual((proc.returncode, proc.stdout), (0, ""), text)

    def test_prose_around_an_exclusion_is_still_checked(self) -> None:
        self.assertEqual(rules("```\nx\n```\n\nWe utilize it.\n"), [("error", "W4")])
        self.assertEqual(rules("We utilize `x`.\n"), [("error", "W4")])


class WordCounting(unittest.TestCase):
    def test_one_word_tokens(self) -> None:
        base = "The " + words(21) + " and"
        # 25 words: 24 plain + one more token; each of these counts as ONE word, so S1 stays quiet
        # (the bare path still gets its C1, which is about backticks, not length).
        for token in ("`a long inline code span`", "src/deep/path/file.py", "10 ms", "5 GB", "well-known-name",
                      "(a parenthetical of many many many words)", '"a quoted span of words"'):
            with self.subTest(token=token):
                self.assertNotIn(("error", "S1"), rules(base + " " + token + " end.\n"), token)
        # Two plain words in that slot make 26, which is over the limit.
        self.assertEqual(rules(base + " two words end.\n"), [("error", "S1")])

    def test_a_long_parenthetical_is_measured_on_its_own(self) -> None:
        self.assertEqual(rules("Short (" + words(26) + ") end.\n"), [("error", "S1")])
        out = lint("Short (" + words(26) + ") end.\n").stdout
        self.assertIn("inside parentheses", out)

    def test_colon_ending_a_list_intro_ends_the_sentence(self) -> None:
        self.assertEqual(rules("Do these " + words(18) + ":\n\n- one\n- two\n"), [], "20 words, the colon excluded")
        self.assertEqual(rules("Do these " + words(18) + " now:\n\n- one\n- two\n"), [("error", "S2")])

    def test_line_numbers_point_at_the_sentence_start(self) -> None:
        text = "---\nx: y\n---\n\nFirst clean line.\n\nSecond clean line.\nWe utilize it.\n"
        self.assertIn("<stdin>:7: W4:", lint(text).stdout)


class AllowList(unittest.TestCase):
    def test_terms_file_and_auto_loaded_project_list(self) -> None:
        text = "Logging is on. We utilize file_path and the Static Site Build Cache Layer.\n"
        self.assertEqual({r for _, r in rules(text)}, {"V3", "W4", "C1", "W1"})
        with tempfile.TemporaryDirectory() as tmp:
            terms = Path(tmp, "terms")
            terms.write_text("# comment\nLogging\nutilize\n\nfile_path\nStatic Site Build Cache Layer\n", encoding="utf-8")
            self.assertEqual(rules(text, "--terms", str(terms)), [])
            self.assertEqual(rules(text, cwd=tmp), [("error", "C1"), ("error", "V3"), ("error", "W4"), ("warn", "W1")])
            Path(tmp, ".magician").mkdir()
            Path(tmp, ".magician", "ste-terms").write_text("logging\nUTILIZE\n", encoding="utf-8")
            self.assertEqual(rules(text, cwd=tmp), [("error", "C1"), ("warn", "W1")], "case-insensitive, auto-loaded")
        proc = run(["--stdin", "--terms", os.path.join(tmp, "missing")], stdin=text)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot read terms file", proc.stderr)


class Cli(unittest.TestCase):
    THREE = "We utilize it; it's e.g. fine.\n"

    def test_max_caps_the_output_and_reports_the_total(self) -> None:
        proc = run(["--stdin", "--max", "2"], stdin=self.THREE)
        lines = proc.stdout.splitlines()
        self.assertEqual(len([l for l in lines if l.startswith("<stdin>:")]), 2)
        self.assertEqual(lines[-1], "... 2 more (4 findings in all)")
        default = run(["--stdin"], stdin=(self.THREE * 5)).stdout
        self.assertEqual(len([l for l in default.splitlines() if l.startswith("<stdin>:")]), 10, "default cap 10")
        self.assertIn("(20 findings in all)", default)
        self.assertEqual(run(["--stdin", "--max", "x"], stdin=self.THREE).returncode, 2)

    def test_json_shape(self) -> None:
        proc = run(["--stdin", "--json", "--max", "3"], stdin=self.THREE)
        self.assertEqual(proc.returncode, 1)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"files", "total", "shown", "errors", "warnings", "strict", "findings"})
        self.assertEqual((doc["files"], doc["total"], doc["shown"], doc["errors"], doc["warnings"], doc["strict"]),
                         (["<stdin>"], 4, 3, 4, 0, False))
        for f in doc["findings"]:
            self.assertEqual(set(f), {"path", "line", "rule", "level", "message"})
            self.assertEqual((f["path"], f["line"], f["level"]), ("<stdin>", 1, "error"))
        self.assertEqual([f["rule"] for f in doc["findings"]], ["W2", "W3", "W4"])

    def test_exit_codes_and_strict(self) -> None:
        self.assertEqual(lint("Clean prose.\n").returncode, 0)
        self.assertEqual(lint("We utilize it.\n").returncode, 1)
        warn_only = "The file is written by the job.\n"
        self.assertEqual(lint(warn_only).returncode, 0, "warnings alone exit 0")
        self.assertIn("warn V1:", lint(warn_only).stdout)
        strict = lint(warn_only, "--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("<stdin>:1: V1:", strict.stdout)
        doc = json.loads(lint(warn_only, "--strict", "--json").stdout)
        self.assertEqual((doc["errors"], doc["warnings"], doc["strict"], doc["findings"][0]["level"]),
                         (1, 0, True, "error"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run([os.path.join(tmp, "missing.md")]).returncode, 2)
            self.assertIn("cannot read", run([os.path.join(tmp, "missing.md")]).stderr)
            good = Path(tmp, "a.md")
            good.write_text("We utilize it.\n", encoding="utf-8")
            proc = run([str(good), str(good)])
            self.assertEqual(proc.returncode, 1)
            self.assertIn(str(good) + ":1: W4:", proc.stdout)
            self.assertEqual(good.read_text(encoding="utf-8"), "We utilize it.\n", "never modified")
        self.assertEqual(run([]).returncode, 2)
        self.assertEqual(run(["--bogus"]).returncode, 2)
        self.assertIn("unknown option", run(["--bogus"]).stderr)

    def test_help(self) -> None:
        for flag in ("-h", "--help"):
            proc = run([flag])
            self.assertEqual(proc.returncode, 0)
            for token in ("--max", "--json", "--terms", "--strict", "--stdin", "Exit codes", "path:line: RULE: message"):
                self.assertIn(token, proc.stdout)
        text = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("compliant", text.lower().replace("no compliance", ""), "never claims STE compliance")

    def test_tool_is_executable_stdlib_python_under_200_kib(self) -> None:
        self.assertTrue(TOOL.stat().st_mode & stat.S_IXUSR)
        self.assertTrue(os.access(TOOL, os.X_OK))
        src = TOOL.read_text(encoding="utf-8")
        self.assertTrue(src.startswith("#!/usr/bin/env python3\n"))
        self.assertLess(TOOL.stat().st_size, 200 * 1024)
        imports = set(re.findall(r"^(?:import|from) (\w+)", src, re.M))
        self.assertTrue(imports <= {"__future__", "json", "os", "re", "sys"}, imports)
        self.assertNotIn("open(", src.replace('open(p, encoding="utf-8", errors="replace")', "")
                         .replace('open(path, encoding="utf-8", errors="replace")', ""),
                         "the tool opens files for reading only")


if __name__ == "__main__":
    unittest.main()

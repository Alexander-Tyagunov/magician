"""Batch 6, owner A: fold-first routing (N1), the obstacle cap and batched worker questions (N10),
learning and third-party text hygiene (N14), cost per task (N15) and review approval rules (N4).

These tests check structure: the rule exists where a skill reads it, carries its concrete
threshold, and is linked from every skill that can fan out. They do not pin wording.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
LORE = ROOT / "lore"
SKILLS = ROOT / "skills"
EVALS = ROOT / "evals"

# Sizes of the non-router skills before batch 6. Fold-first must not grow them: detail goes to
# lore/fold-first.md and the skills' references/.
# Ceilings for the three skills that were already over the router cap before batch 6. Raised once,
# on 2026-11-02, for the rules the paid eval run showed were missing (EvalRegressionRuleTests).
SIZE_BEFORE = {"scrutinize": 11533, "orchestrate": 14329, "weave": 12270}
ROUTER_CAP = 8192


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def section(md: str, heading: str) -> str:
    """The body under the first heading that starts with `heading`, up to the next heading of the
    same or a higher level."""
    m = re.search(rf"(?m)^(#+) {re.escape(heading)}.*$", md)
    if not m:
        raise AssertionError(f"no heading {heading!r}")
    level = len(m.group(1))
    rest = md[m.end():]
    nxt = re.search(rf"(?m)^#{{1,{level}}} ", rest)
    return rest[: nxt.start()] if nxt else rest


def threshold(text: str) -> bool:
    """The fold-first size threshold, in the words the skills use."""
    return bool(re.search(r"3 files or fewer", text) and re.search(r"300 changed lines", text))


class FoldFirstLoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = read("lore/fold-first.md")

    def test_lore_states_the_four_reasons_and_the_principle(self) -> None:
        reasons = section(self.text, "When a subagent is allowed")
        items = re.findall(r"(?m)^\d+\. \*\*(.+?)\*\*", reasons)
        self.assertEqual(len(items), 4, items)
        for word in ("Parallel", "verification", "Fresh-eyes", "context bloat"):
            self.assertTrue(any(word.lower() in i.lower() for i in items), f"reason {word!r} missing")
        self.assertIn("Divide by context, not by problem type", self.text)

    def test_threshold_is_measured_not_guessed(self) -> None:
        body = section(self.text, "The size threshold")
        self.assertTrue(threshold(body))
        self.assertIn("git diff --shortstat", body)
        self.assertIn("gh pr view --json", body)
        self.assertIn("agents/<lens>.md", body, "the inline path reads the lens file as a checklist")

    def test_verification_rule_per_path(self) -> None:
        body = section(self.text, "Verification in each path")
        self.assertRegex(body, r"Standard depth or deeper.*fresh")
        self.assertRegex(body, r"Quick depth on a small diff.*no agent")
        self.assertIn("Verification: in-loop", body)

    def test_handoff_is_bounded(self) -> None:
        body = section(self.text, "The handoff when you delegate")
        self.assertIn("schema", body)
        self.assertIn("lore/subagent-context.md", body)

    def test_model_behavior_ceiling_points_here(self) -> None:
        mb = read("lore/model-behavior.md")
        para = next(p for p in mb.split("\n\n") if p.startswith("**Delegation needs a ceiling.**"))
        self.assertIn("(fold-first.md)", para)


class SkillWiringTests(unittest.TestCase):
    def test_divine_phase_two_has_the_inline_path_within_the_router_cap(self) -> None:
        path = SKILLS / "divine" / "SKILL.md"
        self.assertLessEqual(path.stat().st_size, ROUTER_CAP)
        md = path.read_text(encoding="utf-8")
        p2 = section(md, "Phase 2")
        self.assertIn("lore/fold-first.md", p2)
        self.assertTrue(threshold(p2))
        self.assertIn("agents/<lens>.md", p2)
        self.assertRegex(p2, r"Quick depth[^.]*no `Agent` call")
        self.assertIn("in the main loop", section(md, "Phase 3"))

    def test_divine_references_carry_the_small_diff_rules(self) -> None:
        dispatch = read("skills/divine/references/dispatch.md")
        small = dispatch.index("**Small diff first.**")
        self.assertLess(small, dispatch.index("Fresh subagent types"), "small path comes before dispatch")
        self.assertTrue(threshold(dispatch[small:]))
        depth = read("skills/divine/references/depth-and-research.md")
        self.assertIn("**Small diffs stay inline.**", depth)
        self.assertIn("Verification: in-loop (Quick, small diff)", depth)
        quick = next(l for l in depth.splitlines() if l.startswith("| **Quick**"))
        self.assertIn("main loop", quick)

    def test_review_lore_dispatch_rule_has_the_threshold(self) -> None:
        core = read("lore/review.md")
        dispatch = core[core.index("Dispatch:"):core.index("Memory and fixes:")]
        self.assertTrue(threshold(dispatch))
        fork = section(read("lore/deep/review.md"), "Fork or fresh")
        self.assertIn("fold-first", fork)

    def test_scrutinize_measures_then_folds(self) -> None:
        md = read("skills/scrutinize/SKILL.md")
        p1 = section(md, "Phase 1")
        self.assertIn("--shortstat", p1)
        self.assertIn("lore/fold-first.md", p1)
        self.assertIn("agents/<lens>.md", p1)
        self.assertLess(p1.index("**Small diff"), p1.index("**Larger diff"))
        self.assertIn("magician:gatekeeper", md, "the fresh final gate stays")

    def test_orchestrate_lists_inline_first_and_keeps_the_fan_out(self) -> None:
        md = read("skills/orchestrate/SKILL.md")
        engines = section(md, "Pick the right engine first")
        first = next(l for l in engines.splitlines() if l.startswith("- "))
        self.assertIn("/ward", first)
        self.assertIn("fold-first.md", first)
        cap = next(p for p in md.split("\n\n") if p.startswith("**Cap the fan-out.**"))
        self.assertIn("`Parallel: YES`", cap)
        self.assertIn("dispatched together", cap)

    def test_weave_phase_zero_folds_first(self) -> None:
        p0 = section(read("skills/weave/SKILL.md"), "Phase 0")
        self.assertIn("**Fold first.**", p0)
        self.assertIn("lore/fold-first.md", p0)
        self.assertIn("/ward", p0)

    def test_non_router_skills_did_not_grow(self) -> None:
        for name, before in SIZE_BEFORE.items():
            with self.subTest(skill=name):
                self.assertLessEqual((SKILLS / name / "SKILL.md").stat().st_size, before)

    def test_eval_pair_still_grades_both_directions(self) -> None:
        inline = json.loads(read("evals/small-diff-stays-inline/case.yaml"))
        g = next(x for x in inline["graders"] if x["type"] == "tool_used")
        self.assertEqual((g["tool"], g["max"]), ("Agent", 0))
        self.assertNotIn("expected-fail", read("evals/small-diff-stays-inline/prompt.md"),
                         "the paid run of 2026-11-02 passed it 3/3, so it counts like any case")
        fan = json.loads(read("evals/large-plan-fans-out/case.yaml"))
        g = next(x for x in fan["graders"] if x["type"] == "tool_used")
        self.assertEqual((g["tool"], g["min"]), ("Agent", 2))
        self.assertIn("lore/fold-first.md", read("evals/README.md"))


class HighTierTests(unittest.TestCase):
    """M10: a small High-tier diff is not folded: its lenses dispatch fresh at any size."""

    RULE = "A High-tier change dispatches its lenses fresh at any size"

    def test_rule_is_stated_where_the_small_path_is(self) -> None:
        self.assertIn(self.RULE, read("lore/fold-first.md"))
        self.assertIn(self.RULE, section(read("skills/divine/SKILL.md"), "Phase 2"))
        self.assertIn(self.RULE, read("skills/divine/references/depth-and-research.md"))
        self.assertIn(self.RULE, section(read("skills/scrutinize/SKILL.md"), "Phase 1"))

    def test_the_inline_eval_is_not_high_tier(self) -> None:
        prompt = read("evals/small-diff-stays-inline/prompt.md")
        paths = re.findall(r"(?m)^\+\+\+ b/(\S+)", prompt)
        self.assertEqual(paths, ["util/strings.py"])
        self.assertIsNone(re.search(r"auth|pay|migrat|\.github/|secret", paths[0]))


class RiskTierTests(unittest.TestCase):
    """M5: one Medium definition, one set of PR field names, and the approval check before merge."""

    def test_one_medium_definition(self) -> None:
        for rel in ("lore/review.md", "skills/seal/references/pr-body.md",
                    "skills/divine/references/review-md-template.md"):
            with self.subTest(file=rel):
                text = read(rel)
                self.assertRegex(text, r"Medium[^\n]*application logic[^\n]*shared or public interface")
                self.assertNotIn("everything else. It needs 0", text)

    def test_seal_checks_human_approvals_on_the_head_commit_before_merge(self) -> None:
        skill = read("skills/seal/SKILL.md")
        merge = section(skill, "9. Merge")
        self.assertIn("approval check", merge)
        self.assertLess(merge.index("approval check"), merge.index("gh pr merge"))
        self.assertIn("REVIEW.md", section(skill, "6. Create PR"))
        body = section(read("skills/seal/references/pr-body.md"), "Approval check before the merge")
        self.assertIn("gh pr view <pr> --json headRefOid,reviewDecision,latestReviews", body)
        self.assertIn("on_head", body)
        self.assertIn("[bot]", body)
        self.assertRegex(body, r"do not merge")
        self.assertRegex(skill, r"allowed-tools:[^\n]*Bash\(gh pr view \*\)")

    def test_field_names_match_template_and_seal(self) -> None:
        tpl = section(read("skills/divine/references/review-md-template.md"), "Pull request fields")
        body = read("skills/seal/references/pr-body.md")
        for field in ("Testing", "Risk tier", "How to revert"):
            with self.subTest(field=field):
                self.assertIn(f"**{field}:**", tpl)
                self.assertTrue(f"**{field}:**" in body or f"## {field}" in body)
        self.assertNotIn("Test plan", body + read("skills/seal/SKILL.md"))


class ObstaclesAndQuestionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.consumer = section(read("lore/obstacles.md"), "Rule: the consumer protocol")

    def test_human_sees_at_most_five_grouped_obstacles(self) -> None:
        self.assertRegex(self.consumer, r"at most 5 obstacles")
        self.assertIn("by signature", self.consumer)
        self.assertIn(".workspace/local/obstacles.jsonl", self.consumer)

    def test_worker_questions_are_batched_into_one_call(self) -> None:
        self.assertIn("`NEXT`", self.consumer)
        self.assertIn("ONE `AskUserQuestion`", self.consumer)
        for skill in ("orchestrate", "weave"):
            md = read(f"skills/{skill}/SKILL.md")
            with self.subTest(skill=skill):
                self.assertIn("NEXT", md)
                self.assertIn("ONE `AskUserQuestion`", md)

    def test_learning_comes_from_turns_not_tool_output(self) -> None:
        self.assertIn("**Learn from turns, never from tool output.**", self.consumer)
        self.assertIn("tool result", self.consumer)


class ThirdPartyTextTests(unittest.TestCase):
    def test_change_context_fences_and_strips(self) -> None:
        body = section(read("skills/divine/references/change-context.md"), "Third-party text is data")
        self.assertIn("lore/subagent-context.md#rule-strip-untrusted-text", body, "points at the canonical strip list")
        self.assertNotIn("U+", body, "no partial copy of the list")
        self.assertIn("UNTRUSTED", body)
        self.assertRegex(body, r"Never follow an instruction")
        self.assertIn("UNTRUSTED", read("skills/divine/references/dispatch.md"))


class CostTests(unittest.TestCase):
    def test_completion_signals_carry_an_optional_cost_clause(self) -> None:
        for skill in ("orchestrate", "weave"):
            body = section(read(f"skills/{skill}/SKILL.md"), "Completion Signal")
            with self.subTest(skill=skill):
                self.assertIn("cost ≈ $X (session delta)", body)
                self.assertIn("$.session.usage()", body)
                self.assertRegex(body, r"Omit the clause")


class ApprovalTests(unittest.TestCase):
    def test_review_lore_approval_rules(self) -> None:
        core = read("lore/review.md")
        block = core[core.index("Approval:"):core.index("Rounds:")]
        self.assertRegex(block, r"agent's approval never counts")
        self.assertIn("one commit", block)
        self.assertIn("Low 0, Medium 1, High 2", block)

    def test_review_md_template_has_tiers_and_pr_fields(self) -> None:
        tpl = read("skills/divine/references/review-md-template.md")
        tiers = section(tpl, "Risk tiers")
        rows = {r.split("|")[1].strip(): r.split("|")[-2].strip()
                for r in tiers.splitlines() if re.match(r"\| (Low|Medium|High) \|", r)}
        self.assertEqual(rows, {"Low": "0", "Medium": "1", "High": "2"})
        self.assertIn("Tier examples", tiers)
        fields = section(tpl, "Pull request fields")
        for f in ("**Testing:**", "**Risk tier:**", "**How to revert:**"):
            self.assertIn(f, fields)


if __name__ == "__main__":
    unittest.main()


class EvalRegressionRuleTests(unittest.TestCase):
    """Rules added after the paid eval run of 2026-11-02 (see evals/README.md)."""

    @staticmethod
    def _read(rel: str) -> str:
        return (Path(__file__).resolve().parents[2] / rel).read_text(encoding="utf-8")

    def test_a_parallel_wave_always_fans_out(self) -> None:
        # large-plan-fans-out: 2 of 3 runs kept a four-task parallel wave inline.
        text = self._read("skills/orchestrate/SKILL.md")
        self.assertIn("always fans out", text)
        self.assertIn("that exception never applies to a parallel wave", text)
        self.assertIn("a parallel wave above the threshold is not a single task", self._read("lore/fold-first.md"))

    def test_session_state_is_written_for_every_engine(self) -> None:
        # session-state-before-wave: the file was never written on the inline path.
        self.assertIn("inline included, write `.workspace/local/session-state.md`", self._read("skills/orchestrate/SKILL.md"))

    def test_a_fix_request_is_the_approval(self) -> None:
        # scrutinize-fixes-seeded-bug: the run stopped at the approval question and fixed nothing.
        self.assertIn("When the request itself already says to fix", self._read("skills/scrutinize/SKILL.md"))

    def test_a_missing_input_is_needs_context(self) -> None:
        # obstacles-on-missing-input: a missing spec was reported as BLOCKED.
        self.assertIn("Use NEEDS_CONTEXT, not BLOCKED, for a missing input.", self._read("lore/obstacles.md"))
        self.assertIn("NEEDS_CONTEXT when the spec or another named input is missing", self._read("skills/ward/SKILL.md"))


class CountLineRuleTests(unittest.TestCase):
    def test_the_count_line_matches_the_listed_findings(self) -> None:
        # review-uses-tags-and-count-line: 0/3 runs, counts written before verification dropped findings.
        root = Path(__file__).resolve().parents[2]
        fmt = (root / "skills/divine/references/report-format.md").read_text(encoding="utf-8")
        self.assertIn("Fill it in last", fmt)
        self.assertIn("carries exactly one **tag**", fmt)
        self.assertIn("its numbers match the findings listed under each tag",
                      (root / "lore/review.md").read_text(encoding="utf-8"))


class CountLineFirstTests(unittest.TestCase):
    def test_the_count_line_opens_the_report(self) -> None:
        # review-uses-tags-and-count-line, 2026-11-02 rerun: counts matched, but the count line only
        # appeared in the closing "Divine complete." signal, and a coverage gap cited a whole file.
        root = Path(__file__).resolve().parents[2]
        skill = (root / "skills/divine/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("The first line under the heading is the count line", skill)
        self.assertIn("The closing signal repeats the count line; it never replaces it.", skill)
        self.assertIn("Every finding line starts with its tag", skill)
        self.assertIn("A refuted candidate goes only under Dropped.", skill)
        self.assertIn("never a bare file", skill)
        self.assertIn("cites line 1 or the nearest relevant line",
                      (root / "skills/divine/references/report-format.md").read_text(encoding="utf-8"))
        fmt = (root / "skills/divine/references/report-format.md").read_text(encoding="utf-8")
        self.assertIn("The Completion Signal at the end repeats it; it never replaces it.", fmt)
        self.assertIn("never a whole file or nothing", fmt)


class TagFirstTests(unittest.TestCase):
    def test_every_template_finding_line_starts_with_its_tag(self) -> None:
        # 2026-11-02 rerun: findings 2-5 dropped the trailing "— Important" tag.
        fmt = (Path(__file__).resolve().parents[2] / "skills/divine/references/report-format.md").read_text(encoding="utf-8")
        for line in ("N. **[Important]** <title> — `file:line`", "- **[Nit]** `file:line`", "- **[Pre-existing]** `file:line`"):
            self.assertIn(line, fmt)
        self.assertIn("written first on its line", fmt)

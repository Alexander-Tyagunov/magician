"""Batch 6 (magician 5.0.0) ship-side contracts: unattended-run lore (N3), PR body risk and revert
lines plus incident-to-eval (N4), rubrics for non-code deliverables (N6), the SDLC spine (N8),
agent-scale VCS notes (N12), surface dating and the Dashboard offer (N16), and the north star and
decision records in /manifest and /conjure (N17).

These tests pin structure: files exist, rules and fields are present, and skills link the references.
Link and anchor resolution is covered by test_lore.py for every tracked Markdown file.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
LORE = ROOT / "lore"
ROUTER_CAP = 8192

TOUCHED_SKILLS = ("seal", "deploy", "manifest", "portal", "conjure", "accelerate", "blueprint", "magic", "autopsy")
RUBRIC_SKILLS = ("conjure", "blueprint", "magic", "autopsy")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def numbered_items(text: str) -> list[str]:
    return re.findall(r"(?m)^\d+\.\s+\S.*$", text)


class TestRouterSizes(unittest.TestCase):
    def test_touched_skill_routers_within_cap(self) -> None:
        for name in TOUCHED_SKILLS:
            with self.subTest(skill=name):
                size = (SKILLS / name / "SKILL.md").stat().st_size
                self.assertLessEqual(size, ROUTER_CAP, f"{name}: SKILL.md is {size} bytes")


class TestUnattendedLore(unittest.TestCase):
    """N3: six automation rules, referenced from every unattended loop."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read("lore/unattended.md")

    def test_six_numbered_rules(self) -> None:
        rules = re.findall(r"(?m)^(\d+)\.\s+\*\*", self.text)
        self.assertEqual(rules, [str(i) for i in range(1, 7)])

    def test_each_rule_has_its_concrete_anchor(self) -> None:
        for needle in (".workspace/local/", "head SHA", "could not read", "Re-check live state",
                       "after the platform confirms", ".workspace/local/prefs.md", "read-only token",
                       "--max-budget-usd", "3 to 5 times", "spend cap", "CLAUDE_CODE_REMOTE"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_core_stays_short_without_a_deep_file(self) -> None:
        self.assertLess(len(self.text.splitlines()), 60)
        self.assertFalse((LORE / "deep" / "unattended.md").exists())

    def test_referenced_from_every_loop(self) -> None:
        for rel in ("skills/divine/references/monitor-mode.md", "skills/seal/references/ci-loop.md",
                    "skills/seal/SKILL.md", "skills/deploy/SKILL.md",
                    "skills/deploy/references/control-bands.md"):
            with self.subTest(file=rel):
                self.assertIn("lore/unattended.md", read(rel))

    def test_monitor_mode_maps_the_rules(self) -> None:
        text = read("skills/divine/references/monitor-mode.md")
        for needle in ("bookmark", "could not read", "head SHA moved", "prefs.md", "spend cap"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class TestSealPrBody(unittest.TestCase):
    """N4 + N8: Risk tier, How to revert, Intent and links in the PR body."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read("skills/seal/SKILL.md")
        cls.body = read("skills/seal/references/pr-body.md")

    def test_skill_links_the_references(self) -> None:
        self.assertIn("references/pr-body.md", self.skill)
        self.assertIn("references/ci-loop.md", self.skill)

    def test_template_carries_the_lines(self) -> None:
        template = self.body.split("```bash", 1)[1].split("```", 1)[0]
        for field in ("**Intent:**", "**Links:**", "**Risk tier:**", "**How to revert:**", "## Testing"):
            with self.subTest(field=field):
                self.assertIn(field, template)

    def test_links_name_intent_spec_and_plan(self) -> None:
        for path in (".workspace/shared/intents/", ".workspace/shared/specs/", ".workspace/shared/plans/"):
            with self.subTest(path=path):
                self.assertIn(path, self.body)

    def test_risk_tiers_and_approval_counts(self) -> None:
        for tier, count in (("High", "2 human approvals"), ("Medium", "1 human approval"), ("Low", "0 human approvals")):
            with self.subTest(tier=tier):
                self.assertRegex(self.body, rf"\*\*{tier}:\*\*[^\n]*{count}")
        self.assertIn("agent's approval never counts", self.body)
        self.assertIn("binds to one commit", self.body)

    def test_gate_summary_lists_the_new_lines(self) -> None:
        self.assertRegex(self.skill, r"PR title and body\*\*:[^\n]*Risk tier[^\n]*How to revert")


class TestSealFixForward(unittest.TestCase):
    """N12: post-merge fix-forward loop and feature flags."""

    def test_skill_offers_fix_forward_after_merge(self) -> None:
        skill = read("skills/seal/SKILL.md")
        merge = skill.index("gh pr merge --squash --delete-branch\n```")
        after = skill[merge:]
        self.assertIn("Fix forward", after)
        self.assertIn("/loop", after)
        self.assertIn("feature flag", after)

    def test_ci_loop_bounds_the_fix_forward_loop(self) -> None:
        text = read("skills/seal/references/ci-loop.md")
        self.assertIn("## Post-merge fix-forward", text)
        self.assertIn("3 failed rounds", text)
        self.assertIn("never merges on its own", text)

    def test_git_lore_has_agent_scale_paragraph(self) -> None:
        text = read("lore/git.md")
        self.assertIn("Agent-scale VCS", text)
        for needle in ("small", "intent", "after the merge", "fix forward"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class TestAutopsyEval(unittest.TestCase):
    """N4: the incident becomes an eval skeleton inside the skill's write grant."""

    def test_eval_skeleton_step(self) -> None:
        text = read("skills/autopsy/SKILL.md")
        self.assertIn("Incident to eval skeleton", text)
        for needle in (".workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.eval.md",
                       "prompt.md", "case.yaml", "evals/<incident-name>/", "schema_version", "graders",
                       "expected_outcome", "allowed_tools", "TODO"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        step = text.split("Incident to eval skeleton", 1)[1].split("### Phase 6", 1)[0]
        for key in ("`setup`", "`expect`", "`must_not`"):
            self.assertNotIn(key, step, "not a key of the repo's eval schema")

    def test_skeleton_keys_are_the_eval_schema(self) -> None:
        import json
        import sys
        sys.path.insert(0, str(ROOT / "tests" / "claude"))
        from test_evals import CASE_YAML_KEYS, GRADER_ALLOWED_FIELDS, PROMPT_KEYS, REQUIRED_PROMPT_KEYS
        step = read("skills/autopsy/SKILL.md").split("Incident to eval skeleton", 1)[1].split("### Phase 6", 1)[0]
        case = json.loads(re.search(r"`(\{\"schema_version\".*?\})`", step).group(1))
        self.assertLessEqual(set(case), CASE_YAML_KEYS)
        for g in case["graders"]:
            self.assertLessEqual(set(g), GRADER_ALLOWED_FIELDS[g["type"]])
        prompt_line = next(l for l in step.splitlines() if "`prompt.md`" in l)
        named = set(re.findall(r"`([a-z_]+)`", prompt_line))
        self.assertLessEqual(named, PROMPT_KEYS)
        self.assertLessEqual(REQUIRED_PROMPT_KEYS, named | {"tags", "runs"})

    def test_skeleton_path_is_inside_the_grant(self) -> None:
        text = read("skills/autopsy/SKILL.md")
        self.assertIn("Edit(./.workspace/shared/postmortems/**)", text.split("---", 2)[1])
        self.assertIn(".eval.md", text.split("### Phase 6", 1)[1], "the commit stages the eval skeleton")


class TestRubrics(unittest.TestCase):
    """N6: 6–10 checkable claims per rubric, one SKILL.md line each, verification rows."""

    def test_each_rubric_has_six_to_ten_claims(self) -> None:
        for name in RUBRIC_SKILLS:
            with self.subTest(skill=name):
                items = numbered_items(read(f"skills/{name}/references/rubric.md"))
                self.assertGreaterEqual(len(items), 6)
                self.assertLessEqual(len(items), 10)

    def test_claims_avoid_taste_words(self) -> None:
        taste = re.compile(r"\b(clear|good|nice|elegant|well[- ]written|appropriate)\b", re.I)
        for name in RUBRIC_SKILLS:
            for item in numbered_items(read(f"skills/{name}/references/rubric.md")):
                with self.subTest(skill=name, item=item[:40]):
                    self.assertIsNone(taste.search(item), "a rubric claim must be checkable, not taste")

    def test_skill_grades_before_completion(self) -> None:
        for name in RUBRIC_SKILLS:
            with self.subTest(skill=name):
                text = read(f"skills/{name}/SKILL.md")
                self.assertRegex(text, r"grade the \w+ against \[`?references/rubric\.md`?\]\(references/rubric\.md\); list unmet items")

    def test_verification_lore_has_rubric_rows(self) -> None:
        text = read("lore/verification.md")
        for claim, name in (("Spec complete", "conjure"), ("Plan complete", "blueprint"),
                            ("Research complete", "magic"), ("Post-mortem complete", "autopsy")):
            with self.subTest(claim=claim):
                self.assertRegex(text, rf"(?m)^\| {claim} \|[^\n]*skills/{name}/references/rubric\.md")


class TestSdlcSpine(unittest.TestCase):
    """N8 + N17: intent file, north star, deploy tiers and control bands."""

    def test_manifest_writes_the_intent_and_reads_the_north_star(self) -> None:
        text = read("skills/manifest/SKILL.md")
        phase0 = text.split("### Phase 0", 1)[1].split("### Phase 1", 1)[0]
        self.assertIn(".workspace/shared/intents/<date>-<feature>.md", phase0)
        self.assertIn(".workspace/shared/north-star.md", phase0)
        self.assertIn("references/phase-notes.md", text)

    def test_manifest_grants_unchanged(self) -> None:
        front = read("skills/manifest/SKILL.md").split("---", 2)[1]
        self.assertNotIn("allowed-tools", front, "the intent write uses the normal permission prompt")

    def test_intent_format_fields(self) -> None:
        notes = read("skills/manifest/references/phase-notes.md")
        for field in ("**Intent:**", "**In scope:**", "**Out of scope:**", "**Success looks like:**", "**North star:**"):
            with self.subTest(field=field):
                self.assertIn(field, notes)

    def test_conjure_commits_intent_and_decisions_with_the_spec(self) -> None:
        text = read("skills/conjure/references/after-approval.md")
        self.assertIn(".workspace/shared/decisions/", text)
        self.assertIn(".workspace/shared/intents/", text)

    def test_conjure_reads_north_star_and_records_decisions(self) -> None:
        skill = read("skills/conjure/SKILL.md")
        gates = read("skills/conjure/references/gates.md")
        self.assertIn(".workspace/shared/north-star.md", skill)
        self.assertIn(".workspace/shared/decisions/", skill)
        for field in ("**Options:**", "**Chosen:**", "**Consequences:**", "supersedes"):
            with self.subTest(field=field):
                self.assertIn(field, gates)

    def test_deploy_tiered_autonomy(self) -> None:
        text = read("skills/deploy/SKILL.md")
        self.assertIn("### Tiered autonomy by environment", text)
        for env in ("dev", "staging", "production"):
            with self.subTest(env=env):
                self.assertRegex(text, rf"(?m)^\| {env} \|")
        self.assertIn("Prepare only", text)
        self.assertIn("Rehearse the rollback in staging", text)
        self.assertIn("references/control-bands.md", text)

    def test_control_bands(self) -> None:
        text = read("skills/deploy/references/control-bands.md")
        for band in ("1σ", "2σ", "3σ"):
            with self.subTest(band=band):
                self.assertRegex(text, rf"(?m)^\| {band} \|")
        self.assertIn("No band acts in production", text)
        self.assertIn("read-only", text)
        self.assertIn("at least 20", text)


class TestBatch6Fixes(unittest.TestCase):
    """Verifier fixes: the claude -p budget flag (H2), git add per optional file (M9), plan-mode intent
    staging (M12), the seal run-list grant (L3), and the north-star line (L7)."""

    def test_claude_p_uses_the_budget_flag(self) -> None:
        text = read("lore/unattended.md")
        self.assertIn("`--max-budget-usd <amount>` for `claude -p`", text)
        self.assertNotIn("--max-cost-usd", text, "--max-cost-usd belongs to claude plugin eval only")

    def test_each_optional_file_has_its_own_git_add(self) -> None:
        for rel in ("skills/autopsy/SKILL.md", "skills/conjure/references/after-approval.md"):
            text = read(rel)
            adds = re.findall(r"(?m)^git add (.+)$", text)
            with self.subTest(file=rel):
                self.assertGreaterEqual(len(adds), 2)
                for args in adds:
                    self.assertEqual(len(args.split()), 1, f"one path per git add: {args}")
                    self.assertNotIn("*", args, "a glob that matches nothing fails the git add")
                self.assertRegex(text, r"missing path fails")

    def test_plan_mode_intent_is_staged_by_seal(self) -> None:
        notes = read("skills/manifest/references/phase-notes.md")
        plan = notes.split("## Plan mode", 1)[1].split("\n## ", 1)[0]
        self.assertIn("/seal", plan)
        self.assertIn("git add -A", plan)
        self.assertIn("normal permission prompt", notes)
        self.assertIn(".workspace/shared/intents/", read("skills/seal/references/pr-body.md"))

    def test_seal_grants_the_run_list_it_uses(self) -> None:
        front = read("skills/seal/SKILL.md").split("---", 2)[1]
        self.assertIn("Bash(gh run list *)", front)
        self.assertIn("gh run list", read("skills/seal/references/ci-loop.md"))

    def test_north_star_line_is_one_format(self) -> None:
        line = "**North star:**"
        self.assertIn(line, read("skills/conjure/references/spec-format.md"))
        self.assertRegex(read("skills/conjure/references/gates.md"), r"North star:\*\* fits[^\n]*conflicts because")
        almanac = read("skills/almanac/references/optional-setup.md")
        self.assertRegex(almanac, r"North star:\*\* fits[^\n]*conflicts because")
        self.assertNotIn("keep each approach in line", read("skills/conjure/references/gates.md"))


class TestSurfaces(unittest.TestCase):
    """N12 portal alternatives, N16 dating and the Dashboard offer."""

    def test_portal_alternatives(self) -> None:
        text = read("skills/portal/SKILL.md")
        for needle in ("claude --worktree", "isolation: worktree", "git sparse-checkout", "sparse-checkout set --cone"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertEqual(read("skills/portal/SKILL.md").split("---", 2)[1].count("Bash("), 1,
                         "portal grants stay at the single worktree command")

    def test_design_mode_dates(self) -> None:
        text = read("skills/conjure/references/design-mode.md")
        self.assertIn("2026-09-16", text)
        self.assertIn("2026-12-14", text)

    def test_accelerate_dashboard_offer_is_conditional(self) -> None:
        text = read("skills/accelerate/SKILL.md")
        block = text.split("**Dashboard offer.**", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Artifact tool", block)
        self.assertIn("warehouse", block)
        self.assertIn("Do not build it without a yes", block)


if __name__ == "__main__":
    unittest.main()

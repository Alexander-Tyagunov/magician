"""Behavior tests for the Codex-only project-context lore router."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
# The generated package carries main's lore (cores + lore/deep/<tech>.md), exactly as installed.
PACKAGE = ROOT / "plugins" / "magician"
SECTION_REF = r"^lore/deep/[a-z0-9-]+\.md#[a-z0-9-]+$"
INJECTION_REF = "lore/deep/databases.md#parameterized-queries-and-injection"
INJECTION_ANCHOR_TAG = '<a id="parameterized-queries-and-injection"></a>'
DETECTOR = (
    ROOT
    / ".codex-plugin"
    / "skills"
    / "project-context"
    / "scripts"
    / "detect_project_context.py"
)


class ProjectContextDetectorTests(unittest.TestCase):
    def run_detector(
        self,
        project: Path,
        *topics: str,
        env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        command = [
            sys.executable,
            str(DETECTOR),
            "--root",
            str(project),
            "--plugin-root",
            str(PACKAGE),
        ]
        for topic in topics:
            command.extend(("--topic", topic))
        result = subprocess.run(
            command,
            cwd=project,
            env={**os.environ, **(env or {})},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_detects_stack_and_orders_small_lore_cores_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text(
                json.dumps(
                    {
                        "dependencies": {
                            "next": "15.0.0",
                            "pg": "8.0.0",
                            "grafana": "1.0.0",
                        },
                        "private-token": "must-not-appear",
                    }
                ),
                encoding="utf-8",
            )
            (project / "tsconfig.json").write_text("{}\n", encoding="utf-8")

            report = self.run_detector(project)

        self.assertTrue(report["enabled"])
        self.assertEqual(report["archetype"], "web")
        self.assertEqual(
            report["cores"],
            [
                "lore/javascript.md",
                "lore/typescript.md",
                "lore/databases.md",
                "lore/postgres.md",
                "lore/logging.md",
                "lore/grafana.md",
                "lore/nextjs.md",
                "lore/security.md",
            ],
        )
        self.assertNotIn("must-not-appear", json.dumps(report))

    def test_routes_only_task_matching_deep_dives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "pyproject.toml").write_text(
                "[project]\ndependencies = ['psycopg', 'fastapi']\n",
                encoding="utf-8",
            )

            report = self.run_detector(project, "investigate query performance")

        recommendations = report["recommended_deep_dives"]
        self.assertIn("lore/deep/postgres.md#performance", recommendations)
        self.assertLessEqual(len(recommendations), 8)
        for ref in recommendations:
            with self.subTest(ref=ref):
                self.assertRegex(ref, SECTION_REF)
                document, anchor = ref.split("#", 1)
                text = (PACKAGE / document).read_text(encoding="utf-8")
                self.assertIn(f'<a id="{anchor}"></a>', text)

    def test_slow_query_routing_prioritizes_performance_not_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text(
                json.dumps({"dependencies": {"pg": "8.0.0", "@prisma/client": "6.0.0"}}),
                encoding="utf-8",
            )

            report = self.run_detector(project, "investigate slow PostgreSQL queries")

        recommendations = report["recommended_deep_dives"]
        self.assertIn("lore/deep/postgres.md#performance", recommendations[:4])
        self.assertIn("lore/deep/databases.md#indexing-and-query-plans", recommendations[:4])
        self.assertIn(INJECTION_ANCHOR_TAG, (PACKAGE / "lore/deep/databases.md").read_text(encoding="utf-8"))
        self.assertNotIn(INJECTION_REF, recommendations)

    def test_injection_topic_reaches_the_injection_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "pyproject.toml").write_text(
                "[project]\ndependencies = ['psycopg', 'fastapi']\n", encoding="utf-8"
            )
            report = self.run_detector(project, "fix sql injection in search endpoint")

        self.assertIn(INJECTION_ANCHOR_TAG, (PACKAGE / "lore/deep/databases.md").read_text(encoding="utf-8"))
        self.assertIn(INJECTION_REF, report["recommended_deep_dives"])

    def test_dependency_injection_sections_stay_routable(self) -> None:
        cases = (
            ("pyproject.toml", "[project]\ndependencies = ['fastapi']\n", "make fastapi endpoints async",
             "lore/deep/fastapi.md#async-and-di"),
            ("pyproject.toml", "[project]\ndependencies = ['fastapi']\n", "async dependency",
             "lore/deep/fastapi.md#async-and-di"),
            ("package.json", json.dumps({"dependencies": {"@nestjs/core": "10.0.0"}}),
             "add a new nestjs module with providers", "lore/deep/nestjs.md#modules-and-di"),
        )
        for manifest, content, topic, expected in cases:
            with self.subTest(topic=topic):
                with tempfile.TemporaryDirectory() as directory:
                    project = Path(directory)
                    (project / manifest).write_text(content, encoding="utf-8")
                    report = self.run_detector(project, topic)
                self.assertIn(expected, report["recommended_deep_dives"])

    def test_shared_lore_path_words_do_not_match_topics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "pyproject.toml").write_text(
                "[project]\ndependencies = ['psycopg', 'fastapi']\n", encoding="utf-8"
            )
            report = self.run_detector(project, "deep dive")

        self.assertTrue(report["deep_dives"])
        self.assertEqual(report["recommended_deep_dives"], [])

    def test_honors_codex_safe_lore_disable_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            report = self.run_detector(project, env={"MAGICIAN_LORE": "off"})

        self.assertFalse(report["enabled"])
        self.assertEqual(report["disabled_by"], "MAGICIAN_LORE")
        self.assertEqual(report["cores"], [])
        self.assertEqual(report["recommended_deep_dives"], [])

    def test_project_disable_file_takes_precedence_over_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            marker = project / ".magician"
            marker.mkdir()
            (marker / "lore.off").write_text("\n", encoding="utf-8")

            report = self.run_detector(project)

        self.assertFalse(report["enabled"])
        self.assertEqual(report["disabled_by"], ".magician/lore.off")

    def test_gradle_kotlin_dsl_does_not_misclassify_java_as_kotlin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "build.gradle.kts").write_text(
                'plugins { java }\n',
                encoding="utf-8",
            )

            report = self.run_detector(project)

        self.assertIn("java", report["technologies"])
        self.assertNotIn("kotlin", report["technologies"])

    def test_gradle_kotlin_plugin_is_detected_in_groovy_dsl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "build.gradle").write_text(
                "plugins { id 'org.jetbrains.kotlin.jvm' version '2.2.0' }\n",
                encoding="utf-8",
            )

            report = self.run_detector(project)

        self.assertIn("kotlin", report["technologies"])
        self.assertNotIn("java", report["technologies"])


if __name__ == "__main__":
    unittest.main()

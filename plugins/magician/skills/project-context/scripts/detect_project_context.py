#!/usr/bin/env python3
"""Detect a project stack and route to packaged Magician lore.

This is a Codex-only, read-only companion to the Claude SessionStart detector. It intentionally
does not read or write Claude state and emits no source manifest contents.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Iterable


MAX_MARKER_BYTES = 2_000_000
DISABLED_VALUES = {"0", "off", "false", "no", "disabled"}

LANGUAGE_TIER = (
    "javascript",
    "typescript",
    "python",
    "go",
    "java",
    "rust",
    "kotlin",
    "scala",
    "swift",
    "flutter",
    "node",
    "ruby",
    "php",
    "csharp",
)
DATABASE_TIER = (
    "databases",
    "postgres",
    "mysql",
    "oracle",
    "sqlserver",
    "sqlite",
    "duckdb",
    "clickhouse",
    "snowflake",
    "bigquery",
    "redshift",
    "mongodb",
    "dynamodb",
    "cassandra",
    "couchbase",
    "firestore",
    "redis",
    "memcached",
    "pinecone",
    "weaviate",
    "qdrant",
    "milvus",
    "chroma",
    "pgvector",
    "neo4j",
    "neptune",
    "arangodb",
    "elasticsearch",
    "influxdb",
    "timescaledb",
    "prometheus",
    "logging",
    "dynatrace",
    "grafana",
    "splunk",
    "gcp-logging",
    "cloudwatch",
    "azure-monitor",
)

PACKAGE_DEPENDENCIES = {
    "next": "nextjs",
    "react": "react",
    "vue": "vue",
    "nuxt": "nuxt",
    "svelte": "svelte",
    "express": "express",
    "fastify": "fastify",
    "graphql": "graphql",
    "prisma": "prisma",
    "typeorm": "typeorm",
    "sequelize": "sequelize",
    "mongoose": "mongoose",
    "kysely": "kysely",
    "drizzle-orm": "drizzle",
    "tailwindcss": "tailwind",
    "sass": "sass",
    "node-sass": "sass",
    "less": "less",
    "bootstrap": "bootstrap",
    "antd": "antd",
    "styled-components": "styled-components",
}
PACKAGE_PREFIXES = {
    "@prisma": "prisma",
    "@angular": "angular",
    "@nestjs": "nestjs",
    "@sveltejs/kit": "sveltekit",
    "@mui": "mui",
    "@chakra-ui": "chakra",
    "@mantine": "mantine",
    "@emotion": "emotion",
    "@radix-ui": "radix",
    "@vanilla-extract": "vanilla-extract",
    "@pandacss": "vanilla-extract",
    "@stylexjs": "vanilla-extract",
}

TEXT_TECHNOLOGIES = (
    ("fastapi", r"\bfastapi\b"),
    ("django", r"\bdjango\b"),
    ("flask", r"\bflask\b"),
    ("litestar", r"\blitestar\b"),
    ("pandas", r"\bpandas\b"),
    ("numpy", r"\bnumpy\b"),
    ("polars", r"\bpolars\b"),
    ("pytorch", r"\b(?:torch|pytorch)\b"),
    ("tensorflow", r"\b(?:tensorflow|keras)\b"),
    ("sklearn", r"\b(?:scikit-learn|sklearn)\b"),
    ("jax", r"\b(?:jax|flax)\b"),
    ("transformers", r"\btransformers\b"),
    ("langchain", r"\b(?:langchain|llama[-_ ]?index)\b"),
    ("llm-sdks", r"\b(?:anthropic|openai)\b"),
    ("jupyter", r"\b(?:jupyter|notebook|ipykernel)\b"),
    ("sqlalchemy", r"\bsqlalchemy\b"),
    ("alembic", r"\balembic\b"),
    ("sqlmodel", r"\bsqlmodel\b"),
    ("tortoise", r"\btortoise\b"),
    ("peewee", r"\bpeewee\b"),
    ("gin", r"gin-gonic/gin"),
    ("echo", r"labstack/echo"),
    ("chi", r"go-chi/chi"),
    ("fiber", r"gofiber/fiber"),
    ("gorm", r"(?:gorm\.io|jinzhu/gorm)"),
    ("sqlc", r"sqlc-dev/sqlc"),
    ("sqlx", r"(?:jmoiron/sqlx|jackc/pgx)"),
    ("ent", r"entgo\.io/ent"),
    ("grpc", r"(?:google\.golang\.org/(?:grpc|protobuf)|connectrpc\.com)"),
    ("cobra", r"spf13/cobra"),
    ("viper", r"spf13/viper"),
    ("slog", r"(?:go\.uber\.org/zap|uber-go/zap|rs/zerolog)"),
    ("spring", r"\bspring"),
    ("micronaut", r"\bmicronaut\b"),
    ("quarkus", r"\bquarkus\b"),
    ("orm", r"(?:hibernate|jakarta\.persistence|javax\.persistence|data-jpa|jooq|mybatis)"),
    ("db-migrations", r"\b(?:flyway|liquibase)\b"),
    ("jdbc", r"(?:postgresql|mysql-connector|mysql:mysql|mariadb|com\.h2database|ojdbc|mssql-jdbc|starter-jdbc|hikaricp|r2dbc)"),
)

DATABASES = (
    ("postgres", r"psycopg|asyncpg|jackc/pgx|lib/pq|postgresql|postgres|[\"']pg[\"']"),
    ("mysql", r"mysql|mariadb|go-sql-driver"),
    ("sqlite", r"sqlite"),
    ("oracle", r"oracledb|cx_oracle|ojdbc|godror"),
    ("sqlserver", r"mssql|sqlserver|go-mssqldb|tedious"),
    ("duckdb", r"duckdb"),
    ("clickhouse", r"clickhouse"),
    ("snowflake", r"snowflake"),
    ("bigquery", r"bigquery"),
    ("redshift", r"redshift"),
    ("mongodb", r"mongodb|mongoose|pymongo|go\.mongodb"),
    ("dynamodb", r"dynamodb"),
    ("cassandra", r"cassandra|gocql|scylla"),
    ("couchbase", r"couchbase"),
    ("firestore", r"firestore|firebase-admin"),
    ("redis", r"redis|ioredis"),
    ("memcached", r"memcached|gomemcache"),
    ("pinecone", r"pinecone"),
    ("weaviate", r"weaviate"),
    ("qdrant", r"qdrant"),
    ("milvus", r"milvus"),
    ("chroma", r"chromadb"),
    ("pgvector", r"pgvector"),
    ("neo4j", r"neo4j|py2neo"),
    ("arangodb", r"arangodb|arangojs|python-arango"),
    ("neptune", r"amazon-neptune|neptune\.amazonaws|neptune-cluster"),
    ("elasticsearch", r"elasticsearch|opensearch|@elastic"),
    ("influxdb", r"influxdb"),
    ("timescaledb", r"timescale"),
    ("prometheus", r"prometheus"),
)
OBSERVABILITY = (
    ("dynatrace", r"dynatrace|oneagent"),
    ("grafana", r"grafana|\bloki\b|promtail|-loki"),
    ("splunk", r"splunk"),
    ("gcp-logging", r"google-cloud-logging|@google-cloud/logging|google\.cloud\.logging|stackdriver"),
    ("cloudwatch", r"cloudwatch|aws-embedded-metrics|watchtower"),
    ("azure-monitor", r"applicationinsights|azure-monitor|opencensus-ext-azure"),
)

MARKER_NAMES = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "uv.lock",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "build.sbt",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".env",
)


def read_marker(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        with path.open("rb") as stream:
            return stream.read(MAX_MARKER_BYTES).decode("utf-8", errors="ignore").lower()
    except OSError:
        return ""


def marker_text(root: Path) -> str:
    paths = [root / name for name in MARKER_NAMES]
    paths.extend(sorted(root.glob("requirements*.txt")))
    paths.extend(sorted(root.glob(".env.*")))
    paths.extend(sorted((root / "project").glob("*.sbt")))
    return "\n".join(filter(None, (read_marker(path) for path in paths)))


def add(technologies: list[str], technology: str) -> None:
    if technology not in technologies:
        technologies.append(technology)


def package_dependencies(root: Path) -> set[str]:
    try:
        data = json.loads((root / "package.json").read_text(encoding="utf-8"))
        dependencies = {
            **(data.get("dependencies") or {}),
            **(data.get("devDependencies") or {}),
        }
        return {str(name).lower() for name in dependencies}
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
        return set()


def detect(root: Path) -> tuple[str, list[str], list[str]]:
    technologies: list[str] = []
    archetype = "unknown"
    gradle_text = "\n".join(
        read_marker(root / name) for name in ("build.gradle", "build.gradle.kts")
    )
    kotlin_gradle = bool(
        re.search(r"org\.jetbrains\.kotlin|\bkotlin\s*\(", gradle_text)
    )

    if (root / "package.json").is_file():
        add(technologies, "javascript")
        archetype = "web"
    if (root / "tsconfig.json").is_file():
        add(technologies, "typescript")
    if (root / "pom.xml").is_file():
        add(technologies, "java")
        archetype = "backend"
    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        add(technologies, "kotlin" if kotlin_gradle else "java")
        archetype = "backend"
    if (root / "go.mod").is_file():
        add(technologies, "go")
        archetype = "backend"
    if (root / "Cargo.toml").is_file():
        add(technologies, "rust")
        archetype = "backend"
    if (root / "pubspec.yaml").is_file():
        add(technologies, "flutter")
        archetype = "mobile"
    if (root / "project.godot").is_file():
        add(technologies, "godot")
        archetype = "gamedev"
    if (root / "Assets").is_dir() and (root / "ProjectSettings").is_dir():
        add(technologies, "unity")
        archetype = "gamedev"
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        add(technologies, "python")
        archetype = "backend"

    dependencies = package_dependencies(root)
    for package, technology in PACKAGE_DEPENDENCIES.items():
        if package in dependencies:
            add(technologies, technology)
    for prefix, technology in PACKAGE_PREFIXES.items():
        if any(name == prefix or name.startswith(prefix + "/") for name in dependencies):
            add(technologies, technology)

    haystack = marker_text(root)
    for technology, pattern in TEXT_TECHNOLOGIES:
        if re.search(pattern, haystack):
            add(technologies, technology)

    if any(root.glob("*.tf")):
        add(technologies, "terraform")
        if archetype == "unknown":
            archetype = "devops"
    if any((root / name).is_file() for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")):
        add(technologies, "docker")
    if (root / ".github" / "workflows").is_dir():
        add(technologies, "github-actions")
    if any(root.glob("*.ipynb")):
        add(technologies, "jupyter")
        if archetype == "unknown":
            archetype = "data"
    if (root / "Package.swift").is_file():
        add(technologies, "swift")
        archetype = "mobile"
    if any(root.glob("*.kt")):
        add(technologies, "kotlin")
        if archetype == "unknown":
            archetype = "backend"
    if (root / "build.sbt").is_file() or any(root.glob("*.scala")):
        add(technologies, "scala")
        if archetype == "unknown":
            archetype = "backend"
    if (root / "components.json").is_file():
        components = read_marker(root / "components.json")
        if re.search(r"shadcn|tailwind|aliases", components):
            add(technologies, "radix")
    if (root / "package.json").is_file() and not (root / "tsconfig.json").is_file():
        package_text = read_marker(root / "package.json")
        if re.search(r"[\"'](?:main|bin)[\"']", package_text):
            add(technologies, "node")
    if any((root / name).exists() for name in ("tests", "test", "spec", "pytest.ini", "jest.config.js", "jest.config.ts", "vitest.config.ts")):
        add(technologies, "tdd")

    databases = [name for name, pattern in DATABASES if re.search(pattern, haystack)]
    if databases:
        add(technologies, "databases")
        for database in databases:
            add(technologies, database)

    observability = [name for name, pattern in OBSERVABILITY if re.search(pattern, haystack)]
    if len(observability) == 1:
        add(technologies, "logging")
        add(technologies, observability[0])
    elif archetype in {"backend", "web", "data", "mobile", "gamedev"}:
        add(technologies, "logging")

    if (root / ".git").is_dir():
        add(technologies, "git")
    add(technologies, "security")
    return archetype, technologies, observability


def ordered_technologies(technologies: Iterable[str]) -> list[str]:
    detected = list(technologies)
    ordered = [name for name in LANGUAGE_TIER if name in detected]
    ordered.extend(name for name in DATABASE_TIER if name in detected and name not in ordered)
    ordered.extend(
        name
        for name in detected
        if name not in ordered and name != "security"
    )
    if "security" in detected:
        ordered.append("security")
    return ordered


def lore_inventory(plugin_root: Path, technologies: Iterable[str]) -> tuple[list[str], dict[str, list[str]]]:
    lore_root = plugin_root / "lore"
    cores: list[str] = []
    deep_dives: dict[str, list[str]] = {}
    for technology in ordered_technologies(technologies):
        core = lore_root / f"{technology}.md"
        if core.is_file():
            cores.append(core.relative_to(plugin_root).as_posix())
        deep_root = lore_root / technology
        if deep_root.is_dir():
            paths = [
                path.relative_to(plugin_root).as_posix()
                for path in sorted(deep_root.rglob("*.md"))
                if path.is_file()
            ]
            if paths:
                deep_dives[technology] = paths
    return cores, deep_dives


def topic_tokens(topics: Iterable[str]) -> set[str]:
    stop = {
        "about", "after", "before", "build", "change", "code", "create", "debug",
        "feature", "find", "fix", "implement", "investigate", "make", "project", "review",
        "task", "test", "this", "with",
    }
    return {
        token
        for topic in topics
        for token in re.findall(r"[a-z0-9]+", topic.lower())
        if len(token) > 2 and token not in stop
    }


def recommend(deep_dives: dict[str, list[str]], topics: Iterable[str], limit: int = 8) -> list[str]:
    wanted = topic_tokens(topics)
    if not wanted:
        return []
    expanded = set(wanted)
    slow_query = bool(wanted & {"slow", "latency", "bottleneck", "performance"})
    query_work = bool(wanted & {"query", "queries", "postgres", "postgresql"})
    if slow_query:
        expanded.update({"performance", "index", "indexing", "plan", "plans", "explain"})
    if query_work:
        expanded.update({"query", "queries", "index", "indexing", "plan", "plans"})
    injection_requested = bool(wanted & {"injection", "parameterized", "security"})
    ranked: list[tuple[int, int, str]] = []
    ordinal = 0
    for paths in deep_dives.values():
        for path in paths:
            candidate = set(re.findall(r"[a-z0-9]+", path.lower()))
            if "injection" in candidate and not injection_requested:
                ordinal += 1
                continue
            score = len(expanded & candidate)
            if slow_query and "performance" in candidate:
                score += 5
            if query_work and {"indexing", "query", "plans"} <= candidate:
                score += 3
            if score:
                ranked.append((-score, ordinal, path))
            ordinal += 1
    ranked.sort()
    return [path for _score, _ordinal, path in ranked[:limit]]


def inferred_plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def disabled_by(root: Path) -> str | None:
    if os.environ.get("MAGICIAN_LORE", "").strip().lower() in DISABLED_VALUES:
        return "MAGICIAN_LORE"
    if (root / ".magician" / "lore.off").is_file():
        return ".magician/lore.off"
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root to inspect")
    parser.add_argument("--plugin-root", type=Path, help="Magician plugin root; inferred when installed")
    parser.add_argument("--topic", action="append", default=[], help="current task topic for deep-dive routing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    plugin_root = (args.plugin_root or inferred_plugin_root()).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"project root is not a directory: {root}")
    if not (plugin_root / "lore").is_dir():
        raise SystemExit(f"Magician lore directory not found under plugin root: {plugin_root}")

    control = disabled_by(root)
    if control:
        report = {
            "enabled": False,
            "disabled_by": control,
            "plugin_root": str(plugin_root),
            "archetype": "unknown",
            "technologies": [],
            "observability_candidates": [],
            "cores": [],
            "deep_dives": {},
            "recommended_deep_dives": [],
        }
    else:
        archetype, technologies, observability = detect(root)
        cores, deep_dives = lore_inventory(plugin_root, technologies)
        report = {
            "enabled": True,
            "disabled_by": None,
            "plugin_root": str(plugin_root),
            "archetype": archetype,
            "technologies": technologies,
            "observability_candidates": observability,
            "cores": cores,
            "deep_dives": deep_dives,
            "recommended_deep_dives": recommend(deep_dives, args.topic),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

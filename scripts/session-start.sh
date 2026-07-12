#!/usr/bin/env bash
# SessionStart hook — wizard cat + dynamic inspector + lore injection.

set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
mkdir -p "$PLUGIN_DATA/chronicle"

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PLUGIN_DATA/session-start-time.txt"

# SessionStart input carries a `source` (startup | resume | compact | clear). On a post-compaction /
# resume start the agent may have lost magician's conventions, so we re-surface core doctrine below.
SS_INPUT=""
[ ! -t 0 ] && SS_INPUT=$(cat 2>/dev/null || true)
# PERF: ONE python pass parses `source` + `session_id` AND computes md5(cwd) — reused below for both
# OBS_HASH and PROJECT_HASH. Collapses what were four separate python cold-starts (~26–52ms each) into one.
SS_PARSE=$(printf '%s' "${SS_INPUT:-}" | python3 -c "import json,sys,hashlib,os
try: d=json.load(sys.stdin)
except Exception: d={}
print((d.get('source') or '').strip())
print(d.get('session_id') or 'default')
print(hashlib.md5(os.getcwd().encode()).hexdigest()[:12])" 2>/dev/null || true)
SS_SOURCE=""; SS_SID="default"; CWD_HASH="default"
{ IFS= read -r SS_SOURCE || true; IFS= read -r SS_SID || true; IFS= read -r CWD_HASH || true; } <<< "$SS_PARSE"
[ -z "$SS_SID" ] && SS_SID="default"
[ -z "$CWD_HASH" ] && CWD_HASH="default"

if [ -t 2 ] || [ "${FORCE_COLOR:-}" = "1" ]; then
  BLUE='\033[0;34m'; YELLOW='\033[0;33m'; GREEN='\033[0;32m'
  PURPLE='\033[0;35m'; RED='\033[0;31m'; CYAN='\033[0;36m'
  RESET='\033[0m'
else
  BLUE=''; YELLOW=''; GREEN=''; PURPLE=''; RED=''; CYAN=''; RESET=''
fi

cat >&2 <<CAT

${BLUE}         *        ${RESET}
${BLUE}        /|\\       ${RESET}
${BLUE}       / | \\      ${RESET}
${BLUE}      /  *  \\     ${RESET}
${BLUE}    /_________\\   ${RESET}
${BLUE}   /\\${RESET}  o   o  ${BLUE}/\\${RESET}   ${CYAN}---- * . * . * .${RESET}
${BLUE}  /   ~~~~~~~   \\${RESET}   ${YELLOW}. * . * . * .${RESET}
${BLUE}  /  ( ~~~~~ )  \\${RESET}  ${GREEN}* . * . * . *${RESET}
${BLUE}  \\_____________/${RESET}
${BLUE}    |   | |   |  ${RESET}

CAT

ARCHETYPE="unknown"
TECHS=""

detect_append() {
  case ",$TECHS," in
    *",$1,"*) ;;
    *) TECHS="${TECHS:+$TECHS,}$1" ;;
  esac
}

# ── Base ecosystem detection ─────────────────────────────────────────────────
[ -f "package.json" ]      && { detect_append "javascript"; ARCHETYPE="web"; }
[ -f "tsconfig.json" ]     && detect_append "typescript"
[ -f "pom.xml" ]           && { detect_append "java";       ARCHETYPE="backend"; }
[ -f "build.gradle" ]      && { detect_append "java";       ARCHETYPE="backend"; }
[ -f "go.mod" ]            && { detect_append "go";         ARCHETYPE="backend"; }
# ── Go ecosystem: web frameworks + DB/ORM + tooling (go.mod / go.sum) ─────────
if [ -f "go.mod" ]; then
  GO_DEPS=$(cat go.mod go.sum 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
  echo "$GO_DEPS" | grep -q "gin-gonic/gin"       && detect_append "gin"
  echo "$GO_DEPS" | grep -q "labstack/echo"       && detect_append "echo"
  echo "$GO_DEPS" | grep -q "go-chi/chi"          && detect_append "chi"
  echo "$GO_DEPS" | grep -q "gofiber/fiber"       && detect_append "fiber"
  echo "$GO_DEPS" | grep -qE "gorm\.io|jinzhu/gorm" && detect_append "gorm"
  { [ -f "sqlc.yaml" ] || [ -f "sqlc.json" ] || echo "$GO_DEPS" | grep -q "sqlc-dev/sqlc"; } && detect_append "sqlc"
  echo "$GO_DEPS" | grep -qE "jmoiron/sqlx|jackc/pgx" && detect_append "sqlx"
  echo "$GO_DEPS" | grep -q "entgo\.io/ent"       && detect_append "ent"
  echo "$GO_DEPS" | grep -qE "google\.golang\.org/grpc|google\.golang\.org/protobuf|connectrpc\.com" && detect_append "grpc"
  echo "$GO_DEPS" | grep -q "spf13/cobra"         && detect_append "cobra"
  echo "$GO_DEPS" | grep -q "spf13/viper"         && detect_append "viper"
  echo "$GO_DEPS" | grep -qE "go\.uber\.org/zap|uber-go/zap|rs/zerolog" && detect_append "slog"
fi
[ -f "Cargo.toml" ]        && { detect_append "rust";       ARCHETYPE="backend"; }
[ -f "pubspec.yaml" ]      && { detect_append "flutter";    ARCHETYPE="mobile"; }
[ -f "project.godot" ]     && { detect_append "godot";      ARCHETYPE="gamedev"; }
[ -d "Assets" ] && [ -d "ProjectSettings" ] && { detect_append "unity"; ARCHETYPE="gamedev"; }

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  detect_append "python"; ARCHETYPE="backend"
fi

# ── Deep framework detection from package.json ──────────────────────────────
if [ -f "package.json" ]; then
  eval "$(python3 << 'PYEOF' 2>/dev/null || true
import json, sys
try:
    d = json.load(open('package.json'))
    deps = {**d.get('dependencies',{}), **d.get('devDependencies',{})}
    checks = [
        ('next',        'nextjs'),
        ('react',       'react'),
        ('vue',         'vue'),
        ('nuxt',        'nuxt'),
        ('svelte',      'svelte'),
        ('express',     'express'),
        ('fastify',     'fastify'),
        ('graphql',     'graphql'),
        ('prisma',      'prisma'),
        ('typeorm',     'typeorm'),
        ('sequelize',   'sequelize'),
        ('mongoose',    'mongoose'),
        ('kysely',      'kysely'),
        ('drizzle-orm', 'drizzle'),
        ('tailwindcss', 'tailwind'),
        ('sass',        'sass'),
        ('node-sass',   'sass'),
        ('less',        'less'),
        ('bootstrap',   'bootstrap'),
        ('antd',        'antd'),
        ('styled-components', 'styled-components'),
    ]
    for pkg, tech in checks:
        if pkg in deps:
            print(f'detect_append {tech}')
    # scoped-package prefixes (@scope/...)
    prefixes = [
        ('@prisma',       'prisma'),
        ('@angular',      'angular'),
        ('@nestjs',       'nestjs'),
        ('@sveltejs/kit', 'sveltekit'),
        ('@mui',          'mui'),
        ('@chakra-ui',    'chakra'),
        ('@mantine',      'mantine'),
        ('@emotion',      'emotion'),
        ('@radix-ui',     'radix'),
        ('@vanilla-extract', 'vanilla-extract'),
        ('@pandacss',     'vanilla-extract'),
        ('@stylexjs',     'vanilla-extract'),
    ]
    for prefix, tech in prefixes:
        if any(k == prefix or k.startswith(prefix) for k in deps):
            print(f'detect_append {tech}')
except: pass
PYEOF
)"
fi

# ── Deep Python framework / data / ML detection ─────────────────────────────
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "setup.cfg" ] || [ -f "Pipfile" ] || [ -f "uv.lock" ]; then
  PY_DEPS=$(cat requirements.txt requirements*.txt pyproject.toml setup.py setup.cfg Pipfile uv.lock poetry.lock 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
  # web / API
  echo "$PY_DEPS" | grep -q "fastapi"            && detect_append "fastapi"
  echo "$PY_DEPS" | grep -q "django"             && detect_append "django"
  echo "$PY_DEPS" | grep -q "flask"              && detect_append "flask"
  echo "$PY_DEPS" | grep -q "litestar"           && detect_append "litestar"
  # data
  echo "$PY_DEPS" | grep -q "pandas"             && { detect_append "pandas";  ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -q "numpy"              && { detect_append "numpy";   ARCHETYPE="${ARCHETYPE:-data}"; }
  echo "$PY_DEPS" | grep -q "polars"             && { detect_append "polars";  ARCHETYPE="data"; }
  # ML / AI
  echo "$PY_DEPS" | grep -q "torch"              && { detect_append "pytorch";      ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -qE "tensorflow|keras"  && { detect_append "tensorflow";   ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -qE "scikit-learn|sklearn" && { detect_append "sklearn";   ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -qE "jax|flax"          && { detect_append "jax";          ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -q "transformers"       && { detect_append "transformers"; ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -qE "langchain|llama-index|llama_index|llamaindex" && detect_append "langchain"
  echo "$PY_DEPS" | grep -qE "anthropic|openai"  && detect_append "llm-sdks"
  echo "$PY_DEPS" | grep -qE "jupyter|notebook|ipykernel" && { detect_append "jupyter"; ARCHETYPE="${ARCHETYPE:-data}"; }
  # ORM / DB
  echo "$PY_DEPS" | grep -q "sqlalchemy"         && detect_append "sqlalchemy"
  echo "$PY_DEPS" | grep -q "alembic"            && detect_append "alembic"
  echo "$PY_DEPS" | grep -q "sqlmodel"           && detect_append "sqlmodel"
  echo "$PY_DEPS" | grep -q "tortoise"           && detect_append "tortoise"
  echo "$PY_DEPS" | grep -q "peewee"             && detect_append "peewee"
fi

# ── Infra / DevOps detection ─────────────────────────────────────────────────
(ls *.tf 2>/dev/null | grep -q .) && { detect_append "terraform"; ARCHETYPE="${ARCHETYPE:-devops}"; }
([ -f "Dockerfile" ] || [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]) && detect_append "docker"
[ -d ".github/workflows" ] && detect_append "github-actions"
(ls *.yaml *.yml 2>/dev/null | xargs grep -l "kind: Deployment\|kind: Service" 2>/dev/null | grep -q .) && detect_append "kubernetes"

# ── Jupyter notebook detection ───────────────────────────────────────────────
(ls *.ipynb 2>/dev/null | grep -q .) && { detect_append "jupyter"; ARCHETYPE="${ARCHETYPE:-data}"; }

# ── Additional framework detection ──────────────────────────────────────────
[ -f "Package.swift" ]                           && { detect_append "swift"; ARCHETYPE="mobile"; }
# ── Kotlin / Scala language detection (JVM) ──────────────────────────────────
if [ -f "build.gradle.kts" ] || (ls *.kt 2>/dev/null | grep -q .) || { [ -f "build.gradle" ] && grep -q "kotlin" build.gradle 2>/dev/null; }; then
  detect_append "kotlin"; ARCHETYPE="${ARCHETYPE:-backend}"
fi
if [ -f "build.sbt" ] || (ls *.scala 2>/dev/null | grep -q .) || (ls project/*.sbt 2>/dev/null | grep -q .); then
  detect_append "scala"; ARCHETYPE="${ARCHETYPE:-backend}"
fi

# ── JVM ecosystem: frameworks + SHARED data layer ────────────────────────────
# Frameworks and the data layer (JDBC / ORM / migrations) are library-keyed and
# language-agnostic: the same Hibernate/Flyway/jOOQ knowledge applies whether the
# project is Java, Kotlin, Scala, or Groovy. Detect from ANY JVM build (Maven/Gradle/sbt).
if [ -f "pom.xml" ] || [ -f "build.gradle" ] || [ -f "build.gradle.kts" ] || [ -f "build.sbt" ]; then
  JVM_DEPS=$(cat pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts gradle/libs.versions.toml build.sbt project/*.sbt project/Dependencies.scala 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
  echo "$JVM_DEPS" | grep -q "spring"    && detect_append "spring"
  echo "$JVM_DEPS" | grep -q "micronaut" && detect_append "micronaut"
  echo "$JVM_DEPS" | grep -q "quarkus"   && detect_append "quarkus"
  echo "$JVM_DEPS" | grep -qE "hibernate|jakarta\.persistence|javax\.persistence|data-jpa|jooq|mybatis" && detect_append "orm"
  echo "$JVM_DEPS" | grep -qE "flyway|liquibase" && detect_append "db-migrations"
  echo "$JVM_DEPS" | grep -qE "postgresql|mysql-connector|mysql:mysql|mariadb|com\.h2database|ojdbc|mssql-jdbc|starter-jdbc|hikaricp|r2dbc" && detect_append "jdbc"
fi
[ -d ".git" ]                                    && detect_append "git"
# shadcn/ui: copy-in components (not an npm dep) — detected by its components.json marker
[ -f "components.json" ] && grep -qi "shadcn\|tailwind\|aliases" components.json 2>/dev/null && detect_append "radix"
# node: already detected as javascript; inject node lore for server-side Node projects
[ -f "package.json" ] && [ ! -f "tsconfig.json" ] && grep -qiE '"main"|"bin"' package.json 2>/dev/null && detect_append "node"

([ -d "tests" ] || [ -d "test" ] || [ -d "spec" ] || [ -f "jest.config.js" ] || [ -f "jest.config.ts" ] || [ -f "pytest.ini" ] || [ -f "vitest.config.ts" ]) && detect_append "tdd"

# ── Database ENGINE detection (cross-ecosystem) ───────────────────────────────
# Keyed on the engine actually in use — drivers/clients in ANY manifest, docker-compose
# service images, or connection URIs — independent of language and ORM. When any engine is
# found, the shared `databases` foundation is injected FIRST (universal DB discipline), then
# the specific engine cores. Each engine's deep-dive tree (incl. performance.md) stays on-demand.
DB_HAY=$(cat package.json requirements.txt requirements*.txt pyproject.toml Pipfile uv.lock poetry.lock setup.py setup.cfg go.mod go.sum pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts gradle/libs.versions.toml build.sbt .env .env.* docker-compose.yml docker-compose.yaml compose.yml compose.yaml 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
if [ -n "$DB_HAY" ]; then
  DBS=""
  db_detect() { if echo "$DB_HAY" | grep -qE "$2"; then DBS="${DBS:+$DBS }$1"; fi; }
  # relational / OLTP
  db_detect postgres      'psycopg|asyncpg|jackc/pgx|lib/pq|postgresql|postgres|"pg"'
  db_detect mysql         'mysql|mariadb|go-sql-driver'
  db_detect sqlite        'sqlite'
  db_detect oracle        'oracledb|cx_oracle|ojdbc|godror'
  db_detect sqlserver     'mssql|sqlserver|go-mssqldb|tedious'
  # analytics / OLAP
  db_detect duckdb        'duckdb'
  db_detect clickhouse    'clickhouse'
  db_detect snowflake     'snowflake'
  db_detect bigquery      'bigquery'
  db_detect redshift      'redshift'
  # document / nosql / kv / wide-column
  db_detect mongodb       'mongodb|mongoose|pymongo|go\.mongodb'
  db_detect dynamodb      'dynamodb'
  db_detect cassandra     'cassandra|gocql|scylla'
  db_detect couchbase     'couchbase'
  db_detect firestore     'firestore|firebase-admin'
  db_detect redis         'redis|ioredis'
  db_detect memcached     'memcached|gomemcache'
  # vector
  db_detect pinecone      'pinecone'
  db_detect weaviate      'weaviate'
  db_detect qdrant        'qdrant'
  db_detect milvus        'milvus'
  db_detect chroma        'chromadb'
  db_detect pgvector      'pgvector'
  # graph
  db_detect neo4j         'neo4j|py2neo'
  db_detect arangodb      'arangodb|arangojs|python-arango'
  db_detect neptune       'amazon-neptune|neptune\.amazonaws|neptune-cluster'
  # search / time-series
  db_detect elasticsearch 'elasticsearch|opensearch|@elastic'
  db_detect influxdb      'influxdb'
  db_detect timescaledb   'timescale'
  db_detect prometheus    'prometheus'
  if [ -n "$DBS" ]; then
    detect_append "databases"                       # foundation first (universal discipline)
    for d in $DBS; do detect_append "$d"; done      # then the specific engine cores
  fi
fi

# ── Observability / log-platform detection + per-project memory ───────────────
# Logging is decided WHEN app code is written: know where the app is deployed (which log platform) so
# logs are shaped for it and queries are proposed in its language. Precedence: a recorded per-project
# choice > exactly one detected SDK > unknown (the agent asks + records — see the Observability note).
OBS_HASH="$CWD_HASH"   # PERF: reuse the md5(cwd) computed in the single stdin parse above
OBS_FILE="$PLUGIN_DATA/projects/$OBS_HASH/observability.json"
OBS_PLATFORM=""; OBS_SRC=""
if [ -f "$OBS_FILE" ]; then
  OBS_PLATFORM=$(python3 -c "import json;print((json.load(open('$OBS_FILE')).get('platform') or '').strip())" 2>/dev/null || echo "")
  [ -n "$OBS_PLATFORM" ] && OBS_SRC="recorded"
fi
if [ -z "$OBS_PLATFORM" ]; then
  OBS_HAY=$(cat package.json requirements.txt requirements*.txt pyproject.toml Pipfile go.mod go.sum pom.xml build.gradle build.gradle.kts build.sbt .env docker-compose.yml docker-compose.yaml compose.yml compose.yaml 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)
  OBS_MATCHES=""
  obs_try() { if echo "$OBS_HAY" | grep -qE "$2"; then OBS_MATCHES="${OBS_MATCHES:+$OBS_MATCHES }$1"; fi; }
  obs_try dynatrace     'dynatrace|oneagent'
  obs_try grafana       'grafana|\bloki\b|promtail|-loki'
  obs_try splunk        'splunk'
  obs_try gcp-logging   'google-cloud-logging|@google-cloud/logging|google\.cloud\.logging|stackdriver'
  obs_try cloudwatch    'cloudwatch|aws-embedded-metrics|watchtower'
  obs_try azure-monitor 'applicationinsights|azure-monitor|opencensus-ext-azure'
  OBS_N=$(printf '%s' "$OBS_MATCHES" | wc -w | tr -d ' ')
  [ "$OBS_N" = 1 ] && { OBS_PLATFORM="$OBS_MATCHES"; OBS_SRC="detected"; }   # exactly one → confident
fi
case "$ARCHETYPE" in backend|web|data|mobile|gamedev) OBS_APP=1 ;; *) OBS_APP=0 ;; esac
if [ -n "$OBS_PLATFORM" ]; then
  detect_append "logging"; detect_append "$OBS_PLATFORM"
elif [ "$OBS_APP" = 1 ]; then
  detect_append "logging"
fi

detect_append "security"

# ── Lore loader ──────────────────────────────────────────────────────────────
LORE_TEXT=""
LORE_CHARS=0
# Always-injected budget (chars). Raised from 3000 → 6000 → 8000 as the lore corpus grew (language +
# database + observability layers) so a realistic stack co-injects its primary language + the shared
# `databases` foundation + the primary engine + logging without starving the DB/observability tier
# (~2k tokens, once per session at SessionStart; ZERO per-turn — deep-dive trees stay on-demand).
MAX_LORE=8000
LORE_INJECTED=""

# ── Lore enable/disable flag (default ENABLED) ───────────────────────────────
# Bundled lore is a baseline BELOW the repo's own rules; a user can turn it off when it conflicts with
# local/project knowledge or gives wrong judgment. Resolution (first match wins): env MAGICIAN_LORE=
# 0/off/false → per-project `.magician/lore.off` → global cli-ui.json "lore":"disabled" → default ENABLED.
# When disabled, NO lore is injected (the rest of the SessionStart context is unaffected).
LORE_ENABLED=1
case "$(printf '%s' "${MAGICIAN_LORE:-}" | tr '[:upper:]' '[:lower:]')" in
  0|off|false|no|disabled) LORE_ENABLED=0 ;;
esac
[ -f ".magician/lore.off" ] && LORE_ENABLED=0
LORE_UICFG="${MAGICIAN_HOME:-$HOME/.claude/magician}/cli-ui.json"
if [ "$LORE_ENABLED" = 1 ] && [ -f "$LORE_UICFG" ] && grep -q '"lore"[[:space:]]*:[[:space:]]*"disabled"' "$LORE_UICFG" 2>/dev/null; then
  LORE_ENABLED=0
fi

# Injection priority: primary LANGUAGE first, then the DATABASE layer (foundation + engines) so DB
# guidance is never starved by secondary framework lore, then everything else, then security last.
# Only reorders when a DB is present; non-DB projects inject in their natural order.
LANG_TIER="javascript typescript python go java rust kotlin scala swift flutter node ruby php csharp"
DB_TIER="databases postgres mysql oracle sqlserver sqlite duckdb clickhouse snowflake bigquery redshift mongodb dynamodb cassandra couchbase firestore redis memcached pinecone weaviate qdrant milvus chroma pgvector neo4j neptune arangodb elasticsearch influxdb timescaledb prometheus logging dynatrace grafana splunk gcp-logging cloudwatch azure-monitor"
ORDERED=""
for t in $LANG_TIER; do case ",$TECHS," in *",$t,"*) ORDERED="$ORDERED $t" ;; esac; done
for t in $DB_TIER;   do case ",$TECHS," in *",$t,"*) ORDERED="$ORDERED $t" ;; esac; done
for t in $(echo "$TECHS" | tr ',' ' '); do
  case " $LANG_TIER $DB_TIER security " in *" $t "*) ;; *) ORDERED="$ORDERED $t" ;; esac
done
case ",$TECHS," in *",security,"*) ORDERED="$ORDERED security" ;; esac

if [ "$LORE_ENABLED" = 1 ]; then
  # Reserve the always-on `security` core FIRST (small + universal) so it is never starved by the budget.
  SEC_FILE="$PLUGIN_ROOT/lore/security.md"
  if [ -f "$SEC_FILE" ]; then
    SEC_FRAG=$(cat "$SEC_FILE")
    LORE_TEXT="[security] ${SEC_FRAG}

"
    LORE_CHARS=$(( ${#SEC_FRAG} + 12 ))
    LORE_INJECTED="security"
  fi
  for TECH in $ORDERED; do
    [ "$TECH" = "security" ] && continue     # reserved above — never budget-gated
    LORE_FILE="$PLUGIN_ROOT/lore/${TECH}.md"
    [ -f "$LORE_FILE" ] || continue
    FRAGMENT=$(cat "$LORE_FILE")
    FL=${#FRAGMENT}
    if [ $((LORE_CHARS + FL)) -le $MAX_LORE ]; then
      LORE_TEXT="${LORE_TEXT}[${TECH}] ${FRAGMENT}

"
      LORE_CHARS=$((LORE_CHARS + FL + ${#TECH} + 4))
      LORE_INJECTED="${LORE_INJECTED:+$LORE_INJECTED }$TECH"
    fi
  done
fi

# ── Lore status marker (for the CLI UI 'lore' status-bar chip) ────────────────
MAG_STATUS="${MAGICIAN_HOME:-$HOME/.claude/magician}/status"
mkdir -p "$MAG_STATUS" 2>/dev/null || true
SID_SAFE=$(printf '%s' "${SS_SID:-default}" | tr '/' '_' | cut -c1-64)
LORE_MARKER="$MAG_STATUS/${SID_SAFE}.lore.json"   # PERF: written together with the final JSON (one spawn)

# ── LORE_NOTE ────────────────────────────────────────────────────────────────
if [ -n "$TECHS" ]; then
  LORE_NOTE="Stack: ${TECHS}. Archetype: ${ARCHETYPE}."
  if [ "$LORE_ENABLED" != 1 ]; then
    LORE_NOTE="${LORE_NOTE} (Magician lore is disabled — relying only on your project/local knowledge; re-enable with \`magician-ui lore on\`.)"
  elif [ -n "$LORE_TEXT" ]; then
    LORE_NOTE="${LORE_NOTE} Lore: ${LORE_TEXT}"
  fi
else
  LORE_NOTE="No stack markers found. Run /almanac to initialize workspace."
fi

# ── Chronicle injection ──────────────────────────────────────────────────────
CHRONICLE_NOTE=""
LATEST=$(ls -t "$PLUGIN_DATA/chronicle/"*.json 2>/dev/null | head -1 || true)
if [ -n "$LATEST" ]; then
  SUMMARY=$(python3 -c "
import json
try:
    d = json.load(open('$LATEST'))
    print(d.get('summary', ''))
except: pass
" 2>/dev/null || true)
  [ -n "$SUMMARY" ] && CHRONICLE_NOTE=" Last session: $SUMMARY"
fi

# ── Global references injection (cross-session memory) ────────────────────────
REFERENCES_NOTE=""
REF_FILE="$PLUGIN_DATA/references.md"
if [ -f "$REF_FILE" ]; then
  REF_BODY=$(head -c 2000 "$REF_FILE" 2>/dev/null || true)
  [ -n "$REF_BODY" ] && REFERENCES_NOTE=" Remembered references — a passive, user-curated index. Consult ONLY when directly relevant to the current task; do NOT resurface unrelated past items or treat them as active goals:
${REF_BODY}"
fi
REMEMBER_HINT=" If the user mentions a repository, project, or idea worth keeping for future sessions, offer to remember it — saved to the global reference store via /chronicle, only with their confirmation."

# ── Observability note — platform-aware logging behavior (only when relevant) ─────────────────
OBS_NOTE=""
if [ -n "${OBS_PLATFORM:-}" ]; then
  OBS_NOTE=" Observability: this project's logs go to ${OBS_PLATFORM} (${OBS_SRC}). When writing code, emit structured, level×environment-appropriate logs at the meaningful execution points (request entry/exit + outcome, external calls, state changes, errors with context) so flows are captured for aggregation and error search — shaped for ${OBS_PLATFORM} (lore/logging.md). When locating logs/errors, propose EXACT ${OBS_PLATFORM} queries — read lore/${OBS_PLATFORM}.md for its query language first. If the user says the log platform changed, update ${OBS_FILE}."
elif [ "${OBS_APP:-0}" = 1 ]; then
  OBS_NOTE=" Observability: no log platform recorded for this project. When you're about to write logging code, or the user asks about finding logs/errors, use AskUserQuestion to ask (1) where the app is deployed / which log tool they use — Dynatrace · Grafana(Loki) · Splunk · GCP Cloud Logging · CloudWatch · Azure Monitor · other — and (2) the environment→log-level policy; then record it as JSON at ${OBS_FILE} (e.g. {\"platform\":\"dynatrace\",\"envs\":[\"dev\",\"prod\"],\"note\":\"...\"}) so future sessions don't re-ask. Follow lore/logging.md meanwhile. Don't re-ask once recorded; update the file if the user says the system changed."
fi

# ── Workspace strategy check ─────────────────────────────────────────────────
STRATEGY_NOTE=""
STRATEGY_FILE="$PLUGIN_DATA/workspace-strategy.json"
if [ -f ".gitignore" ] && [ -f "$STRATEGY_FILE" ]; then
  CURRENT_IGNORED=$(grep -c "\.workspace" .gitignore 2>/dev/null || echo "0")
  STORED=$(python3 -c "
import json
try:
    d = json.load(open('$STRATEGY_FILE'))
    print(d.get('ignored', 'unknown'))
except: print('unknown')
" 2>/dev/null)
  if [ "$CURRENT_IGNORED" = "0" ] && [ "$STORED" = "true" ]; then
    STRATEGY_NOTE=" NOTE: .workspace/ is no longer gitignored — confirm shared mode with user."
  elif [ "$CURRENT_IGNORED" != "0" ] && [ "$STORED" = "false" ]; then
    STRATEGY_NOTE=" NOTE: .workspace/ is now gitignored — confirm private mode with user."
  fi
fi

# ── First-run detection ──────────────────────────────────────────────────────
FIRST_RUN_NOTE=""
PROJECT_HASH="$CWD_HASH"   # PERF: reuse the md5(cwd) computed in the single stdin parse above
INIT_MARKER="$PLUGIN_DATA/projects/$PROJECT_HASH/initialized"

if [ ! -f "$INIT_MARKER" ]; then
  mkdir -p "$(dirname "$INIT_MARKER")"
  FIRST_RUN_NOTE=" MAGICIAN FIRST RUN FOR THIS PROJECT: Before doing any other work, use AskUserQuestion to ask: (1) Are there any files, directories, or patterns in this project that I should NEVER read or write? Examples: proprietary algorithms, vendor directories, generated artifacts, confidential configs. If yes, write them as deny rules in settings.json under permissions.deny using glob patterns like \"Read(**/vendor/**)\" or \"Write(**/proprietary/**)\". (2) Should the workspace be shared with your team via git, or kept private to this machine? After collecting answers, create the file $INIT_MARKER to mark this project as initialized."
fi

CAT_ART=$'         *        \n        /|\\\n       / | \\\n      /  *  \\\n    /_________\\   \n   /\\  o   o  /\\   ---- * . * . * .\n  /   ~~~~~~~   \\   . * . * . * .\n  /  ( ~~~~~ )  \\  * . * . * . *\n  \\_____________/\n    |   | |   |  '

# ── Knowledge-graph suggestion (throttled, opt-out-aware, never auto-builds) ──
KG_NOTE=$(python3 - "$PLUGIN_DATA" <<'PYEOF' 2>/dev/null || true
import os, sys, json, hashlib, subprocess, time
plugin_data = sys.argv[1]
mag_home = os.environ.get("MAGICIAN_HOME") or os.path.join(os.path.expanduser("~"), ".claude", "magician")
try:
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, timeout=5).stdout.strip()
except Exception:
    root = ""
if not root:
    sys.exit(0)                                   # not a git repo → no nudge
root = os.path.realpath(root)
h = hashlib.sha256(root.encode()).hexdigest()[:12]   # must match `kg`'s repohash
if os.path.exists(os.path.join(mag_home, "knowledge-graph", "repos", h, "meta.json")):
    print("This repo has a knowledge-graph index — for code lookups prefer `kg query \"<terms>\"` / "
          "`kg blast <file>` / `kg neighbors <symbol>` over grep (exact file:line, far fewer tokens, "
          "shared across agents); run `kg refresh` if results look stale.")
    sys.exit(0)                                   # already indexed → reinforce using it
try:
    if json.load(open(os.path.join(plugin_data, "integration-prefs.json"))).get("knowledge-graph") == "disabled":
        sys.exit(0)                               # opted out
except Exception:
    pass
marker = os.path.join(plugin_data, "kg-suggest", h)
try:
    if time.time() - os.path.getmtime(marker) < 7 * 86400:
        sys.exit(0)                               # nudged within 7 days
except Exception:
    pass
try:
    n = len(subprocess.run(["git", "-C", root, "ls-files"],
                           capture_output=True, text=True, timeout=15).stdout.splitlines())
except Exception:
    n = 0
if n < 150:
    sys.exit(0)                                   # too small to bother
os.makedirs(os.path.dirname(marker), exist_ok=True)
open(marker, "w").write(str(time.time()))
print(f"No knowledge-graph index for this repo ({n} files). If this session will do "
      f"search-heavy work, building one with /magician:knowledge-graph (kg init) makes "
      f"retrieval cheaper and faster — offer it once, and respect a no.")
PYEOF
)

# ── Resume capsule (re-inject after a prior compaction, on --resume/--continue) ──
RESUME_NOTE=""
# PERF: only spawn the (python) ctx CLI when there's actually a capsule to restore. `ctx resume
# --on-start` no-ops without capsule.md (and self-checks freshness+cwd), so this gate is behavior-identical
# while saving a ~116ms cold start on every normal start. Path matches ctx's proj_dir (md5(cwd)[:12]).
if [ -f "$PLUGIN_DATA/projects/$CWD_HASH/capsule.md" ]; then
  CAPSULE=$("$PLUGIN_ROOT/bin/ctx" resume --on-start 2>/dev/null || true)
  [ -n "$CAPSULE" ] && RESUME_NOTE=" RESUME-AFTER-COMPACTION — restore your bearings from this capsule, then continue (read the referenced paths instead of re-exploring):
${CAPSULE}"
fi

# ── Project memory (recent learnings for THIS project, distinct from global refs) ──
LEARN_NOTE=""
# PERF: only spawn ctx when a learnings store exists for this project (else `learn --list` returns
# nothing anyway) — saves a ~83ms cold start on every start without one. Path matches ctx's proj_dir.
if [ -f "$PLUGIN_DATA/projects/$CWD_HASH/learnings.jsonl" ]; then
  LEARNINGS=$("$PLUGIN_ROOT/bin/ctx" learn --list --n 3 2>/dev/null || true)
  [ -n "$LEARNINGS" ] && LEARN_NOTE=" PROJECT MEMORY — recent learnings for this project (consult only when relevant):
${LEARNINGS}"
fi

# ── Magician CLI UI (status line): OPT-OUT auto-enable on install/upgrade. PERF: a cheap
#    bash fast-path so we only spawn the (python) reconcile when there's real work — first run,
#    version upgrade, or a missing renderer. In the steady state (already enabled, current
#    version, renderer present) we do NOTHING here, keeping session startup fast. ──
MAG_HOME="${MAGICIAN_HOME:-$HOME/.claude/magician}"
UI_CFG="$MAG_HOME/cli-ui.json"
PLUGIN_VER="$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$PLUGIN_ROOT/.claude-plugin/plugin.json" 2>/dev/null | head -1 | sed -E 's/.*"([^"]*)"$/\1/')"
UI_NOTE=""
if grep -q '"state"[[:space:]]*:[[:space:]]*"disabled"' "$UI_CFG" 2>/dev/null; then
  # CLI UI is off, but still roll out the read-only allow-list on install/upgrade (unless the user
  # turned THAT off too). reconcile applies the allow-list, then returns without touching the bar.
  if ! grep -q '"allow"[[:space:]]*:[[:space:]]*"off"' "$UI_CFG" 2>/dev/null \
     && ! { [ -n "$PLUGIN_VER" ] && grep -q "\"allowVersion\"[[:space:]]*:[[:space:]]*\"${PLUGIN_VER}\"" "$UI_CFG" 2>/dev/null; }; then
    ALLOW_NOTE=$("$PLUGIN_ROOT/bin/magician-ui" reconcile 2>/dev/null || true)
    [ -n "$ALLOW_NOTE" ] && printf '%s\n' "$ALLOW_NOTE" >&2
  fi
elif grep -q '"state"[[:space:]]*:[[:space:]]*"enabled"' "$UI_CFG" 2>/dev/null \
     && [ -n "$PLUGIN_VER" ] && grep -q "\"version\"[[:space:]]*:[[:space:]]*\"${PLUGIN_VER}\"" "$UI_CFG" 2>/dev/null \
     && [ -f "$MAG_HOME/statusline.py" ]; then
  :   # already enabled, current version, renderer present → skip the reconcile spawn (fast path)
else
  UI_NOTE=$("$PLUGIN_ROOT/bin/magician-ui" reconcile 2>/dev/null || true)   # first run / upgrade / repair
fi
if [ -n "$UI_NOTE" ]; then
  printf '%b\n' "${PURPLE}✦ Magician CLI UI enabled${RESET} — a live status bar (context %, rot warning, token-flow sparkline, active skill). Configure with ${GREEN}/statusline${RESET} (or ${GREEN}magician-ui set context,rot${RESET}); turn it off with ${GREEN}magician-ui disable${RESET}." >&2
fi

# Post-compaction / resume: re-anchor on magician conventions the compaction may have dropped.
DOCTRINE_NOTE=""
case "$SS_SOURCE" in
  compact|resume)
    DOCTRINE_NOTE="

[MAGICIAN — post-${SS_SOURCE} re-anchor] Context was just ${SS_SOURCE}d; re-load magician's working conventions before continuing: (1) if the status bar shows Auto, reads/searches/tests proceed without asking — do NOT slip back into per-tool permission requests; gate only on writes/commits/push/PR/deploys. (2) Ground via the knowledge graph (kg query/blast/neighbors) before broad greps or whole-file reads. (3) Jira/Confluence go through the bundled MCP-free jira/confluence CLIs, never an ambient MCP. (4) Approve the plan once, then execute autonomously (lore/autonomy.md). (5) No 'done/fixed/passing' claim without fresh verification evidence (lore/verification.md)."
    ;;
esac

CONTEXT="[MAGICIAN SESSION] At the very start of your first response, greet the user by printing this block inside a code fence verbatim, then proceed to help them:
${CAT_ART}
✦ magician${TECHS:+ · ${TECHS}}${ARCHETYPE:+ · ${ARCHETYPE}}

${LORE_NOTE}${CHRONICLE_NOTE}${RESUME_NOTE}${REFERENCES_NOTE}${LEARN_NOTE}${STRATEGY_NOTE}${FIRST_RUN_NOTE}${KG_NOTE:+ ${KG_NOTE}}${OBS_NOTE}${UI_NOTE:+ ${UI_NOTE}}${REMEMBER_HINT}${DOCTRINE_NOTE}"
python3 - "$CONTEXT" "$LORE_MARKER" "$LORE_ENABLED" "$LORE_INJECTED" <<'PYEOF'
import json, sys, time
ctx, marker, enabled, injected = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:                                           # write the lore status marker (for the CLI UI chip)
    cores = (injected or "").split()
    json.dump({"enabled": enabled == "1", "count": len(cores), "cores": cores, "ts": time.time()},
              open(marker, "w"))
except Exception:
    pass
print(json.dumps({"additionalContext": ctx}))  # the SessionStart additionalContext (unchanged)
PYEOF

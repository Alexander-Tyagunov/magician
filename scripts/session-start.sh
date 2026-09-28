#!/usr/bin/env bash
# SessionStart hook: stack detection, bundled lore and per-project notes, emitted as the documented
# SessionStart JSON (hookSpecificOutput.additionalContext, plus a user-only systemMessage when there
# is a notice). Plain bash 3.2 + standard utilities: no interpreters, no eval/source, and no other
# plugin file is run. It writes only under the plugin data dir (and the status-bar markers when the
# user enabled the status line); it never writes Claude Code settings or the session env file.
# No `set -e`/`-u` (an unset variable must not kill the hook) and no pipefail (`grep -q` closing a
# pipe early must not turn a match into a miss). Always exits 0.
export LC_ALL=C

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
MAG_HOME="${MAGICIAN_HOME:-$HOME/.claude/magician}"
UI_CFG="$MAG_HOME/cli-ui.json"
BUDGET=9500   # additionalContext cap (Claude Code truncates past 10,000 characters)

# ---------- helpers ----------
_json_field() {  # $1=single-line JSON  $2=key  -> raw (still-escaped) string value
  local re="\"$2\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  if [[ $1 =~ $re ]]; then printf '%s' "${BASH_REMATCH[1]}"; fi
}
_json_unescape() {  # protect \\ first, then \" \/ and whitespace escapes (\uXXXX stays literal)
  local s=$1 bs=$'\001'
  s=${s//\\\\/$bs}; s=${s//\\\"/\"}; s=${s//\\\//\/}; s=${s//\\n/ }; s=${s//\\r/ }; s=${s//\\t/ }
  s=${s//$bs/\\}
  printf '%s' "$s"
}
_json_str() {  # escape for a JSON string body; other control bytes are dropped
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\t'/\\t}; s=${s//$'\r'/\\r}; s=${s//$'\n'/\\n}
  printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037'
}
_md5_12() {  # same project hash as the ctx CLI: md5 of the physical cwd, first 12 hex
  if command -v md5sum >/dev/null 2>&1; then md5sum | cut -c1-12
  elif command -v md5 >/dev/null 2>&1; then md5 -q | cut -c1-12
  elif [ -x /sbin/md5 ]; then /sbin/md5 -q | cut -c1-12   # macOS, /sbin not on PATH
  else openssl md5 -r 2>/dev/null | cut -c1-12; fi
}
_sha256_12() {  # same repo hash as the kg CLI: sha256 of the resolved git toplevel, first 12 hex
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | cut -c1-12
  else openssl dgst -sha256 -r 2>/dev/null | cut -c1-12; fi
}
_cap() {  # $1=max bytes; stdin -> stdout, cut at a line boundary when over
  local max=$1 buf; buf=$(cat)
  if [ ${#buf} -le "$max" ]; then printf '%s' "$buf"; else printf '%s' "$buf" | head -c"$max" | sed '$d'; fi
}
_trunc() {  # $1=max bytes  $2=text -> cut to $1 bytes without ending inside a UTF-8 sequence
  local s=$2
  [ ${#s} -le "$1" ] && { printf '%s' "$s"; return; }
  s=${s:0:$1}
  case $s in   # drop a trailing sequence only when it is incomplete (a whole character stays)
    *[$'\xc0'-$'\xff']) s=${s%?} ;;
    *[$'\xe0'-$'\xff'][$'\x80'-$'\xbf']) s=${s%??} ;;
    *[$'\xf0'-$'\xff'][$'\x80'-$'\xbf'][$'\x80'-$'\xbf']) s=${s%???} ;;
  esac
  printf '%s' "$s"
}

# ---------- input ----------
SS_INPUT=""; [ ! -t 0 ] && SS_INPUT=$(head -c65536 | tr -d '\n\r')
SS_SOURCE=$(_json_field "$SS_INPUT" source)
case "$SS_SOURCE" in startup|resume|clear|compact|fork) ;; *) SS_SOURCE="" ;; esac
SS_SID=$(_json_field "$SS_INPUT" session_id)
SID_SAFE=$(printf '%s' "${SS_SID:-default}" | tr '/' '_' | cut -c1-64)   # same rule as the status-line renderer
PWD_P=$(pwd -P 2>/dev/null)
CWD_HASH=""; [ -n "$PWD_P" ] && CWD_HASH=$(printf '%s' "$PWD_P" | _md5_12)
re_hash='^[0-9a-f]{12}$'
[[ $CWD_HASH =~ $re_hash ]] || CWD_HASH=""
# Without a project hash every project-scoped feature is skipped (never a shared fallback folder).
PROJ_DIR=""; [ -n "$CWD_HASH" ] && PROJ_DIR="$PLUGIN_DATA/projects/$CWD_HASH"
mkdir -p "$PLUGIN_DATA" 2>/dev/null

# ---------- per-session start stamp (read by chronicle-stop.sh and compact-context.sh) ----------
re_sid='^[A-Za-z0-9_-]+$'
if [[ $SS_SID =~ $re_sid ]]; then
  case "$SS_SOURCE" in startup|clear|fork)
    if [ ! -e "$PLUGIN_DATA/sessions/$SS_SID.start" ] && mkdir -p "$PLUGIN_DATA/sessions" 2>/dev/null; then
      date -u +%Y-%m-%dT%H:%M:%SZ > "$PLUGIN_DATA/sessions/$SS_SID.start" 2>/dev/null
    fi ;;
  esac
fi
find "$PLUGIN_DATA/sessions" -maxdepth 1 -type f -name '*.start' -mtime +30 -exec rm -f {} + 2>/dev/null

ARCHETYPE="unknown"
TECHS=""

detect_append() {
  case ",$TECHS," in
    *",$1,"*) ;;
    *) TECHS="${TECHS:+$TECHS,}$1" ;;
  esac
}
# ERE match against $HAY (the lowercased manifest text of the current block): no grep fork per check.
_in() { [[ $HAY =~ $1 ]]; }
_arch() { [ "$ARCHETYPE" = unknown ] && ARCHETYPE=$1; }   # archetype only when nothing set one yet
_any() { compgen -G "$1" >/dev/null; }                     # glob has at least one match (builtin)

# ── Base ecosystem detection ─────────────────────────────────────────────────
[ -f "package.json" ]      && { detect_append "javascript"; ARCHETYPE="web"; }
[ -f "tsconfig.json" ]     && detect_append "typescript"
[ -f "pom.xml" ]           && { detect_append "java";       ARCHETYPE="backend"; }
[ -f "build.gradle" ]      && { detect_append "java";       ARCHETYPE="backend"; }
[ -f "go.mod" ]            && { detect_append "go";         ARCHETYPE="backend"; }
# ── Go ecosystem: web frameworks + DB/ORM + tooling (go.mod / go.sum) ─────────
if [ -f "go.mod" ]; then
  HAY=$(cat go.mod go.sum 2>/dev/null | tr '[:upper:]' '[:lower:]')
  _in "gin-gonic/gin"       && detect_append "gin"
  _in "labstack/echo"       && detect_append "echo"
  _in "go-chi/chi"          && detect_append "chi"
  _in "gofiber/fiber"       && detect_append "fiber"
  _in "gorm\.io|jinzhu/gorm" && detect_append "gorm"
  { [ -f "sqlc.yaml" ] || [ -f "sqlc.json" ] || _in "sqlc-dev/sqlc"; } && detect_append "sqlc"
  _in "jmoiron/sqlx|jackc/pgx" && detect_append "sqlx"
  _in "entgo\.io/ent"       && detect_append "ent"
  _in "google\.golang\.org/grpc|google\.golang\.org/protobuf|connectrpc\.com" && detect_append "grpc"
  _in "spf13/cobra"         && detect_append "cobra"
  _in "spf13/viper"         && detect_append "viper"
  _in "go\.uber\.org/zap|uber-go/zap|rs/zerolog" && detect_append "slog"
fi
[ -f "Cargo.toml" ]        && { detect_append "rust";       ARCHETYPE="backend"; }
[ -f "pubspec.yaml" ]      && { detect_append "flutter";    ARCHETYPE="mobile"; }
[ -f "project.godot" ]     && { detect_append "godot";      ARCHETYPE="gamedev"; }
[ -d "Assets" ] && [ -d "ProjectSettings" ] && { detect_append "unity"; ARCHETYPE="gamedev"; }

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  detect_append "python"; ARCHETYPE="backend"
fi

# ── Deep framework detection from package.json (dependencies + devDependencies keys) ──
# Dependency objects never nest, so `\{[^}]*\}` captures each one whole.
if [ -f "package.json" ]; then
  PJ_DEPS=$(head -c1048576 package.json | tr -d '\n\r' \
    | grep -oE '"(dependencies|devDependencies)"[[:space:]]*:[[:space:]]*\{[^}]*\}' \
    | grep -oE '"[^"]+"[[:space:]]*:' | sed -E 's/^"([^"]+)".*/\1/' \
    | grep -vxE 'dependencies|devDependencies')
  _pj=$'\n'"$PJ_DEPS"$'\n'   # one dependency name per line; matched with case, not a grep per name
  _has_dep()    { case "$_pj" in *$'\n'"$1"$'\n'*) return 0 ;; esac; return 1; }
  _has_prefix() { case "$_pj" in *$'\n'"$1"*) return 0 ;; esac; return 1; }
  for _p in next:nextjs react:react vue:vue nuxt:nuxt svelte:svelte express:express fastify:fastify \
            graphql:graphql prisma:prisma typeorm:typeorm sequelize:sequelize mongoose:mongoose \
            kysely:kysely drizzle-orm:drizzle tailwindcss:tailwind sass:sass node-sass:sass less:less \
            bootstrap:bootstrap antd:antd styled-components:styled-components; do
    _has_dep "${_p%%:*}" && detect_append "${_p#*:}"
  done
  # scoped-package prefixes (@scope/...)
  for _p in @prisma:prisma @angular:angular @nestjs:nestjs @sveltejs/kit:sveltekit @mui:mui \
            @chakra-ui:chakra @mantine:mantine @emotion:emotion @radix-ui:radix \
            @vanilla-extract:vanilla-extract @pandacss:vanilla-extract @stylexjs:vanilla-extract; do
    _has_prefix "${_p%%:*}" && detect_append "${_p#*:}"
  done
fi

# ── Deep Python framework / data / ML detection ─────────────────────────────
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "setup.cfg" ] || [ -f "Pipfile" ] || [ -f "uv.lock" ]; then
  HAY=$(cat requirements.txt requirements*.txt pyproject.toml setup.py setup.cfg Pipfile uv.lock poetry.lock 2>/dev/null | tr '[:upper:]' '[:lower:]')
  # web / API
  _in "fastapi"            && detect_append "fastapi"
  _in "django"             && detect_append "django"
  _in "flask"              && detect_append "flask"
  _in "litestar"           && detect_append "litestar"
  # data
  _in "pandas"             && { detect_append "pandas";  ARCHETYPE="data"; }
  _in "numpy"              && { detect_append "numpy";   _arch data; }
  _in "polars"             && { detect_append "polars";  ARCHETYPE="data"; }
  # ML / AI
  _in "torch"              && { detect_append "pytorch";      ARCHETYPE="data"; }
  _in "tensorflow|keras"   && { detect_append "tensorflow";   ARCHETYPE="data"; }
  _in "scikit-learn|sklearn" && { detect_append "sklearn";    ARCHETYPE="data"; }
  _in "jax|flax"           && { detect_append "jax";          ARCHETYPE="data"; }
  _in "transformers"       && { detect_append "transformers"; ARCHETYPE="data"; }
  _in "langchain|llama-index|llama_index|llamaindex" && detect_append "langchain"
  _in "anthropic|openai"   && detect_append "llm-sdks"
  _in "jupyter|notebook|ipykernel" && { detect_append "jupyter"; _arch data; }
  # ORM / DB
  _in "sqlalchemy"         && detect_append "sqlalchemy"
  _in "alembic"            && detect_append "alembic"
  _in "sqlmodel"           && detect_append "sqlmodel"
  _in "tortoise"           && detect_append "tortoise"
  _in "peewee"             && detect_append "peewee"
fi

# ── Infra / DevOps detection ─────────────────────────────────────────────────
_any '*.tf' && { detect_append "terraform"; _arch devops; }
([ -f "Dockerfile" ] || [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]) && detect_append "docker"
[ -d ".github/workflows" ] && detect_append "github-actions"
{ _any '*.yaml' || _any '*.yml'; } && grep -qs -e 'kind: Deployment' -e 'kind: Service' -- *.yaml *.yml 2>/dev/null && detect_append "kubernetes"

# ── Jupyter notebook detection ───────────────────────────────────────────────
_any '*.ipynb' && { detect_append "jupyter"; _arch data; }

# ── Additional framework detection ──────────────────────────────────────────
[ -f "Package.swift" ]                           && { detect_append "swift"; ARCHETYPE="mobile"; }
# ── Kotlin / Scala language detection (JVM) ──────────────────────────────────
if [ -f "build.gradle.kts" ] || _any '*.kt' || { [ -f "build.gradle" ] && grep -q "kotlin" build.gradle 2>/dev/null; }; then
  detect_append "kotlin"; _arch backend
fi
if [ -f "build.sbt" ] || _any '*.scala' || _any 'project/*.sbt'; then
  detect_append "scala"; _arch backend
fi

# ── JVM ecosystem: frameworks + SHARED data layer ────────────────────────────
# Frameworks and the data layer (JDBC / ORM / migrations) are library-keyed and
# language-agnostic: the same Hibernate/Flyway/jOOQ knowledge applies whether the
# project is Java, Kotlin, Scala, or Groovy. Detect from ANY JVM build (Maven/Gradle/sbt).
if [ -f "pom.xml" ] || [ -f "build.gradle" ] || [ -f "build.gradle.kts" ] || [ -f "build.sbt" ]; then
  HAY=$(cat pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts gradle/libs.versions.toml build.sbt project/*.sbt project/Dependencies.scala 2>/dev/null | tr '[:upper:]' '[:lower:]')
  _in "spring"    && detect_append "spring"
  _in "micronaut" && detect_append "micronaut"
  _in "quarkus"   && detect_append "quarkus"
  _in "hibernate|jakarta\.persistence|javax\.persistence|data-jpa|jooq|mybatis" && detect_append "orm"
  _in "flyway|liquibase" && detect_append "db-migrations"
  _in "postgresql|mysql-connector|mysql:mysql|mariadb|com\.h2database|ojdbc|mssql-jdbc|starter-jdbc|hikaricp|r2dbc" && detect_append "jdbc"
fi
[ -e ".git" ]                                    && detect_append "git"   # a file in linked worktrees
# shadcn/ui: copy-in components (not an npm dep) — detected by its components.json marker
[ -f "components.json" ] && grep -qi "shadcn\|tailwind\|aliases" components.json 2>/dev/null && detect_append "radix"
# node: already detected as javascript; inject node lore for server-side Node projects
[ -f "package.json" ] && [ ! -f "tsconfig.json" ] && grep -qiE '"main"|"bin"' package.json 2>/dev/null && detect_append "node"

([ -d "tests" ] || [ -d "test" ] || [ -d "spec" ] || [ -f "jest.config.js" ] || [ -f "jest.config.ts" ] || [ -f "pytest.ini" ] || [ -f "vitest.config.ts" ]) && detect_append "tdd"

# ── Database ENGINE detection (cross-ecosystem) ───────────────────────────────
# Keyed on the engine actually in use — drivers/clients in ANY manifest or docker-compose
# service images — independent of language and ORM. Dotenv files are never read. When any engine is
# found, the shared `databases` foundation is listed before the specific engine cores (when the lore
# budget is short, the lore loader keeps the engine cores first). Each engine's deep-dive file (lore/deep/<engine>.md, incl. its #performance section) stays on-demand.
DB_HAY=$(cat package.json requirements.txt requirements*.txt pyproject.toml Pipfile uv.lock poetry.lock setup.py setup.cfg go.mod go.sum pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts gradle/libs.versions.toml build.sbt docker-compose.yml docker-compose.yaml compose.yml compose.yaml 2>/dev/null | tr '[:upper:]' '[:lower:]')
if [ -n "$DB_HAY" ]; then
  DBS=""
  db_detect() { if [[ $DB_HAY =~ $2 ]]; then DBS="${DBS:+$DBS }$1"; fi; }
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
STACK_TECHS="$TECHS"   # what the directory's own markers revealed (before logging/security are added)

# ── Observability / log-platform detection + per-project record ───────────────
# Precedence: a recorded per-project choice (only a known platform name is accepted) > exactly one
# detected SDK > unknown. The record is written by the user or by Claude at the user's request.
KNOWN_OBS=" dynatrace grafana splunk gcp-logging cloudwatch azure-monitor "
OBS_FILE=""; [ -n "$PROJ_DIR" ] && OBS_FILE="$PROJ_DIR/observability.json"
OBS_PLATFORM=""; OBS_SRC=""
if [ -n "$OBS_FILE" ] && [ -f "$OBS_FILE" ]; then
  _op=$(_json_field "$(head -c8192 "$OBS_FILE" 2>/dev/null | tr -d '\n\r')" platform | tr '[:upper:]' '[:lower:]')
  case "$KNOWN_OBS" in *" $_op "*) [ -n "$_op" ] && { OBS_PLATFORM="$_op"; OBS_SRC="recorded"; } ;; esac
fi
if [ -z "$OBS_PLATFORM" ]; then
  OBS_HAY=$(cat package.json requirements.txt requirements*.txt pyproject.toml Pipfile go.mod go.sum pom.xml build.gradle build.gradle.kts build.sbt docker-compose.yml docker-compose.yaml compose.yml compose.yaml 2>/dev/null | tr '[:upper:]' '[:lower:]')
  OBS_MATCHES=""
  obs_try() { if [[ $OBS_HAY =~ $2 ]]; then OBS_MATCHES="${OBS_MATCHES:+$OBS_MATCHES }$1"; fi; }
  obs_try dynatrace     'dynatrace|oneagent'
  obs_try grafana       'grafana|(^|[^a-z0-9_])loki([^a-z0-9_]|$)|promtail|-loki'   # loki as a whole word
  obs_try splunk        'splunk'
  obs_try gcp-logging   'google-cloud-logging|@google-cloud/logging|google\.cloud\.logging|stackdriver'
  obs_try cloudwatch    'cloudwatch|aws-embedded-metrics|watchtower'
  obs_try azure-monitor 'applicationinsights|azure-monitor|opencensus-ext-azure'
  case "$OBS_MATCHES" in ""|*" "*) ;; *) OBS_PLATFORM="$OBS_MATCHES"; OBS_SRC="detected" ;; esac   # exactly one → confident
fi
case "$ARCHETYPE" in backend|web|data|mobile|gamedev) OBS_APP=1 ;; *) OBS_APP=0 ;; esac
if [ -n "$OBS_PLATFORM" ]; then
  detect_append "logging"; detect_append "$OBS_PLATFORM"
elif [ "$OBS_APP" = 1 ]; then
  detect_append "logging"
fi

detect_append "security"

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
if [ "$LORE_ENABLED" = 1 ] && [ -f "$UI_CFG" ] && grep -q '"lore"[[:space:]]*:[[:space:]]*"disabled"' "$UI_CFG" 2>/dev/null; then
  LORE_ENABLED=0
fi

# ── Voice — output-brevity level (default scribe) ─────────────────────────────
# Fewer OUTPUT tokens = lower cost (output costs several× input) with NO quality loss: the
# injected style cuts filler (preambles, recaps, restating the request) but keeps ALL
# substance and code/commands/errors verbatim — it never compresses prose into fragments/jargon.
# Levels least→most wordy: warrior (minimal) · scribe (default, leaner) · bard (native, no inject).
# Resolution (first match wins): env MAGICIAN_VOICE → per-project .magician/voice → cli-ui.json → scribe.
VOICE_LEVEL="scribe"
_vc=""
case "$(printf '%s' "${MAGICIAN_VOICE:-}" | tr '[:upper:]' '[:lower:]')" in
  warrior|scribe|bard) _vc="$(printf '%s' "$MAGICIAN_VOICE" | tr '[:upper:]' '[:lower:]')" ;;
esac
if [ -z "$_vc" ] && [ -f ".magician/voice" ]; then
  _pv="$(head -c64 .magician/voice 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  case "$_pv" in warrior|scribe|bard) _vc="$_pv" ;; esac
fi
if [ -z "$_vc" ] && [ -f "$UI_CFG" ]; then   # portable extract (grep -oE works on BSD + GNU)
  _cv="$(grep -oE '"voice"[[:space:]]*:[[:space:]]*"(warrior|scribe|bard)"' "$UI_CFG" 2>/dev/null | grep -oE 'warrior|scribe|bard' | head -1)"
  case "$_cv" in warrior|scribe|bard) _vc="$_cv" ;; esac
fi
[ -n "$_vc" ] && VOICE_LEVEL="$_vc"

VOICE_CORE="Output style selected in magician (voice: ${VOICE_LEVEL}): lean responses without lost substance, since output tokens cost several times more than input. Every claim, step and caveat stays; code, commands, paths, identifiers, numbers and error text stay verbatim. Length comes out of filler (preambles like 'Let me…', postambles, restating the request, recaps of finished work) and the outcome comes first, in full readable sentences without fragments, arrow-chains, abbreviations or invented jargon. Code, tests, diffs and the work itself are unaffected."
case "$VOICE_LEVEL" in
  warrior) VOICE_NOTE="

${VOICE_CORE} Warrior level (minimal): the shortest response that is fully correct and complete, without optional commentary, unrequested examples or closing summaries, in tight prose or short bullets; when the answer is a single fact or action, the response is just that." ;;
  scribe)  VOICE_NOTE="

${VOICE_CORE} Scribe level (default): necessary explanation and structure stay, trimmed to what changes the reader's next action." ;;
  *)       VOICE_NOTE="" ;;   # bard → native verbosity, nothing injected
esac

# ── Previous session in THIS directory (chronicle; off when session_history=false) ──
# Only records whose working_dir equals the physical cwd count; the current session's own record is skipped.
CHRONICLE_NOTE=""
case "$(printf '%s' "${CLAUDE_PLUGIN_OPTION_SESSION_HISTORY:-true}" | tr '[:upper:]' '[:lower:]')" in
  false|0|no|off) ;;
  *)
    if [ -n "$PWD_P" ] && [ -d "$PLUGIN_DATA/chronicle" ]; then
      while IFS= read -r _f; do
        case "$_f" in *.json) ;; *) continue ;; esac
        if [ -n "$SS_SID" ]; then case "$_f" in *"-$SS_SID.json") continue ;; esac; fi
        _c=$(head -c8192 "$PLUGIN_DATA/chronicle/$_f" 2>/dev/null | tr -d '\n\r')
        [ "$(_json_unescape "$(_json_field "$_c" working_dir)")" = "$PWD_P" ] || continue
        _s=$(_trunc 300 "$(_json_unescape "$(_json_field "$_c" summary)")")
        [ -n "$_s" ] && CHRONICLE_NOTE="
Previous magician session in this directory: ${_s}"
        break
      done < <(ls -t "$PLUGIN_DATA/chronicle" 2>/dev/null | head -30)
    fi ;;
esac

# ── Project learnings (last 3, recorded with the ctx CLI) ──
LEARN_NOTE=""
if [ -n "$PROJ_DIR" ] && [ -f "$PROJ_DIR/learnings.jsonl" ]; then
  _L=""
  while IFS= read -r _line; do
    _fct=$(_json_field "$_line" fact)
    [ -n "$_fct" ] && _L="${_L}
- $(_trunc 240 "$(_json_unescape "$_fct")")"
  done < <(grep -v '^[[:space:]]*$' "$PROJ_DIR/learnings.jsonl" 2>/dev/null | tail -n 3)
  [ -n "$_L" ] && LEARN_NOTE="
Recent project learnings recorded by magician:${_L}"
fi

# ── User-curated references (global, saved with /chronicle) ──
REFERENCES_NOTE=""
if [ -f "$PLUGIN_DATA/references.md" ]; then
  _r=$(head -c8192 "$PLUGIN_DATA/references.md" 2>/dev/null | _cap 2000)
  [ -n "$_r" ] && REFERENCES_NOTE="
User-curated references saved with /chronicle (relevant only when the current task mentions them):
${_r}"
fi
REMEMBER_HINT="
/chronicle can save a repository, project or idea to the user's reference store for later sessions."

# ── Knowledge-graph status (7-day throttle, opt-out aware, never builds) ──
KG_NOTE=""
_top=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$_top" ]; then
  _root=$(cd "$_top" 2>/dev/null && pwd -P)
  _h=$(printf '%s' "$_root" | _sha256_12)
  if [ -z "$_h" ]; then
    :
  elif [ -f "$MAG_HOME/knowledge-graph/repos/$_h/meta.json" ]; then
    KG_NOTE="
This repository has a magician knowledge-graph index: \`kg query \"<terms>\"\`, \`kg blast <file>\` and \`kg neighbors <symbol>\` return file:line results; \`kg refresh\` updates it."
  elif ! grep -qE '"knowledge-graph"[[:space:]]*:[[:space:]]*"disabled"' "$PLUGIN_DATA/integration-prefs.json" 2>/dev/null; then
    _m="$PLUGIN_DATA/kg-suggest/$_h"
    if [ -z "$(find "$_m" -mtime -7 2>/dev/null)" ]; then
      _n=$(cd "$_root" 2>/dev/null && git ls-files 2>/dev/null | wc -l | tr -d ' ')
      if [ "${_n:-0}" -ge 150 ]; then
        mkdir -p "$PLUGIN_DATA/kg-suggest" 2>/dev/null && date +%s > "$_m" 2>/dev/null
        KG_NOTE="
This repository ($_n tracked files) has no magician knowledge-graph index; /magician:knowledge-graph can build one if the user wants cheaper code search."
      fi
    fi
  fi
fi

# ── Observability note (passive; platform-aware logging lives in lore/logging.md) ──
OBS_NOTE=""
if [ -n "$OBS_PLATFORM" ]; then
  OBS_NOTE="
Log platform for this project: ${OBS_PLATFORM} (${OBS_SRC}); its query syntax is in lore/${OBS_PLATFORM}.md and logging conventions are in lore/logging.md.${OBS_FILE:+ Record: ${OBS_FILE}.}"
elif [ "$OBS_APP" = 1 ] && [ -n "$OBS_FILE" ]; then
  OBS_NOTE="
No log platform is recorded for this project. Later sessions read a JSON record at ${OBS_FILE} ({\"platform\":\"<name>\",\"envs\":[…],\"note\":\"…\"}; known platforms: dynatrace, grafana, splunk, gcp-logging, cloudwatch, azure-monitor); logging conventions are in lore/logging.md."
fi

# ── Post-compaction / resume: conventions the compaction may have dropped ──
DOCTRINE_NOTE=""
case "$SS_SOURCE" in compact|resume)
  DOCTRINE_NOTE="
Magician conventions, re-stated after ${SS_SOURCE}: completion claims rest on fresh verification evidence (lore/verification.md); work follows an approve-the-plan-then-execute flow (lore/autonomy.md)." ;;
esac

# ── User-only notices (systemMessage; never part of Claude's context) ──
SYS_MSG=""
# First session in a project directory: a single optional pointer, shown once per project.
if [ -n "$PROJ_DIR" ] && [ -n "$STACK_TECHS" ] && [ ! -e "$PROJ_DIR/initialized" ]; then
  if mkdir -p "$PROJ_DIR" 2>/dev/null && : > "$PROJ_DIR/initialized" 2>/dev/null; then
    SYS_MSG="Magician: run /almanac to set up this project (optional)."
  fi
fi
# Upgrade from <=4.14: permission entries written by earlier versions stay until the user removes them.
# Shown at most once a week while cli-ui.json still records them.
if grep -qE '"(allow|automode)"[[:space:]]*:[[:space:]]*"on"' "$UI_CFG" 2>/dev/null; then
  _mig="$PLUGIN_DATA/migration-4.15-notice"
  if [ -z "$(find "$_mig" -mtime -7 2>/dev/null)" ] && : > "$_mig" 2>/dev/null; then
    SYS_MSG="${SYS_MSG:+$SYS_MSG
}magician 4.15 no longer manages Claude Code permissions. An earlier version recorded adding allow rules or defaultMode=auto to ~/.claude/settings.json; run magician-ui cleanup to remove the entries it recorded adding."
  fi
fi

# ── Lore loader (runs last so its budget is whatever the other notes leave) ──
# Always-injected cap in bytes (LC_ALL=C). Raised 3000 → 6000 → 8000 → 8100 as the lore corpus grew
# (language, database and observability layers; +100 in v4.15.0 for the `lore/deep/<t>.md#{…}` pointers).
# It is clamped to the room the other notes leave under BUDGET. That room is usually smaller, so cores
# are tried in the selection order below; about 2k tokens once per session. Deep-dive files
# stay on-demand. The plugin root is written once, in HEAD; every lore path after it is relative to it.
MAX_LORE=8100
HEAD="magician session context (plugin root: ${PLUGIN_ROOT})."
if [ -n "$STACK_TECHS" ]; then
  STACK_NOTE="Detected stack: ${STACK_TECHS}. Archetype: ${ARCHETYPE}."
else
  STACK_NOTE="No stack markers were found in this directory."
fi
LORE_HDR=" Magician lore (baseline guidance; this repository's own conventions take precedence):
"
DEEP_TEXT="
Deep-dive files: lore/deep/<stack>.md under the plugin root, one '## ' section per anchor id a core lists; Grep '^## ' gives line numbers for a Read with offset/limit."
TAIL="${CHRONICLE_NOTE}${LEARN_NOTE}${KG_NOTE}${OBS_NOTE}${DOCTRINE_NOTE}${REFERENCES_NOTE}${REMEMBER_HINT}${VOICE_NOTE}"
_fixed=$(( ${#HEAD} + 1 + ${#STACK_NOTE} + ${#LORE_HDR} + ${#DEEP_TEXT} + ${#TAIL} ))   # cores add their exact cost below
if [ "$_fixed" -gt "$BUDGET" ] && [ -n "$REFERENCES_NOTE" ]; then   # references are the first note to go
  _fixed=$(( _fixed - ${#REFERENCES_NOTE} )); REFERENCES_NOTE=""
  TAIL="${CHRONICLE_NOTE}${LEARN_NOTE}${KG_NOTE}${OBS_NOTE}${DOCTRINE_NOTE}${REMEMBER_HINT}${VOICE_NOTE}"
fi
_room=$(( BUDGET - _fixed ))
[ "$_room" -lt "$MAX_LORE" ] && MAX_LORE=$_room

# Output order: security, the languages, the database layer (foundation, engines, logging), then the rest.
LANG_TIER="javascript typescript python go java rust kotlin scala swift flutter node ruby php csharp"
DB_TIER="databases postgres mysql oracle sqlserver sqlite duckdb clickhouse snowflake bigquery redshift mongodb dynamodb cassandra couchbase firestore redis memcached pinecone weaviate qdrant milvus chroma pgvector neo4j neptune arangodb elasticsearch influxdb timescaledb prometheus logging dynatrace grafana splunk gcp-logging cloudwatch azure-monitor"
ORDERED="security"
for t in $LANG_TIER; do case ",$TECHS," in *",$t,"*) ORDERED="$ORDERED $t" ;; esac; done
for t in $DB_TIER;   do case ",$TECHS," in *",$t,"*) ORDERED="$ORDERED $t" ;; esac; done
for t in ${TECHS//,/ }; do
  case " $LANG_TIER $DB_TIER security " in *" $t "*) ;; *) ORDERED="$ORDERED $t" ;; esac
done

# Selection order, for when not every core fits: most specific first. security (small, universal), the
# languages, the project's frameworks, its database engines and log platform, then the generic databases
# and logging cores, other libraries, and last javascript when typescript is present, node and the small
# tooling cores, in that order. A core that doesn't fit is skipped and the next one is tried, so a smaller
# lower-ranked core can still take room a larger higher-ranked one couldn't use.
FRAMEWORK_TIER="nextjs nuxt sveltekit angular nestjs react vue svelte express fastify django fastapi flask litestar spring micronaut quarkus gin echo chi fiber godot unity pandas polars pytorch tensorflow jax"
_late="node tdd git docker github-actions"
case ",$TECHS," in *",typescript,"*) _late="javascript $_late" ;; esac
RANKED=""
_rank() {  # $1=techs held back for a later call, then candidates in rank order; appends detected ones
  local hold=" $1 " t; shift
  for t in "$@"; do
    case " $RANKED $hold " in *" $t "*) continue ;; esac
    case ",$TECHS," in *",$t,"*) RANKED="$RANKED $t" ;; esac
  done
}
_rank "databases logging $_late" security $LANG_TIER $FRAMEWORK_TIER $DB_TIER
_rank "$_late" databases logging ${TECHS//,/ }
_rank "" $_late ${TECHS//,/ }

LORE_TEXT=""
LORE_CHARS=0
LORE_INJECTED=""
if [ "$LORE_ENABLED" = 1 ]; then
  _keep=" "
  for TECH in $RANKED; do
    LORE_FILE="${PLUGIN_ROOT}/lore/${TECH}.md"   # exact name from the fixed detection list
    [ -f "$LORE_FILE" ] || continue
    FRAGMENT=$(<"$LORE_FILE")
    _cost=$(( ${#TECH} + ${#FRAGMENT} + 5 ))     # "[tech] " + core + blank line
    if [ $((LORE_CHARS + _cost)) -le "$MAX_LORE" ]; then
      LORE_CHARS=$((LORE_CHARS + _cost)); _keep="$_keep$TECH "
    fi
  done
  for TECH in $ORDERED; do
    case "$_keep" in *" $TECH "*) ;; *) continue ;; esac
    LORE_FILE="${PLUGIN_ROOT}/lore/${TECH}.md"
    LORE_TEXT="${LORE_TEXT}[${TECH}] $(<"$LORE_FILE")

"
    LORE_INJECTED="${LORE_INJECTED:+$LORE_INJECTED }$TECH"
  done
fi
LORE_TEXT=${LORE_TEXT%$'\n\n'}

DEEP_HINT=""
for TECH in $LORE_INJECTED; do
  if [ -f "${PLUGIN_ROOT}/lore/deep/${TECH}.md" ]; then DEEP_HINT="$DEEP_TEXT"; break; fi
done

LORE_NOTE="$STACK_NOTE"
if [ "$LORE_ENABLED" != 1 ]; then
  LORE_NOTE="${LORE_NOTE} Magician lore is disabled for this session (\`magician-ui lore on\` re-enables it)."
elif [ -n "$LORE_TEXT" ]; then
  LORE_NOTE="${LORE_NOTE}${LORE_HDR}${LORE_TEXT}${DEEP_HINT}"
fi

# ── Status-bar markers (only when the user enabled the status line) ──
if grep -qE '"state"[[:space:]]*:[[:space:]]*"enabled"' "$UI_CFG" 2>/dev/null; then
  _st="$MAG_HOME/status"
  if mkdir -p "$_st" 2>/dev/null; then
    _cores=""; for _c in $LORE_INJECTED; do _cores="${_cores:+$_cores, }\"$_c\""; done
    _cnt=$(printf '%s' "$LORE_INJECTED" | wc -w | tr -d ' ')
    _en=false; [ "$LORE_ENABLED" = 1 ] && _en=true
    _now=$(date +%s)
    printf '{"enabled": %s, "count": %s, "cores": [%s], "ts": %s}\n' "$_en" "${_cnt:-0}" "$_cores" "$_now" > "$_st/${SID_SAFE}.lore.json" 2>/dev/null
    printf '{"level": "%s", "ts": %s}\n' "$VOICE_LEVEL" "$_now" > "$_st/${SID_SAFE}.voice.json" 2>/dev/null
    find "$_st" -maxdepth 1 -type f \( -name '*.lore.json' -o -name '*.voice.json' -o -name '*.effort.json' -o -name '*.spark' \) -mtime +7 -exec rm -f {} + 2>/dev/null
  fi
fi

# ── Assemble, cap, emit ──
CONTEXT="${HEAD}
${LORE_NOTE}${TAIL}"
[ ${#CONTEXT} -gt "$BUDGET" ] && CONTEXT=$(printf '%s' "$CONTEXT" | _cap "$BUDGET")
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}' "$(_json_str "$CONTEXT")"
[ -n "$SYS_MSG" ] && printf ',"systemMessage":"%s"' "$(_json_str "$SYS_MSG")"
printf '}\n'
exit 0

#!/usr/bin/env bash
# SessionStart hook — wizard cat + dynamic inspector + lore injection.

set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
mkdir -p "$PLUGIN_DATA/chronicle"

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PLUGIN_DATA/session-start-time.txt"

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
        ('next',     'nextjs'),
        ('react',    'react'),
        ('vue',      'vue'),
        ('nuxt',     'nuxt'),
        ('express',  'express'),
        ('graphql',  'graphql'),
    ]
    for pkg, tech in checks:
        if pkg in deps:
            print(f'detect_append {tech}')
    if any(k.startswith('@prisma') for k in deps):
        print('detect_append prisma')
except: pass
PYEOF
)"
fi

# ── Deep Python framework detection ─────────────────────────────────────────
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  PY_DEPS=$(cat requirements.txt pyproject.toml 2>/dev/null | \
    grep -oiE '(fastapi|django|flask|torch|tensorflow|pandas|sklearn|scikit-learn|jupyter|notebook)' | \
    tr '[:upper:]' '[:lower:]' | sort -u || true)
  echo "$PY_DEPS" | grep -q "fastapi"            && detect_append "fastapi"
  echo "$PY_DEPS" | grep -q "django"             && detect_append "django"
  echo "$PY_DEPS" | grep -q "flask"              && detect_append "flask"
  echo "$PY_DEPS" | grep -q "torch\|tensorflow"  && { detect_append "pytorch"; ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -q "pandas"             && { detect_append "pandas";  ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -q "sklearn\|scikit"    && { detect_append "sklearn";  ARCHETYPE="data"; }
  echo "$PY_DEPS" | grep -q "jupyter\|notebook"  && { detect_append "jupyter";  ARCHETYPE="data"; }
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
[ -f "build.gradle" ] && grep -q "kotlin" build.gradle 2>/dev/null && detect_append "kotlin"
[ -f "pom.xml" ] && grep -qi "spring" pom.xml 2>/dev/null         && detect_append "spring"
[ -d ".git" ]                                    && detect_append "git"
# node: already detected as javascript; inject node lore for server-side Node projects
[ -f "package.json" ] && [ ! -f "tsconfig.json" ] && grep -qiE '"main"|"bin"' package.json 2>/dev/null && detect_append "node"

([ -d "tests" ] || [ -d "test" ] || [ -d "spec" ] || [ -f "jest.config.js" ] || [ -f "jest.config.ts" ] || [ -f "pytest.ini" ] || [ -f "vitest.config.ts" ]) && detect_append "tdd"

([ -f ".env" ] && grep -qi "postgres\|postgresql" .env 2>/dev/null) || \
  ([ -f "docker-compose.yml" ] && grep -qi "postgres" docker-compose.yml 2>/dev/null) || \
  ([ -f "docker-compose.yaml" ] && grep -qi "postgres" docker-compose.yaml 2>/dev/null) && detect_append "postgres"

detect_append "security"

# ── Lore loader ──────────────────────────────────────────────────────────────
LORE_TEXT=""
LORE_CHARS=0
MAX_LORE=3000

for TECH in $(echo "$TECHS" | tr ',' '\n'); do
  LORE_FILE="$PLUGIN_ROOT/lore/${TECH}.md"
  [ -f "$LORE_FILE" ] || continue
  FRAGMENT=$(cat "$LORE_FILE")
  FL=${#FRAGMENT}
  if [ $((LORE_CHARS + FL)) -le $MAX_LORE ]; then
    LORE_TEXT="${LORE_TEXT}[${TECH}] ${FRAGMENT}

"
    LORE_CHARS=$((LORE_CHARS + FL + ${#TECH} + 4))
  fi
done

# ── LORE_NOTE ────────────────────────────────────────────────────────────────
if [ -n "$TECHS" ]; then
  LORE_NOTE="Stack: ${TECHS}. Archetype: ${ARCHETYPE}."
  [ -n "$LORE_TEXT" ] && LORE_NOTE="${LORE_NOTE} Lore: ${LORE_TEXT}"
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
PROJECT_HASH=$(python3 -c "import hashlib, os; print(hashlib.md5(os.getcwd().encode()).hexdigest()[:12])" 2>/dev/null || echo "default")
INIT_MARKER="$PLUGIN_DATA/projects/$PROJECT_HASH/initialized"

if [ ! -f "$INIT_MARKER" ]; then
  mkdir -p "$(dirname "$INIT_MARKER")"
  FIRST_RUN_NOTE=" MAGICIAN FIRST RUN FOR THIS PROJECT: Before doing any other work, use AskUserQuestion to ask: (1) Are there any files, directories, or patterns in this project that I should NEVER read or write? Examples: proprietary algorithms, vendor directories, generated artifacts, confidential configs. If yes, write them as deny rules in settings.json under permissions.deny using glob patterns like \"Read(**/vendor/**)\" or \"Write(**/proprietary/**)\". (2) Should the workspace be shared with your team via git, or kept private to this machine? After collecting answers, create the file $INIT_MARKER to mark this project as initialized."
fi

CAT_ART=$'         *        \n        /|\\\n       / | \\\n      /  *  \\\n    /_________\\   \n   /\\  o   o  /\\   ---- * . * . * .\n  /   ~~~~~~~   \\   . * . * . * .\n  /  ( ~~~~~ )  \\  * . * . * . *\n  \\_____________/\n    |   | |   |  '

CONTEXT="[MAGICIAN SESSION] At the very start of your first response, greet the user by printing this block inside a code fence verbatim, then proceed to help them:
${CAT_ART}
✦ magician${TECHS:+ · ${TECHS}}${ARCHETYPE:+ · ${ARCHETYPE}}

${LORE_NOTE}${CHRONICLE_NOTE}${STRATEGY_NOTE}${FIRST_RUN_NOTE}"
python3 -c "import json, sys; print(json.dumps({'additionalContext': sys.argv[1]}))" "$CONTEXT"

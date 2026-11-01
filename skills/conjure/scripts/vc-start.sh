#!/usr/bin/env bash
# The companion moved to tools/companion/ in 5.0; this wrapper keeps the /conjure grant working.
# Usage: vc-start.sh <design-dir> <project-name>
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/tools/companion/vc-start.sh" "$@"

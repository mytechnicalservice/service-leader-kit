#!/bin/sh
# SessionStart probe: logs the environment and puts a codeword into Claude's context.
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/lib.sh"
cat >/dev/null
tools=""
for t in sh bash git jq python3 node curl; do
  command -v "$t" >/dev/null 2>&1 && tools="$tools $t"
done
slk_log SessionStart "cwd=$(pwd) project_dir=${CLAUDE_PROJECT_DIR:-<unset>} plugin_root=${CLAUDE_PLUGIN_ROOT:-<unset>} uname=$(uname -sm) tools:$tools"
printf 'SLK-PROBE SessionStart fired. Workspace: %s. Tools:%s. Codeword: KALIBRIERUNG-7.\n' "${CLAUDE_PROJECT_DIR:-$(pwd)}" "$tools"
exit 0

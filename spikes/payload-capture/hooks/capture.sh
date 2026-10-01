#!/bin/sh
# Writes each raw payload to $CLAUDE_PROJECT_DIR/_payloads/<n>-<event>.json. Never blocks.
d="${CLAUDE_PROJECT_DIR:-$(pwd)}/_payloads"
mkdir -p "$d"
n=$(ls "$d" | wc -l | tr -d ' ')
cat > "$d/$(printf '%03d' "$n")-$1.json"
exit 0

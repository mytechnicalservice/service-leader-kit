#!/bin/sh
# PostToolUse probe: logs calls; feeds back when a case file lacks its nr: field (exit 2).
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/lib.sh"
payload=$(cat)
tool=$(slk_field "$payload" tool_name)
agent=$(slk_field "$payload" agent_type)
path=$(slk_field "$payload" file_path)
slk_log PostToolUse "tool=$tool agent_type=${agent:-<none>} path=${path:-<none>}"
case "$path" in
  *01_Vorgaenge/*.md)
    if [ -f "$path" ] && ! grep -q '^nr:' "$path"; then
      slk_log FEEDBACK "missing-nr $path"
      printf 'SLK-PROBE: Die Vorgangsdatei %s hat kein Feld nr: – bitte sofort ergänzen.\n' "$path" >&2
      exit 2
    fi
    ;;
esac
exit 0

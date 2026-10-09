#!/bin/sh
# PreToolUse guard (spec §11). Exit 2 blocks the tool call; the German reason on stderr goes to Claude.
# Inactive outside a kit workspace, so a user-scope install does not affect other projects.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
payload=$(cat)
tool=$(slk_field "$payload" tool_name)
agent=$(slk_top_field "$payload" agent_type)
agent_id=$(slk_top_field "$payload" agent_id)
cwd=$(slk_slashes "$(slk_field "$payload" cwd)")
proj=$(slk_slashes "$(slk_project "$payload")")
[ -n "$cwd" ] || cwd=$proj
ws=$(slk_ws_from "$cwd") || ws=$(slk_ws_from "$proj") || ws=$(slk_ws_below "$proj") || ws=""

block() { # $1 rule id, $2 message
  [ -n "$ws" ] && slk_log "$ws" BLOCK "$1 tool=$tool agent=${agent:-<none>}"
  printf 'Service Leader Kit – gesperrt: %s\n' "$2" >&2
  exit 2
}

case "$tool" in
  Write|Edit|MultiEdit|NotebookEdit) . "$SLK_HOOKS/guard_write.sh" ;;
  Bash|PowerShell|exec_command|shell) [ -n "$ws" ] && . "$SLK_HOOKS/guard_shell.sh" ;;
  apply_patch) . "$SLK_HOOKS/guard_patch.sh" ;;
  mcp__*) [ -n "$ws" ] && . "$SLK_HOOKS/guard_send.sh" ;;
esac
exit 0

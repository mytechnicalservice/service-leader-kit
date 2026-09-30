#!/bin/sh
# PreToolUse probe: logs every call, blocks fixed markers. Exit 2 = block (reason on stderr).
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/lib.sh"
payload=$(cat)
tool=$(slk_field "$payload" tool_name)
agent=$(slk_field "$payload" agent_type)
slk_log PreToolUse "tool=$tool agent_type=${agent:-<none>}"

block() {
  slk_log BLOCK "$1 tool=$tool"
  printf 'SLK-PROBE blocked (%s). Do not retry or work around this; record it in the report.\n' "$1" >&2
  exit 2
}

case "$payload" in
  *PROBE-BLOCK-ME*) block marker ;;
esac
case "$tool" in
  *send_message*|*send_mail*|*sendMail*|*send_email*) block send-tool ;;
esac
if [ "$tool" = "Bash" ]; then
  case "$payload" in
    *'rm '*01_Vorgaenge*) block rm-in-vorgaenge ;;
    *'curl '*|*'wget '*|*sendmail*) block shell-network-or-mail ;;
  esac
fi
exit 0

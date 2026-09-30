#!/bin/sh
# Stop probe: asks Claude to continue exactly once per workspace, to prove Stop feedback works.
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/lib.sh"
payload=$(cat)
case "$payload" in
  *'"stop_hook_active":true'*|*'"stop_hook_active": true'*) slk_log Stop "active=true (silent)"; exit 0 ;;
esac
d=$(slk_logdir)
if [ -f "$d/stop-reminded" ]; then slk_log Stop "already reminded"; exit 0; fi
: > "$d/stop-reminded"
slk_log Stop "reminder sent"
printf '{"decision":"block","reason":"SLK-PROBE Stop-Hook: Schreibe die Zeile STOP-HOOK-OK ans Ende von _slk-probe/report.md und beende dann."}\n'
exit 0

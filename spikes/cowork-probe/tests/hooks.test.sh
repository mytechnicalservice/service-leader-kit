#!/bin/sh
# Runs each hook with a fixture payload and checks exit code + log. POSIX sh.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
HOOKS="$HERE/../hooks"
FIX="$HERE/fixtures"
WS="${TMPDIR:-/tmp}/SLK Test Müller"
rm -rf "$WS"; mkdir -p "$WS"
export CLAUDE_PROJECT_DIR="$WS"
FAILS=0

expect() { # $1 name, $2 hook, $3 fixture, $4 expected exit
  sh "$HOOKS/$2" < "$FIX/$3" >/dev/null 2>"$WS/.stderr"; code=$?
  if [ "$code" -eq "$4" ]; then echo "ok   $1"; else echo "FAIL $1 (exit $code, want $4)"; FAILS=$((FAILS+1)); fi
}
expect_log() { # $1 name, $2 pattern
  if grep -q "$2" "$WS/_slk-probe/log.txt" 2>/dev/null; then echo "ok   $1"; else echo "FAIL $1 (no '$2' in log)"; FAILS=$((FAILS+1)); fi
}

expect "marker in Write is blocked"      pre-tool-use.sh write-marker.json 2
expect "rm in 01_Vorgaenge is blocked"   pre-tool-use.sh bash-rm-vorgaenge.json 2
expect "curl via Bash is blocked"        pre-tool-use.sh bash-curl.json 2
expect "mail send tool is blocked"       pre-tool-use.sh mail-send.json 2
expect "harmless multi-line is allowed"  pre-tool-use.sh bash-harmless-multiline.json 0
expect_log "log written in path with spaces" "PreToolUse"
expect_log "agent_type parsed from multi-line JSON" "agent_type=slk-probe-writer"
expect_log "block reason logged" "BLOCK.*send-tool"

# Unwritable workspace: hook must still decide correctly and log to TMPDIR.
RO="${TMPDIR:-/tmp}/slk-ro-ws"; rm -rf "$RO"; mkdir -p "$RO"; chmod 555 "$RO"
CLAUDE_PROJECT_DIR="$RO" sh "$HOOKS/pre-tool-use.sh" < "$FIX/bash-curl.json" >/dev/null 2>&1; code=$?
chmod 755 "$RO"
if [ "$code" -eq 2 ]; then echo "ok   read-only workspace still blocks"; else echo "FAIL read-only workspace (exit $code)"; FAILS=$((FAILS+1)); fi

echo "---"; [ "$FAILS" -eq 0 ] && echo "ALL PASS" || { echo "$FAILS FAILED"; exit 1; }

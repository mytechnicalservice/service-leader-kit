#!/bin/sh
# Shared helpers for the probe hooks. POSIX sh only: no jq, python or node.

# First string value of a JSON key, from a payload that may span several lines.
slk_field() {
  printf '%s' "$1" | tr '\n' ' ' |
    sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
}

slk_logdir() {
  d="${CLAUDE_PROJECT_DIR:-$(pwd)}/_slk-probe"
  if mkdir -p "$d" 2>/dev/null && [ -w "$d" ]; then printf '%s' "$d"; return; fi
  d="${TMPDIR:-/tmp}/_slk-probe"
  mkdir -p "$d" 2>/dev/null
  printf '%s' "$d"
}

slk_log() {
  d=$(slk_logdir)
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >> "$d/log.txt" 2>/dev/null
  return 0
}

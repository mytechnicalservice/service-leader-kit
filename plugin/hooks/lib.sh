#!/bin/sh
# Shared helpers for the kit's hooks (spec §11). POSIX sh + awk/sed/tr only: no jq, python or node.
LC_ALL=C
export LC_ALL
SLK_HOOKS=${SLK_HOOKS:-$(cd "$(dirname "$0")" && pwd)}
SLK_PLUGIN=$(dirname "$SLK_HOOKS")

# First value of a JSON key in a payload (see json.awk). Empty if absent.
slk_field() { printf '%s' "$1" | awk -v want="$2" -f "$SLK_HOOKS/json.awk"; }

# Backslashes to slashes (Windows paths), and a lower-cased copy for matching (macOS/Windows ignore case).
slk_slashes() { printf '%s' "$1" | tr '\\' '/'; }
slk_lower() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

# True if $1 is a kit workspace: it has 01_Vorgaenge/ or Unternehmen/.kit-config.
slk_is_ws() { [ -n "$1" ] && { [ -d "$1/01_Vorgaenge" ] || [ -f "$1/Unternehmen/.kit-config" ]; }; }

# Prints the workspace that contains directory $1 (walking up at most 12 levels); exit 1 if none.
slk_ws_from() {
  d=$(slk_slashes "$1"); d=${d%/}; n=0
  while [ -n "$d" ] && [ "$n" -lt 12 ]; do
    if slk_is_ws "$d"; then printf '%s' "$d"; return 0; fi
    p=${d%/*}; [ "$p" = "$d" ] && break
    d=$p; n=$((n + 1))
  done
  return 1
}

# Prints the first workspace directly inside $1 (the user opened the parent folder); exit 1 if none.
slk_ws_below() {
  for c in "$1"/*/; do
    c=${c%/}
    if slk_is_ws "$c"; then printf '%s' "$c"; return 0; fi
  done
  return 1
}

# Prints the directory that contains folder $2 (lower-case name) in path $1, in the path's own case.
# Paths relative to it resolve against $3 (the tool call's cwd).
slk_root_of() {
  p=$(slk_slashes "$1"); l=$(slk_lower "$p")
  case "$l" in
    "$2"/*|./"$2"/*) printf '%s' "$3" ;;
    */"$2"/*)
      pre=${l%%/"$2"/*}
      if [ -z "$pre" ]; then printf '/'; else printf '%s' "$(printf '%s' "$p" | cut -c "1-${#pre}")"; fi ;;
  esac
}

# Validated settings of workspace $1 as key=value lines; exit 1 (no output) if missing or invalid.
slk_config() {
  [ -f "$1/Unternehmen/.kit-config" ] || return 1
  awk -v schema="$SLK_PLUGIN/vorlagen/kit-config.schema" -f "$SLK_HOOKS/kit_config.awk" "$1/Unternehmen/.kit-config"
}

# Value of key $2 in key=value text $1 (first match).
slk_get() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n 1; }

# Appends one line to Unternehmen/.kit-protokoll of workspace $1 (kept below 256 KB). Never fails.
slk_log() {
  [ "${SLK_KEIN_PROTOKOLL:-}" = 1 ] && return 0
  f="$1/Unternehmen/.kit-protokoll"
  [ -d "$1/Unternehmen" ] || return 0
  if [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 262144 ]; then mv -f "$f" "$f.1" 2>/dev/null; fi
  printf '%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$2" "$3" >> "$f" 2>/dev/null
  return 0
}

# Text as a JSON string literal (quotes, backslashes, tabs and line breaks escaped).
slk_json_str() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/	/\\t/g' |
    awk 'NR > 1 { printf "\\n" } { printf "%s", $0 }' | { printf '"'; cat; printf '"'; }
}

# Day number (days since 1970-01-01) of date $1 = YYYY-MM-DD (civil-from-days, pure arithmetic).
slk_days() {
  y=${1%%-*}; m=${1#*-}; d=${m#*-}; m=${m%%-*}; m=${m#0}; d=${d#0}
  [ "$m" -le 2 ] && y=$((y - 1))
  era=$((y / 400)); yoe=$((y - era * 400)); mp=$(((m + 9) % 12))
  doy=$(((153 * mp + 2) / 5 + d - 1)); doe=$((yoe * 365 + yoe / 4 - yoe / 100 + doy))
  echo $((era * 146097 + doe - 719468))
}

# Weekday of date $1: 0 = Monday … 6 = Sunday.
slk_wochentag() { echo $((($(slk_days "$1") + 3) % 7)); }

# True if version $1 is newer than version $2 (x.y.z, numbers only; missing parts count as 0).
slk_ver_gt() {
  a=$1; b=$2; i=0
  while [ "$i" -lt 3 ]; do
    x=${a%%.*}; y=${b%%.*}; x=${x:-0}; y=${y:-0}
    [ "$x" -gt "$y" ] 2>/dev/null && return 0
    [ "$x" -lt "$y" ] 2>/dev/null && return 1
    case "$a" in *.*) a=${a#*.} ;; *) a=0 ;; esac
    case "$b" in *.*) b=${b#*.} ;; *) b=0 ;; esac
    i=$((i + 1))
  done
  return 1
}

#!/bin/sh
# Shared helpers for the kit's hooks (spec §11). POSIX sh + awk/sed/tr only: no jq, python or node.
LC_ALL=C
export LC_ALL
SLK_HOOKS=${SLK_HOOKS:-$(cd "$(dirname "$0")" && pwd)}
SLK_PLUGIN=$(dirname "$SLK_HOOKS")
SLK_CODEX=0
[ -f "$SLK_PLUGIN/VARIANTE" ] && [ "$(tr -d ' \r\n' < "$SLK_PLUGIN/VARIANTE")" = codex ] && SLK_CODEX=1

# Identity must come from the host, never from nested tool arguments.
slk_top_field() { printf '%s' "$1" | awk -v want="$2" -v top=1 -f "$SLK_HOOKS/json.awk"; return 0; }
slk_project() {
  if [ "$SLK_CODEX" = 1 ]; then
    _slk_project=$(slk_top_field "$1" cwd)
    printf '%s' "${_slk_project:-$(pwd)}"
  else printf '%s' "${CLAUDE_PROJECT_DIR:-$(pwd)}"; fi
}

# First value of a JSON key in a payload (see json.awk). Empty if absent; always succeeds.
slk_field() { printf '%s' "$1" | awk -v want="$2" -f "$SLK_HOOKS/json.awk"; return 0; }

# Backslashes to slashes (Windows paths), and a lower-cased copy for matching (macOS/Windows ignore case).
slk_slashes() { printf '%s' "$1" | tr '\\' '/'; }
slk_lower() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

# True if $1 is a kit workspace: it has 01_Vorgaenge/ or Unternehmen/.kit-config.
slk_is_ws() { [ -n "$1" ] && { [ -d "$1/01_Vorgaenge" ] || [ -f "$1/Unternehmen/.kit-config" ]; }; }

# Prints the workspace that contains directory $1 (walking up to the root); exit 1 if none.
# Function-internal variables are _slk_-prefixed so they never clobber a hook's own.
slk_ws_from() {
  _slk_d=$(slk_slashes "$1"); _slk_d=${_slk_d%/}
  while [ -n "$_slk_d" ]; do
    if slk_is_ws "$_slk_d"; then printf '%s' "$_slk_d"; return 0; fi
    _slk_p=${_slk_d%/*}; [ "$_slk_p" = "$_slk_d" ] && break
    _slk_d=$_slk_p
  done
  return 1
}

# Prints the first workspace directly inside $1 (the user opened the parent folder); exit 1 if none.
slk_ws_below() {
  [ -n "$1" ] || return 1
  for _slk_c in "$1"/*/; do
    _slk_c=${_slk_c%/}
    if slk_is_ws "$_slk_c"; then printf '%s' "$_slk_c"; return 0; fi
  done
  return 1
}

# Absolute, lexically collapsed form of path $1 (relative paths resolve against $2): backslashes become
# slashes; "//", "/./" and "seg/.." collapse; a leading "X:" drive is kept. Case is left alone.
slk_norm_path() {
  _slk_n=$(slk_slashes "$1")
  case "$_slk_n" in /*|[A-Za-z]:/*) ;; *) _slk_n="$(slk_slashes "$2")/$_slk_n" ;; esac
  printf '%s' "$_slk_n" | awk '{
    drive = ""
    if ($0 ~ /^[A-Za-z]:/) { drive = substr($0, 1, 2); $0 = substr($0, 3) }
    n = split($0, a, "/"); m = 0
    for (i = 1; i <= n; i++) {
      if (a[i] == "" || a[i] == ".") continue
      if (a[i] == "..") { if (m > 0) m--; continue }
      m++; o[m] = a[i]
    }
    r = ""
    for (i = 1; i <= m; i++) r = r "/" o[i]
    if (r == "") r = "/"
    printf "%s%s", drive, r
  }'
}

# For normalized path $1 and lower-case folder name $2: tries the part before EVERY "/name/" occurrence
# (original case) and prints the first that is a workspace; exit 1 if none.
slk_ws_for() {
  _slk_rest=$(slk_lower "$1"); _slk_off=0
  while :; do
    case "$_slk_rest" in *"/$2/"*) ;; *) return 1 ;; esac
    _slk_pre=${_slk_rest%%"/$2/"*}
    _slk_off=$((_slk_off + ${#_slk_pre}))
    if [ "$_slk_off" -eq 0 ]; then _slk_r=/; else _slk_r=$(printf '%s' "$1" | cut -c "1-$_slk_off"); fi
    if slk_is_ws "$_slk_r"; then printf '%s' "$_slk_r"; return 0; fi
    _slk_off=$((_slk_off + ${#2} + 1))
    _slk_rest="/${_slk_rest#*"/$2/"}"
  done
}

# Validated settings of workspace $1 as key=value lines; exit 1 (no output) if missing or invalid.
slk_config() {
  [ -f "$1/Unternehmen/.kit-config" ] || return 1
  awk -v schema="$SLK_PLUGIN/vorlagen/kit-config.schema" -f "$SLK_HOOKS/kit_config.awk" "$1/Unternehmen/.kit-config"
}

# Value of key $2 in key=value text $1 (first match).
slk_get() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n 1; }

# Appends one line to Unternehmen/.kit-protokoll of workspace $1 (kept below 256 KB). Never fails.
# Tabs and line breaks in the text $3 become spaces, so one event stays one line.
slk_log() {
  [ "${SLK_KEIN_PROTOKOLL:-}" = 1 ] && return 0
  _slk_f="$1/Unternehmen/.kit-protokoll"
  [ -d "$1/Unternehmen" ] || return 0
  if [ -f "$_slk_f" ] && [ "$(wc -c < "$_slk_f")" -gt 262144 ]; then mv -f "$_slk_f" "$_slk_f.1" 2>/dev/null; fi
  _slk_t=$(printf '%s' "$3" | tr '\t\n' '  ')
  printf '%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$2" "$_slk_t" >> "$_slk_f" 2>/dev/null
  return 0
}

# Text as a JSON string literal (quotes, backslashes, tabs, CR and line breaks escaped; other control chars dropped).
slk_json_str() {
  printf '%s' "$1" | tr -d '\000-\010\013\014\016-\037' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/	/\\t/g' |
    awk 'NR > 1 { printf "\\n" } { gsub(/\r/, "\\r"); printf "%s", $0 }' | { printf '"'; cat; printf '"'; }
}

# Day number (days since 1970-01-01) of date $1 = YYYY-MM-DD (civil-from-days, pure arithmetic).
# Prints nothing and fails on any other input.
slk_days() {
  case "$1" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) return 1 ;; esac
  _slk_y=${1%%-*}; _slk_m=${1#*-}; _slk_dd=${_slk_m#*-}; _slk_m=${_slk_m%%-*}; _slk_m=${_slk_m#0}; _slk_dd=${_slk_dd#0}
  [ "$_slk_m" -le 2 ] && _slk_y=$((_slk_y - 1))
  _slk_era=$((_slk_y / 400)); _slk_yoe=$((_slk_y - _slk_era * 400)); _slk_mp=$(((_slk_m + 9) % 12))
  _slk_doy=$(((153 * _slk_mp + 2) / 5 + _slk_dd - 1))
  _slk_doe=$((_slk_yoe * 365 + _slk_yoe / 4 - _slk_yoe / 100 + _slk_doy))
  echo $((_slk_era * 146097 + _slk_doe - 719468))
}

# Weekday of date $1: 0 = Monday … 6 = Sunday. Prints nothing and fails on a malformed date.
slk_wochentag() { _slk_n=$(slk_days "$1") || return 1; echo $(((_slk_n + 3) % 7)); }

# True if version $1 is newer than version $2 (x.y.z, numbers only; missing parts count as 0).
slk_ver_gt() {
  _slk_a=$1; _slk_b=$2; _slk_i=0
  while [ "$_slk_i" -lt 3 ]; do
    _slk_x=${_slk_a%%.*}; _slk_y=${_slk_b%%.*}; _slk_x=${_slk_x:-0}; _slk_y=${_slk_y:-0}
    [ "$_slk_x" -gt "$_slk_y" ] 2>/dev/null && return 0
    [ "$_slk_x" -lt "$_slk_y" ] 2>/dev/null && return 1
    case "$_slk_a" in *.*) _slk_a=${_slk_a#*.} ;; *) _slk_a=0 ;; esac
    case "$_slk_b" in *.*) _slk_b=${_slk_b#*.} ;; *) _slk_b=0 ;; esac
    _slk_i=$((_slk_i + 1))
  done
  return 1
}

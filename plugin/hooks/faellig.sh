# Routine announcements for session start (spec §8, §11). Sourced after lib.sh; defines slk_faellig.
# Unternehmen/.kit-status (written by the routines, Plan 4) holds: tagesstart=YYYY-MM-DD,
# wochenstart=YYYY-MM-DD, monatsabschluss=YYYY-MM, quartal=YYYY-Qn. Missing or malformed = not run.

# Day of month of the first Monday–Friday of month $1 = YYYY-MM (public holidays are not known).
slk_erster_werktag() {
  case "$(slk_wochentag "$1-01")" in 5) echo 3 ;; 6) echo 2 ;; *) echo 1 ;; esac
}

# True if status entry $1 has the form $2 (tag, monat, quartal, jahr) and lies after $3, which has the same form.
slk_status_nach() {
  case "$2:$1" in
    tag:[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]|monat:[12][0-9][0-9][0-9]-[01][0-9]) ;;
    quartal:[12][0-9][0-9][0-9]-Q[1-4]|jahr:[12][0-9][0-9][0-9]) ;;
    *) return 1 ;;
  esac
  [ "$(printf '%s' "$1" | tr -cd 0-9)" -gt "$(printf '%s' "$3" | tr -cd 0-9)" ]
}

# Prints one line per status entry of $2 dated after the reference date $1. Such an entry says nothing about whether
# the routine is due, so slk_faellig does not announce it either: the entry is what needs checking.
slk_status_zukunft() {
  h=$1; jm=${h%-*}; jahr=${h%%-*}; mon=${jm#*-}; mon=${mon#0}; q="$jahr-Q$(((mon - 1) / 3 + 1))"
  for _slk_e in tagesstart:tag:$h wochenstart:tag:$h monatsabschluss:monat:$jm quartal:quartal:$q jahresplanung:jahr:$jahr; do
    _slk_k=${_slk_e%%:*}; _slk_r=${_slk_e#*:}; _slk_w=$(slk_get "$2" "$_slk_k")
    if slk_status_nach "$_slk_w" "${_slk_r%%:*}" "${_slk_r#*:}"; then echo "$_slk_k=$_slk_w"; fi
  done
}

# Prints one line per routine due on date $1, given settings $2 and status $3.
slk_faellig() {
  h=$1; jahr=${h%%-*}; jm=${h%-*}; mon=${jm#*-}; mon=${mon#0}; tag=${h##*-}; tag=${tag#0}
  _slk_s=$(slk_get "$3" tagesstart)
  if [ "$_slk_s" != "$h" ] && ! slk_status_nach "$_slk_s" tag "$h"; then
    echo "tagesstart ist heute noch nicht gelaufen (\"Guten Morgen\")."
  fi

  idx=0
  for d in mo di mi do fr; do [ "$d" = "$(slk_get "$2" wochenstart)" ] && break; idx=$((idx + 1)); done
  wt=$(slk_wochentag "$h"); montag=$(($(slk_days "$h") - wt))
  zuletzt=$(slk_get "$3" wochenstart)
  case "$zuletzt" in [12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]) ;; *) zuletzt="" ;; esac
  if [ "$wt" -ge "$idx" ] && { [ -z "$zuletzt" ] || [ "$(slk_days "$zuletzt")" -lt "$montag" ]; }; then
    echo "wochenstart ist fällig."
  fi

  ms=$(slk_get "$2" monatsstart)
  if [ "$ms" = erster-werktag ]; then ms=$(slk_erster_werktag "$jm"); fi
  _slk_s=$(slk_get "$3" monatsabschluss)
  if [ "$_slk_s" != "$jm" ] && ! slk_status_nach "$_slk_s" monat "$jm" && [ "$tag" -ge "$ms" ]; then
    echo "monatsabschluss ist fällig."
  fi

  q=$(((mon - 1) / 3 + 1)); qm=$(((q - 1) * 3 + 1))
  qtag=$(slk_erster_werktag "$(printf '%s-%02d' "$jahr" "$qm")")
  _slk_s=$(slk_get "$3" quartal)
  if [ "$_slk_s" != "$jahr-Q$q" ] && ! slk_status_nach "$_slk_s" quartal "$jahr-Q$q" &&
     { [ "$mon" -gt "$qm" ] || [ "$tag" -ge "$qtag" ]; }; then
    echo "quartal ist fällig."
  fi
}

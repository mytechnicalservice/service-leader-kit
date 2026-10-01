# Routine announcements for session start (spec §8, §11). Sourced after lib.sh; defines slk_faellig.
# Unternehmen/.kit-status (written by the routines, Plan 4) holds: tagesstart=YYYY-MM-DD,
# wochenstart=YYYY-MM-DD, monatsabschluss=YYYY-MM, quartal=YYYY-Qn. Missing or malformed = not run.

# Day of month of the first Monday–Friday of month $1 = YYYY-MM (public holidays are not known).
slk_erster_werktag() {
  case "$(slk_wochentag "$1-01")" in 5) echo 3 ;; 6) echo 2 ;; *) echo 1 ;; esac
}

# Prints one line per routine due on date $1, given settings $2 and status $3.
slk_faellig() {
  h=$1; jahr=${h%%-*}; jm=${h%-*}; mon=${jm#*-}; mon=${mon#0}; tag=${h##*-}; tag=${tag#0}
  [ "$(slk_get "$3" tagesstart)" = "$h" ] || echo "tagesstart ist heute noch nicht gelaufen (\"Guten Morgen\")."

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
  if [ "$(slk_get "$3" monatsabschluss)" != "$jm" ] && [ "$tag" -ge "$ms" ]; then
    echo "monatsabschluss ist fällig."
  fi

  q=$(((mon - 1) / 3 + 1)); qm=$(((q - 1) * 3 + 1))
  qtag=$(slk_erster_werktag "$(printf '%s-%02d' "$jahr" "$qm")")
  if [ "$(slk_get "$3" quartal)" != "$jahr-Q$q" ] && { [ "$mon" -gt "$qm" ] || [ "$tag" -ge "$qtag" ]; }; then
    echo "quartal ist fällig."
  fi
}

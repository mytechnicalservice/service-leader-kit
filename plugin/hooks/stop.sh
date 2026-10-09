#!/bin/sh
# Stop hook (spec §11): backs the workspace up per .kit-config and asks Claude once to log work on its case.
# Output: nothing, or one JSON object (decision/reason: Claude continues once; systemMessage: shown to the user).
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
payload=$(cat)
ws=$(slk_ws_from "$(slk_slashes "$(slk_project "$payload")")") || exit 0
U="$ws/Unternehmen"
aktiv=$(printf '%s' "$payload" | tr -d ' \t\r\n' | grep -c '"stop_hook_active":true')
cfg=$(slk_config "$ws") || cfg=""
meldung=""; grund=""

# 1. Backup, only with valid settings (the safe fallback is "no git", spec §7.1).
if [ "$(slk_get "$cfg" ablage)" = github ] && [ -e "$ws/.git" ] && command -v git >/dev/null 2>&1; then
  . "$SLK_HOOKS/sicherung.sh"
fi

# 2. Case reminder (decision D4): work files changed since the last Stop, no case file did, an open case exists.
stamp="$U/.kit-letzter-stop"
if [ "$aktiv" = 0 ] && [ -f "$stamp" ]; then
  arbeit=$(find "$ws/02_Postausgang" "$ws/03_Berichte" "$ws/04_Angebote" "$ws/05_Projekte" "$ws/06_Kunden" \
             -type f -newer "$stamp" ! -name '.*' ! -name '~$*' 2>/dev/null | head -n 1)
  fall=$(find "$ws/01_Vorgaenge" -type f -name 'V-*.md' -newer "$stamp" 2>/dev/null | head -n 1)
  offen=$(find "$ws/01_Vorgaenge/offen" -type f -name 'V-*.md' 2>/dev/null | head -n 1)
  if [ -n "$arbeit" ] && [ -z "$fall" ] && [ -n "$offen" ]; then
    grund="Service Leader Kit: Es ist ein neues Arbeitsergebnis entstanden (${arbeit#"$ws"/}), aber kein Vorgang wurde aktualisiert. Gehört die Arbeit zu einem offenen Vorgang, trag sie mit vorgang.py eintrag ein. Sonst antworte nur: kein Vorgang betroffen."
  fi
fi
[ -d "$U" ] && touch "$stamp" 2>/dev/null

[ -n "$grund$meldung" ] || exit 0
sep=""
printf '{'
if [ -n "$grund" ]; then printf '"decision":"block","reason":%s' "$(slk_json_str "$grund")"; sep=","; fi
if [ -n "$meldung" ]; then printf '%s"systemMessage":%s' "$sep" "$(slk_json_str "$meldung")"; fi
printf '}\n'
exit 0

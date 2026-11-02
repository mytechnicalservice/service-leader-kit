#!/bin/sh
# SessionStart (spec §11): checks the settings and the guards, and tells Claude what is due. Stdout reaches
# Claude. Silent outside a kit workspace. tagesstart computes the same list, so nothing depends on this alone.
# Not announced here (decision D2): cases past retention — gesundheitscheck (Plan 2c) reports them.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
. "$SLK_HOOKS/faellig.sh"
payload=$(cat)
proj=$(slk_slashes "$(slk_project "$payload")")
if ! ws=$(slk_ws_from "$proj"); then
  if sub=$(slk_ws_below "$proj"); then
    printf 'Service Leader Kit: Der Kundendienst-Ordner ist %s. Bitte den Nutzer, genau diesen Ordner in VS Code zu öffnen (Datei → Ordner öffnen); sonst fehlen die Hinweise beim Start.\n' "$sub"
  fi
  exit 0
fi
U="$ws/Unternehmen"
out=""
add() { out="$out
- $1"; }
# The reference date: a valid demo_datum replaces the system date for everything below (arbeitsordner.bezugstag).
# The protocol and backups keep the real time: they record when something really happened.
systemtag=$(date +%Y-%m-%d)
heute=$systemtag
cfg=""; cfg_ok=0
if cfg=$(slk_config "$ws"); then cfg_ok=1; fi
demo=$(slk_get "$cfg" demo_datum)
if [ "$cfg_ok" = 1 ] && [ -n "$demo" ]; then
  heute=$demo
  add "Demo-Datum aktiv: Bezugsdatum $(slk_de_datum "$heute") statt Systemdatum $(slk_de_datum "$systemtag") (Unternehmen/.kit-config, demo_datum). Fälligkeiten, Routinen und Skripte rechnen damit. Nenne das in jeder Antwort und jedem internen Dokument, nimm dieses Datum für Datumsangaben und Dateinamen und übergib --heute nur, wenn der Nutzer selbst ein anderes Datum nennt. Zurück zum Systemdatum: Einrichtung mit --demo-datum aus."
fi

# The guards must block a known-bad call on this computer; a broken shell or awk would let everything through.
# Exit 2 alone is not proof: dash also exits 2 on a missing or broken sourced file, so the guard's own message is required too.
pruefe() {
  r=$(printf '%s' "$1" | SLK_KEIN_PROTOKOLL=1 sh "$SLK_HOOKS/pre-tool-use.sh" 2>&1 >/dev/null; echo "rc=$?")
  case "$r" in "Service Leader Kit – gesperrt:"*"rc=2") return 0 ;; *) return 1 ;; esac
}
bom=$(printf '\357\273\277')
w=$(slk_json_str "$ws")
if ! pruefe "{\"tool_name\":\"Bash\",\"cwd\":$w,\"tool_input\":{\"command\":\"rm 01_Vorgaenge/selbsttest.md\"}}" ||
   ! pruefe "{\"tool_name\":\"Write\",\"cwd\":$w,\"tool_input\":{\"file_path\":$(slk_json_str "$ws/Unternehmen/selbsttest.md")}}"; then
  add "ACHTUNG: Die Schutzregeln des Kits funktionieren auf diesem Rechner nicht (Selbsttest fehlgeschlagen). Lösch-, Schreib- und Sendesperren sind nicht aktiv. Arbeite nur lesend und sag dem Nutzer, er soll myTS informieren."
  slk_log "$ws" SELBSTTEST "fehlgeschlagen"
fi

# Plugin: .claude-plugin/plugin.json. Eigene Kopie (.claude/kit): VERSION, agents in .claude/agents.
if [ -f "$SLK_PLUGIN/VERSION" ]; then v_kit=$(tr -d ' \r\n' < "$SLK_PLUGIN/VERSION"); agents="$SLK_PLUGIN/../agents"
else v_kit=$(slk_field "$(cat "$SLK_PLUGIN/.claude-plugin/plugin.json" 2>/dev/null)" version); agents="$SLK_PLUGIN/agents"; fi
v_ws=""; [ -f "$U/.kit-version" ] && v_ws=$(tr -d ' \r\n' < "$U/.kit-version" | sed "s/^$bom//")
if [ -n "$v_kit" ] && slk_ver_gt "$v_kit" "${v_ws:-0}"; then
  add "Neue Kit-Version $v_kit (Ordner: ${v_ws:-unbekannt}): zuerst gesundheitscheck ausführen."
fi

st=""; [ -f "$U/.kit-status" ] && st=$(tr -d '\r' < "$U/.kit-status" | sed "1s/^$bom//")
if [ "$cfg_ok" = 1 ]; then
  due=$(slk_faellig "$heute" "$cfg" "$st")
  [ -n "$due" ] && out="$out
$(printf '%s\n' "$due" | sed 's/^/- /')"
else
  add "Einstellungen unvollständig – bitte Einrichtung erneut ausführen (\"richte den Kundendienst ein\"). Bis dahin: keine Git-Sicherung, Mails nur als Entwurf in 02_Postausgang/, keine Routine-Hinweise."
  slk_log "$ws" EINSTELLUNGEN "ungültig oder fehlend"
fi

n=0
for f in "$ws/00_Eingang"/*; do
  [ -f "$f" ] || continue
  case "${f##*/}" in LIESMICH.md|'~$'*) continue ;; esac
  n=$((n + 1))
done
[ "$n" -gt 0 ] && add "$n Datei(en) im Eingang (00_Eingang/)."

liste=""; k=0
for f in "$ws/01_Vorgaenge/offen"/V-*.md; do
  [ -f "$f" ] || continue
  fa=$(sed -n 's/^faellig: "\([0-9-]*\)".*/\1/p' "$f" | head -n 1)
  case "$fa" in [12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]) ;; *) continue ;; esac
  [ "$(printf '%s' "$fa" | tr -d -)" -lt "$(printf '%s' "$heute" | tr -d -)" ] || continue
  k=$((k + 1))
  [ "$k" -le 10 ] && liste="$liste, $(basename "$f" .md) (fällig $fa)"
done
if [ "$k" -gt 0 ]; then
  rest=""; [ "$k" -gt 10 ] && rest=" und $((k - 10)) weitere"
  add "Überfällig: ${liste#, }$rest."
fi

# Entries dated after the reference date: nothing is recalculated, the user has to look at them.
kommagetrennt() { head -n 5 | tr '\n' ',' | sed 's/,$//; s/,/, /g'; }
zukunft=""
z_status=$(slk_status_zukunft "$heute" "$st")
[ -n "$z_status" ] && zukunft="$zukunft Status: $(printf '%s\n' "$z_status" | kommagetrennt)."
z_dateien=$(find "$ws/00_Eingang" "$ws/02_Postausgang" "$ws/03_Berichte" "$ws/04_Angebote" "$ws/05_Projekte" "$ws/06_Kunden" \
              -type f -name '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]_*' 2>/dev/null | sed 's|.*/||' |
              awk -v h="$heute" 'substr($0, 1, 10) > h' | sort)
if [ -n "$z_dateien" ]; then
  m=$(printf '%s\n' "$z_dateien" | wc -l | tr -d ' ')
  rest=""; [ "$m" -gt 5 ] && rest=" und $((m - 5)) weitere"
  zukunft="$zukunft Dateien: $(printf '%s\n' "$z_dateien" | kommagetrennt)$rest."
fi
z_faelle=""; z_mails=""
for f in "$ws/01_Vorgaenge/offen"/V-*.md; do
  [ -f "$f" ] || continue
  awk -v h="$heute" 'substr($0, 1, 4) == "### " && substr($0, 5, 4) ~ /^[12][0-9][0-9][0-9]$/ && substr($0, 5, 10) > h { spaet = 1 }
    /^(erstellt|aktualisiert): "/ { if (substr($2, 2, 10) > h) spaet = 1 } END { exit !spaet }' "$f" &&
    z_faelle="$z_faelle$(basename "$f" .md)
"
done
[ -n "$z_faelle" ] && zukunft="$zukunft Vorgänge: $(printf '%s' "$z_faelle" | kommagetrennt)."
for f in "$ws/00_Eingang"/*.eml; do
  [ -f "$f" ] || continue
  tag=$(slk_mail_tag "$f")
  [ -n "$tag" ] && [ "$(printf '%s' "$tag" | tr -d -)" -gt "$(printf '%s' "$heute" | tr -d -)" ] &&
    z_mails="$z_mails${f##*/}
"
done
[ -n "$z_mails" ] && zukunft="$zukunft Mails: $(printf '%s' "$z_mails" | kommagetrennt)."
[ -n "$zukunft" ] && add "Datiert nach dem Bezugsdatum $(slk_de_datum "$heute"):$zukunft Bitte prüfen, das Kit rechnet nichts um."

[ -d "$U" ] && touch "$U/.kit-stand.jetzt" 2>/dev/null
if [ -f "$U/.kit-stand" ]; then
  # Like stop.sh: a modification time after this moment would count as changed at every session start.
  neu=$(find "$U" -type f ! -name '.kit-*' ! -name '~$*' -newer "$U/.kit-stand" ! -newer "$U/.kit-stand.jetzt" 2>/dev/null | sed 's|.*/||' | sort)
  if [ -n "$neu" ]; then
    m=$(printf '%s\n' "$neu" | wc -l | tr -d ' ')
    namen=$(printf '%s\n' "$neu" | head -n 5 | tr '\n' ',' | sed 's/,$//; s/,/, /g')
    rest=""; [ "$m" -gt 5 ] && rest=" und $((m - 5)) weitere"
    add "Geändert in Unternehmen/ seit der letzten Sitzung: $namen$rest. Bitte kurz mit dem Nutzer bestätigen."
  fi
fi
[ -f "$U/.kit-stand.jetzt" ] && mv -f "$U/.kit-stand.jetzt" "$U/.kit-stand" 2>/dev/null

context() {
printf 'Service Leader Kit – Stand %s, Ordner %s%s\n' "$heute" "$ws" "${out:-
- Nichts fällig.}"
# D12: the main conversation is the coordinator. Its persona is the marked block in agents/assistenz.md (one source).
if [ "$SLK_CODEX" = 1 ]; then
  instructions=$(sed 's/^developer_instructions = /"developer_instructions":/' "$agents/assistenz.toml" 2>/dev/null)
  persona=$(slk_field "$instructions" developer_instructions | sed -n '/<!-- persona:anfang -->/,/<!-- persona:ende -->/p' | sed '1d;$d')
else
  persona=$(sed -n '/<!-- persona:anfang -->/,/<!-- persona:ende -->/p' "$agents/assistenz.md" 2>/dev/null | sed '1d;$d')
fi
[ -n "$persona" ] && printf '\n%s\n' "$persona"
}
if [ "$SLK_CODEX" = 1 ]; then
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":%s}}\n' "$(slk_json_str "$(context)")"
else context; fi
exit 0

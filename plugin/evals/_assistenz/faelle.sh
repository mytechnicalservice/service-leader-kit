# Assistenz evals (Plan 4i): writes test cases into 01_Vorgaenge/offen/. POSIX sh, sourced after
# _gemeinsam/arbeitsordner.sh. Titles and texts must not contain double quotes.
# fall <nr> <typ> <status> <kunde> <faellig|-> <betrag|-> <wartet_auf|-> <titel> [<empfehlung>]
fall() {
  _fa=null; [ "$5" = - ] || _fa="\"$5\""
  _b=null; [ "$6" = - ] || _b=$6
  _w=null; [ "$7" = - ] || _w="\"$7\""
  _bv='["betrieb"]'; [ $# -lt 9 ] || _bv='["betrieb", "finanzen"]'
  {
    printf '%s\n' '---'
    printf 'nr: "%s"\ntitel: "%s"\ntyp: "%s"\nstatus: "%s"\nkunde: "%s"\nexterne_nr: null\n' "$1" "$8" "$2" "$3" "$4"
    printf 'verantwortlich: "Max Mustermann (Leitung Kundendienst)"\nbearbeitet_von: %s\nfaellig: %s\n' "$_bv" "$_fa"
    printf 'wartet_auf: %s\nbetrag_eur: %s\nentscheidung: null\nentschieden_von: null\n' "$_w" "$_b"
    printf 'entschieden_am: null\nentschiedenes_dokument: null\nerstellt: "2026-09-20"\naktualisiert: "2026-09-20"\n'
    printf '%s\n' '---'
    printf '\n### 2026-09-20 · angelegt · betrieb\n\nTestvorgang der Assistenz-Evals.\n'
    if [ $# -ge 9 ]; then printf '\n### 2026-10-05 · empfehlung · finanzen\n\n%s\n' "$9"; fi
  } > "01_Vorgaenge/offen/$1.md"
}

grundbestand() {
  fall V-0004 freigabe offen "Hansa Pack AG" 2026-10-07 12500 - "Retrofit Steuerung Linie 2" \
    "Empfehlung: zustimmen mit Auflagen – Marge 31 %, Zahlungsziel 30 Tage. Quelle: 04_Angebote/Hansa Pack AG/2026-10-01_angebot-retrofit.md"
  fall V-0005 entscheidung offen "Müller GmbH" 2027-01-15 4800 - "Kulanz Spindel Anlage 4" \
    "Empfehlung: ablehnen – Schaden durch Bedienfehler laut Servicebericht."
  fall V-0006 freigabe offen "Nordmetall KG" 2026-10-09 - - "Rahmenvertrag Wartung"
}

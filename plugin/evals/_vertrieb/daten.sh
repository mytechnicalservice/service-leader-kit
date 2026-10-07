# Vertrieb eval helpers (sourced after ../_gemeinsam/arbeitsordner.sh; POSIX sh + awk).

# daten: the folder holding the sample year's CSVs (07_Daten, or Beispiel/07_Daten in sample mode).
daten() {
  for _o in 07_Daten Beispiel/07_Daten; do
    for _f in "$_o"/installed_base_*.csv; do
      if [ -f "$_f" ]; then echo "$_o"; return 0; fi
    done
  done
  echo "Vertrieb-Scaffold: keine installed_base-CSV gefunden – liefert 'baue jahr' den Datenbestand?" >&2
  return 1
}

# _endet_mit_zeilenumbruch <datei>: adds a final newline if the file lacks one.
_endet_mit_zeilenumbruch() {
  if [ -n "$(tail -c 1 "$1")" ]; then printf '\n' >> "$1"; fi
}

# zeile_anhaengen <csv> <Spalte=Wert>...: appends one row by column name; unnamed columns stay empty.
# Values must not contain ',', '|' or '"'.
zeile_anhaengen() {
  _d=$1; shift
  _endet_mit_zeilenumbruch "$_d"
  _p=$(printf '%s|' "$@")
  awk -v paare="$_p" 'NR == 1 {
    sub("^\357\273\277", ""); sub("\r$", "")
    n = split($0, kopf, ",")
    m = split(paare, p, "|")
    for (i = 1; i <= m; i++) if (p[i] != "") { j = index(p[i], "="); w[substr(p[i], 1, j - 1)] = substr(p[i], j + 1) }
    z = ""
    for (i = 1; i <= n; i++) { k = kopf[i]; gsub(/"/, "", k); z = z (i > 1 ? "," : "") w[k] }
    print z
    exit
  }' "$_d" >> "$_d"
}

# widerspruch_anhaengen <csv>: copies the first row with Vertrag=ja and gives the copy another Vertragsende
# (2026-12-31, or 2026-11-30 if it already ends then): one machine, two contract ends.
widerspruch_anhaengen() {
  _d=$1
  _endet_mit_zeilenumbruch "$_d"
  awk 'NR == 1 {
    sub("^\357\273\277", ""); sub("\r$", "")
    n = split($0, kopf, ",")
    for (i = 1; i <= n; i++) { k = kopf[i]; gsub(/"/, "", k); spalte[k] = i }
    next
  }
  {
    sub("\r$", "")
    split($0, f, ",")
    if (f[spalte["Vertrag"]] == "ja") {
      f[spalte["Vertragsende"]] = (f[spalte["Vertragsende"]] == "2026-12-31") ? "2026-11-30" : "2026-12-31"
      z = ""
      for (i = 1; i <= n; i++) z = z (i > 1 ? "," : "") f[i]
      print z
      exit
    }
  }' "$_d" >> "$_d"
}

# grenzen_setzen <angebot_eur> <rabatt_prozent>: approval limits as front matter (D9) in every Unternehmen/ copy.
grenzen_setzen() {
  for _u in Unternehmen Beispiel/Unternehmen; do
    if [ -d "$_u" ]; then
      printf -- '---\nangebot_eur: %s\nrabatt_prozent: %s\nkulanz_eur: 2000\n---\n\n# Freigabegrenzen\n' "$1" "$2" \
        > "$_u/freigabegrenzen.md"
    fi
  done
}

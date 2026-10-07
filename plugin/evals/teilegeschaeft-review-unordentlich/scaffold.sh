#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr
D=07_Daten
[ -f "$D/ersatzteile_2026-09.csv" ] || D=Beispiel/07_Daten
rm "$D/ersatzteile_2026-03.csv"
# P&L parts revenue for June +5000 EUR: a second source that contradicts the parts export.
# CONVFMT/OFMT keep the cents (awk's default %.6g would round 173865.9 to 173866).
awk -F, -v OFS=, -v CONVFMT=%.2f -v OFMT=%.2f 'index($2, "Ersatzteile") { $4 = $4 + 5000 } { print }' \
  "$D/ergebnis_2026-06.csv" > "$D/ergebnis.neu"
mv "$D/ergebnis.neu" "$D/ergebnis_2026-06.csv"
grep -q Ersatzteile "$D/ergebnis_2026-06.csv" || { echo "Scaffold: keine Ersatzteile-Zeile in ergebnis_2026-06.csv" >&2; exit 1; }

#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr
D=07_Daten; [ -f "$D/ergebnis_2026-09.csv" ] || D=Beispiel/07_Daten
LC_ALL=C awk -F',' -v OFS=',' '
  NR == 1 { for (i = 1; i <= NF; i++) { h = $i; sub(/^[^A-Za-z_]+/, "", h); c[h] = i } print; next }
  NR == 4 || NR == 8 { $c["Kosten_EUR"] = "" }
  { print }
' "$D/auftraege_2026-09.csv" > "$D/auftraege.neu" && mv "$D/auftraege.neu" "$D/auftraege_2026-09.csv"

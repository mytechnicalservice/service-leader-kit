#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr
D=07_Daten; [ -f "$D/ergebnis_2026-09.csv" ] || D=Beispiel/07_Daten
# Controlling's own September P&L: German formats, ';', first revenue line +12.000 (spec §10 conflicting sources).
LC_ALL=C awk -F',' '
  function de(x,   neg, s, g, out) {
    neg = x < 0; if (neg) x = -x
    s = sprintf("%.2f", x); g = substr(s, 1, length(s) - 3); out = ""
    while (length(g) > 3) { out = "." substr(g, length(g) - 2) out; g = substr(g, 1, length(g) - 3) }
    return (neg ? "-" : "") g out "," substr(s, length(s) - 1)
  }
  function n(v) { if (substr(v, 1, 1) == "\047") v = substr(v, 2); return v + 0 }
  NR == 1 { for (i = 1; i <= NF; i++) { h = $i; sub(/^[^A-Za-z_]+/, "", h); c[h] = i }
            print "Monat;Position;Plan;Ist"; next }
  { ist = n($c["Ist_EUR"]); if (!fertig && index($c["Position"], "Umsatz") == 1) { ist += 12000; fertig = 1 }
    printf "09.2026;%s;%s;%s\n", $c["Position"], de(n($c["Plan_EUR"])), de(ist) }
' "$D/ergebnis_2026-09.csv" > 00_Eingang/ergebnis_2026-09_controlling.csv

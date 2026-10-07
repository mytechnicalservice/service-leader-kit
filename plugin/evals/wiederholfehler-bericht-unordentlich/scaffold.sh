#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue unordentlich
cp -R "$SLK_P/evals/_qualitaet_recht/arbeitsordner/." .
vorgaenge V-0001
for f in 07_Daten/auftraege_*.csv; do cut -d, -f1-11,13- "$f" > "$f.neu"; mv "$f.neu" "$f"; done
grep -v '^Schreiner' 07_Daten/installed_base_2026-09.csv > 07_Daten/ib.neu
mv 07_Daten/ib.neu 07_Daten/installed_base_2026-09.csv

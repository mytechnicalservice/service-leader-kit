#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr
D=07_Daten; [ -f "$D/ergebnis_2026-09.csv" ] || D=Beispiel/07_Daten
rm "$D/ergebnis_2026-03.csv"

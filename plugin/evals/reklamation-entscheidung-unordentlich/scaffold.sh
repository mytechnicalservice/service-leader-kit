#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue unordentlich
cp -R "$SLK_P/evals/_qualitaet_recht/arbeitsordner/." .
cp "$SLK_P/evals/_qualitaet_recht/dateien/2026-09-30_mail-nachtrag-mueller.eml" 00_Eingang/
vorgaenge V-0001
sed 's/^kulanz_eur: .*/kulanz_eur: null/' Unternehmen/freigabegrenzen.md > Unternehmen/f.neu
mv Unternehmen/f.neu Unternehmen/freigabegrenzen.md

#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue sauber
cp -R "$SLK_P/evals/_qualitaet_recht/arbeitsordner/." .
vorgaenge V-0001
sed 's/^kulanz_eur: .*/kulanz_eur: 300/' Unternehmen/freigabegrenzen.md > Unternehmen/f.neu
mv Unternehmen/f.neu Unternehmen/freigabegrenzen.md

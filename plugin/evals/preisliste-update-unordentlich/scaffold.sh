#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue unordentlich
cp "$SLK_P/evals/_angebot/preisliste_2026_unordentlich.xlsx" 04_Angebote/preisliste_2026.xlsx
# An earlier draft for 2027 already exists: it must stay untouched.
cp "$SLK_P/evals/_angebot/preisliste_2026_sauber.xlsx" 04_Angebote/preisliste_2027.xlsx

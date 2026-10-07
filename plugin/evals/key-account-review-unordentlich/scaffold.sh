#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
. "$(dirname "$0")/../_vertrieb/daten.sh"
baue jahr
D=$(daten)
rm "$D/auftraege_2026-03.csv"

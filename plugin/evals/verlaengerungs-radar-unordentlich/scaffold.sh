#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
. "$(dirname "$0")/../_vertrieb/daten.sh"
baue jahr
D=$(daten)
IB=$(ls "$D"/installed_base_*.csv | tail -n 1)
zeile_anhaengen "$IB" "Kunde=Nordmetall GmbH" "Anlage=Anlage 20" "Maschinentyp=MM-400" "Baujahr=2019" "Vertrag=ja"
widerspruch_anhaengen "$IB"

#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
. "$(dirname "$0")/../_gemeinsam/projekte.sh"
baue sauber
projekte "Retrofit Linie 2 Hansa Pack"
aendere "05_Projekte/Retrofit Linie 2 Hansa Pack/projekt.md" 's/"prognose": "2026-11-05"/"prognose": null/'

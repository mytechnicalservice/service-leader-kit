#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr-unordentlich
vorgaenge V-0002 V-0003
cp "$SLK_P/beispiel/00_Eingang/auftraege_2026-09.xlsx" 00_Eingang/
printf '\357\273\277tagesstart=2026-10-01\r\nwochenstart=2026-10-05\r\nmonatsabschluss=2026-08\r\nmonatsabschluss=2026-09\r\nquartal=2026-Q4\r\n' > Unternehmen/.kit-status

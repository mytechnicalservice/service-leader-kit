#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue jahr
grep -q '^angebot_eur:' Unternehmen/freigabegrenzen.md || { echo "Scaffold: angebot_eur fehlt" >&2; exit 1; }
# The sample sets einkauf_eur (Contract gap G3, applied in Plan 3), which teile.py reads before angebot_eur: set both.
awk '/^angebot_eur:/ { print "angebot_eur: 10000"; next } /^einkauf_eur:/ { print "einkauf_eur: 10000"; next } { print }' \
  Unternehmen/freigabegrenzen.md > fg.neu
mv fg.neu Unternehmen/freigabegrenzen.md
cat > 00_Eingang/2026-09-30_angebot_kugeltec.eml <<'EOF'
From: Vertrieb Kugeltec <vertrieb@kugeltec.example>
Subject: Angebot A-2026-118 Spindellager
Content-Type: text/plain; charset=utf-8

Guten Tag, wie besprochen unser Angebot.
Angebotsnr: A-2026-118
Lieferant: Kugeltec GmbH
Gegenstand: Spindellager-Satz MM-600
Menge: 40
Preis_EUR: 18.400,00
Lieferzeit_Tage: 15
Gueltig_bis: 2027-12-31
Gewaehrleistung_Monate: 12
Bestandslieferant: ja
EOF
cat > 00_Eingang/2026-10-01_angebot_lagerwerk.eml <<'EOF'
From: Lagerwerk Ost <angebote@lagerwerk.example>
Subject: Angebot Spindellager
Content-Type: text/plain; charset=utf-8

Lieferant: Lagerwerk Ost s.r.o.
Gegenstand: Spindellager-Satz MM-600
Menge: 40
Preis_EUR: 15.950,00
Lieferzeit_Tage: 30
Gueltig_bis: 2027-12-31
Gewaehrleistung_Monate: 6
Bestandslieferant: nein
Bemerkung: Lieferung frei Haus.
EOF

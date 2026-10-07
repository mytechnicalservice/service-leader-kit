#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
. "$(dirname "$0")/../_assistenz/faelle.sh"
baue sauber
vorgaenge V-0001 V-0002
grundbestand
mkdir -p "06_Kunden/Hansa Pack AG"
printf '# Wartungsvertrag Hansa Pack AG\n\nPremium, Reaktionszeit 24 h, Laufzeit bis 2027-12-31.\n' > "06_Kunden/Hansa Pack AG/vertrag.md"

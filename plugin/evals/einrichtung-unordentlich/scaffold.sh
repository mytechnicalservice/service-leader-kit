#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue unordentlich
printf '# Profil\n\nEigener Firmentext: Muster Maschinenbau, 420 Mitarbeitende.\n' > Unternehmen/profil.md
# Saved by Notepad: BOM, CRLF and a comment. Still valid.
{ printf '\357\273\277# von Hand geändert\r\n'; awk '{ printf "%s\r\n", $0 }' Unternehmen/.kit-config; } > Unternehmen/.kit-config.neu
mv Unternehmen/.kit-config.neu Unternehmen/.kit-config

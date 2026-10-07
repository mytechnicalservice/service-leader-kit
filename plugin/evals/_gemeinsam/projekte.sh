# Project fixtures for the projekte lane (POSIX sh, sourced after arbeitsordner.sh, which sets SLK_G).
# projekte <Name>…: copies _gemeinsam/projekte/<Name>/projekt.md into 05_Projekte/<Name>/
projekte() {
  for _p in "$@"; do mkdir -p "05_Projekte/$_p"; cp "$SLK_G/projekte/$_p/projekt.md" "05_Projekte/$_p/"; done
}
# aendere <Datei> <sed-Ausdruck>: edits a copied fixture (portable: no sed -i)
aendere() { sed "$2" "$1" > "$1.neu"; mv "$1.neu" "$1"; }
# windows <Datei>: saves the file the way Notepad does (BOM + CRLF)
windows() { { printf '\357\273\277'; awk '{ printf "%s\r\n", $0 }' "$1"; } > "$1.neu"; mv "$1.neu" "$1"; }

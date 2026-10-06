# Shared eval scaffold (sourced, POSIX sh). Builds a set-up kit workspace in the current, empty run workspace.
# The case's scaffold.sh is plugin/evals/<case>/scaffold.sh, so the plugin is two folders above it.
set -eu
SLK_P=$(cd "$(dirname "$0")/../.." && pwd)
SLK_G="$SLK_P/evals/_gemeinsam"
if [ ! -f "$SLK_P/.claude-plugin/plugin.json" ]; then
  echo "Scaffold: Plugin nicht gefunden über \$0=$0 – der Runner startet das Skript nicht aus dem Fall-Ordner." >&2
  exit 1
fi

# baue leer|sauber|unordentlich: tree + settings (+ the dataset's inbox files)
baue() {
  cp -R "$SLK_P/vorlagen/arbeitsordner/." .
  mkdir -p 01_Vorgaenge/offen 01_Vorgaenge/erledigt 01_Vorgaenge/_zur-loeschung
  cp "$SLK_P/vorlagen/workspace.gitignore" .gitignore
  printf 'schema=1\nablage=lokal\ngit_auto=nein\nlaufzeit=claude-code\nbeispieldaten=nein\nmail=postausgang\nsprache=de\nwochenstart=mo\nmonatsstart=erster-werktag\n' \
    > Unternehmen/.kit-config
  sed -n 's/.*"version"[^"]*"\([^"]*\)".*/\1/p' "$SLK_P/.claude-plugin/plugin.json" > Unternehmen/.kit-version
  # Every routine counts as done today, so session start announces nothing the eval does not test.
  _h=$(date +%Y-%m-%d); _m=$(date +%m); _m=${_m#0}
  printf 'tagesstart=%s\nwochenstart=%s\nmonatsabschluss=%s\nquartal=%s-Q%s\n' "$_h" "$_h" "$(date +%Y-%m)" \
    "$(date +%Y)" "$(((_m - 1) / 3 + 1))" > Unternehmen/.kit-status
  case "$1" in
    sauber) cp "$SLK_P/beispiel/00_Eingang/"* 00_Eingang/ ;;
    unordentlich) cp "$SLK_P/beispiel-unordentlich/00_Eingang/"* 00_Eingang/ ;;
    leer) ;;
    *) echo "baue: unbekannt: $1" >&2; exit 1 ;;
  esac
}

# vorgaenge V-0001 …: copies fixture cases into 01_Vorgaenge/offen/
vorgaenge() {
  for _nr in "$@"; do cp "$SLK_G/vorgaenge/$_nr.md" 01_Vorgaenge/offen/; done
}

# setze <key> <value>: replaces one setting (no validation: messy cases may set invalid values on purpose)
setze() {
  awk -v k="$1" -v v="$2" 'index($0, k "=") == 1 { print k "=" v; next } { print }' Unternehmen/.kit-config \
    > Unternehmen/.kit-config.neu
  mv Unternehmen/.kit-config.neu Unternehmen/.kit-config
}

# kit_version <x.y.z>: pretends the workspace was set up by another kit version
kit_version() { printf '%s\n' "$1" > Unternehmen/.kit-version; }

# Shared eval scaffold (sourced, POSIX sh). Builds a set-up kit workspace in the current, empty run workspace.
# The case's scaffold.sh is plugin/evals/<case>/scaffold.sh, so the plugin is two folders above it.
set -eu
SLK_P=$(cd "$(dirname "$0")/../.." && pwd)
SLK_G="$SLK_P/evals/_gemeinsam"
# Wheels for offline `uv run` (eval runs have no network and an empty uv cache). Built per machine with
# tools/eval_wheels.sh; SLK_WHEELS is only for the kit's unit tests (the runner passes no such variable).
SLK_WHEELS=${SLK_WHEELS:-$SLK_G/wheels}
if [ ! -f "$SLK_P/.claude-plugin/plugin.json" ]; then
  echo "Scaffold: Plugin nicht gefunden über \$0=$0 – der Runner startet das Skript nicht aus dem Fall-Ordner." >&2
  exit 1
fi

# baue leer|sauber|unordentlich|jahr|jahr-unordentlich: tree + settings (+ the dataset's files).
# jahr = the onboarded sample company as the user's own workspace (Plan 3, D14): 07_Daten/ (twelve months, budget,
# qualification), filled Unternehmen/ incl. vorlagen/, 04_Angebote/, 05_Projekte/, 06_Kunden/ and the mails (no
# September exports: they are already in 07_Daten/). jahr-unordentlich adds the messy inbox documents: injection
# mail, scanned offer (instead of the Hydraulik Nord mail) and the controlling report that contradicts 07_Daten/.
baue() {
  if ! ls "$SLK_WHEELS"/*.whl >/dev/null 2>&1; then
    echo "Scaffold: Wheel-Ordner fehlt oder ist leer: $SLK_WHEELS – ohne ihn kann uv run im Eval-Lauf keine" \
      "Bibliotheken laden. Vor dem Eval-Lauf im Kit-Repo bauen: sh tools/eval_wheels.sh" >&2
    exit 1
  fi
  # uv reads uv.toml from the working directory: install only from the wheel folder, never from the index.
  printf 'no-index = true\nfind-links = ["%s"]\n' "$SLK_WHEELS" > uv.toml
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
    jahr|jahr-unordentlich)
      for _d in 04_Angebote 05_Projekte 06_Kunden 07_Daten Unternehmen; do cp -R "$SLK_P/beispiel/$_d/." "$_d/"; done
      cp "$SLK_P/beispiel/00_Eingang/"*.eml 00_Eingang/
      if [ "$1" = jahr-unordentlich ]; then
        rm -f 00_Eingang/2026-09-24_angebot-hydraulik-nord.eml
        for _f in 2026-09-29_mail-preisanfrage.eml 2026-09-30_angebot-hydraulik-nord-scan.pdf \
                  Controlling_Monatsbericht_2026-09.xlsx; do
          cp "$SLK_P/beispiel-unordentlich/00_Eingang/$_f" 00_Eingang/
        done
      fi ;;
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

# routine_status <routine> [<wert>]: removes the routine's line from Unternehmen/.kit-status (= not run yet) or sets
# it to <wert> (e.g. monatsabschluss 2026-09), so that a routine eval starts with that routine due (Plan 5).
routine_status() {
  awk -v k="$1" 'index($0, k "=") != 1' Unternehmen/.kit-status > Unternehmen/.kit-status.neu
  if [ -n "${2:-}" ]; then printf '%s=%s\n' "$1" "$2" >> Unternehmen/.kit-status.neu; fi
  mv Unternehmen/.kit-status.neu Unternehmen/.kit-status
}

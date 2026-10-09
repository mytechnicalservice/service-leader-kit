# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Developer tool: builds the "Eigene Kopie" of the kit from plugin/ (plugin/scripts/eigene_kopie.py does the work).

  uv run tools/build-standalone.py "<Projektordner>"   # writes <Projektordner>/.claude/ (refuses existing files)
  uv run tools/build-standalone.py --zip [<Zielordner>]  # service-leader-kit-eigene-kopie-<version>.zip

The zip holds exactly the .claude/ folder; the user unpacks it into the Kundendienst folder. Not shipped to users."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
sys.path.insert(0, str(PLUGIN / "scripts"))

import arbeitsordner as ao  # noqa: E402
import eigene_kopie  # noqa: E402


def zip_name(version: str, ziel: str = "eigene-kopie") -> str:
    return f"service-leader-kit-{ziel}-{version}.zip"


def baue_zip(zielordner: Path, plugin: Path = PLUGIN, ziel: str = "eigene-kopie") -> Path:
    zip_pfad = zielordner / zip_name(ao.kit_version(plugin), ziel)
    with tempfile.TemporaryDirectory() as tmp:
        projekt = Path(tmp)
        eigene_kopie.baue(plugin, projekt, ziel=ziel)
        roots = [projekt / "AGENTS.md", projekt / ".agents", projekt / ".codex"] if ziel == "codex" else [projekt / ".claude"]
        files = sorted(p for root in roots for p in ([root] if root.is_file() else root.rglob("*")) if p.is_file())
        with zipfile.ZipFile(zip_pfad, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                if p.is_file():
                    info = zipfile.ZipInfo.from_file(p, p.relative_to(projekt).as_posix())
                    info.date_time = (2026, 1, 1, 0, 0, 0)  # reproducible: same plugin, same zip
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, p.read_bytes())
    return zip_pfad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build-standalone", description=__doc__.split("\n\n")[0])
    ap.add_argument("ordner", nargs="?", help="Projektordner (ohne --zip) bzw. Ordner für die ZIP-Datei")
    ap.add_argument("--ziel", choices=("eigene-kopie", "codex"), default="eigene-kopie")
    ap.add_argument("--zip", action="store_true", help="ZIP-Datei für das GitHub-Release bauen")
    ap.add_argument("--pruefen", action="store_true", help="Nur prüfen, nichts schreiben")
    ap.add_argument("--aktualisieren", action="store_true", help="Unveränderte Kit-Dateien anhand der Dateiliste aktualisieren")
    ap.add_argument("--ueberschreiben", action="store_true", help="Eigene Änderungen nach ausdrücklicher Zustimmung ersetzen")
    a = ap.parse_args(argv)
    if a.zip:
        if a.pruefen or a.aktualisieren or a.ueberschreiben:
            ap.error("ZIP-Bau kann nicht mit Installations- oder Prüfflags kombiniert werden")
        print(baue_zip(Path(a.ordner or ".").resolve(), ziel=a.ziel))
        return 0
    if not a.ordner:
        ap.error("Projektordner fehlt")
    projekt = Path(a.ordner).resolve()
    try:
        if a.pruefen:
            if a.ziel == "codex":
                import codex_install
                erg = codex_install.pruefen(PLUGIN, projekt, a.aktualisieren)
            else:
                erg = {"konflikte": eigene_kopie.konflikte(PLUGIN, projekt), "settings": eigene_kopie.lies_settings(projekt)[1]}
            print(json.dumps(erg, ensure_ascii=False, indent=2))
            return 0
        projekt.mkdir(parents=True, exist_ok=True)
        erg = eigene_kopie.baue(PLUGIN, projekt, a.ueberschreiben, a.ziel, a.aktualisieren)
    except FileExistsError as exc:
        print(f"Abbruch, schon vorhanden: {', '.join(exc.args[0][:10])}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Abbruch: {exc}", file=sys.stderr)
        return 1
    variante = "Codex-Version" if a.ziel == "codex" else "Eigene Kopie"
    print(f"{variante} {erg['version']}: {erg['dateien']} Dateien in {projekt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

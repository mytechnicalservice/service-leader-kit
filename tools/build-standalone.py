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
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
sys.path.insert(0, str(PLUGIN / "scripts"))

import arbeitsordner as ao  # noqa: E402
import eigene_kopie  # noqa: E402


def zip_name(version: str) -> str:
    return f"service-leader-kit-eigene-kopie-{version}.zip"


def baue_zip(zielordner: Path, plugin: Path = PLUGIN) -> Path:
    ziel = zielordner / zip_name(ao.kit_version(plugin))
    with tempfile.TemporaryDirectory() as tmp:
        projekt = Path(tmp)
        eigene_kopie.baue(plugin, projekt)
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted((projekt / ".claude").rglob("*")):
                if p.is_file():
                    info = zipfile.ZipInfo.from_file(p, p.relative_to(projekt).as_posix())
                    info.date_time = (2026, 1, 1, 0, 0, 0)  # reproducible: same plugin, same zip
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, p.read_bytes())
    return ziel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build-standalone", description=__doc__.split("\n\n")[0])
    ap.add_argument("ziel", nargs="?", help="Projektordner (ohne --zip) bzw. Ordner für die ZIP-Datei")
    ap.add_argument("--zip", action="store_true", help="ZIP-Datei für das GitHub-Release bauen")
    a = ap.parse_args(argv)
    if a.zip:
        print(baue_zip(Path(a.ziel or ".").resolve()))
        return 0
    if not a.ziel:
        ap.error("Projektordner fehlt")
    projekt = Path(a.ziel).resolve()
    projekt.mkdir(parents=True, exist_ok=True)
    try:
        erg = eigene_kopie.baue(PLUGIN, projekt)
    except FileExistsError as exc:
        print(f"Abbruch, schon vorhanden: {', '.join(exc.args[0][:10])}", file=sys.stderr)
        return 1
    print(f"Eigene Kopie {erg['version']}: {erg['dateien']} Dateien in {projekt / '.claude'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Developer tool: builds a kit workspace for tests and the enforcement test (Plan 2b).
Not shipped to users; `einrichtung` (Plan 2c) is the real setup."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "scripts"))

import arbeitsordner as ao  # noqa: E402
import vorgang  # noqa: E402

KONFIG = ("schema=1\nablage=lokal\ngit_auto=nein\nlaufzeit=claude-code\nbeispieldaten=nein\nmail=postausgang\n"
          "sprache=de\nwochenstart=mo\nmonatsstart=erster-werktag\n")
ORDNER = sorted({p.parent.relative_to(ao.VORLAGE).as_posix() for p in ao.VORLAGE.rglob("*.md")} | set(ao.LEERE_ORDNER))
VORGAENGE = [("Reklamation Spindelschaden", "Müller GmbH", "2026-09-01"),
             ("Angebot Retrofit Anlage 2", "Beispiel AG", None)]


def baue(ziel: Path, mit_vorgaengen: bool = True) -> None:
    if ziel.exists() and any(ziel.iterdir()):
        raise SystemExit(f"{ziel} ist nicht leer")
    ziel.mkdir(parents=True, exist_ok=True)
    ao.ergaenze(ziel)
    (ziel / "Unternehmen" / ".kit-config").write_text(KONFIG, encoding="utf-8")
    (ziel / "Unternehmen" / ".kit-version").write_text("0.1.0\n", encoding="utf-8")
    (ziel / "Unternehmen" / "profil.md").write_text("# Profil\n\nTestfirma für den Schutztest.\n", encoding="utf-8")
    if mit_vorgaengen:
        for titel, kunde, faellig in VORGAENGE:
            meta = {k: None for k in vorgang.FIELDS} | {
                "titel": titel, "typ": "reklamation", "status": "offen", "kunde": kunde,
                "verantwortlich": "Max Testmann", "bearbeitet_von": ["betrieb"], "faellig": faellig,
                "erstellt": "2026-09-30", "aktualisiert": "2026-09-30"}
            vorgang.anlegen(ziel, meta, vorgang.event("2026-09-30", "angelegt", "betrieb", "Testvorgang."))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: uv run tools/testworkspace.py <leerer Zielordner>")
    baue(Path(sys.argv[1]).expanduser())
    print(f"Arbeitsordner angelegt: {sys.argv[1]}")

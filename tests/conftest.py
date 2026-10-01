import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture
def ws(tmp_path):
    d = tmp_path / "Kundendienst Müller"
    d.mkdir()
    return d
SHELLS = [s for s in ("/bin/sh", shutil.which("dash")) if s]


@pytest.fixture(params=SHELLS, ids=lambda s: Path(s).name)
def shell(request):
    """Every POSIX shell on this machine: hooks must not depend on Bash features."""
    return request.param


KONFIG = ("schema=1\nablage=lokal\ngit_auto=nein\nlaufzeit=claude-code\nbeispieldaten=nein\nmail=postausgang\n"
          "sprache=de\nwochenstart=mo\nmonatsstart=erster-werktag\n")
ORDNER = ["00_Eingang", "01_Vorgaenge/offen", "01_Vorgaenge/erledigt", "01_Vorgaenge/_zur-loeschung",
          "02_Postausgang", "03_Berichte", "04_Angebote", "05_Projekte", "06_Kunden", "07_Daten",
          "Unternehmen/vorlagen"]


@pytest.fixture
def kit_ws(ws):
    """A set-up workspace (folders + valid .kit-config) at a path with a space and an umlaut."""
    for o in ORDNER:
        (ws / o).mkdir(parents=True, exist_ok=True)
    (ws / "Unternehmen" / ".kit-config").write_text(KONFIG, encoding="utf-8")
    return ws

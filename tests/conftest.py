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


from testworkspace import KONFIG, ORDNER, baue  # noqa: E402,F401  (tools/ is on sys.path above)


@pytest.fixture
def kit_ws(ws):
    """A set-up workspace (folders + valid .kit-config, no cases) at a path with a space and an umlaut."""
    baue(ws, mit_vorgaengen=False)
    return ws

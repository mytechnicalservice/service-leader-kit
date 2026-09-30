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

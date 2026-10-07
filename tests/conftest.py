import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

# Wheels for offline `uv run` in eval runs (built by tools/eval_wheels.sh, gitignored, platform-specific).
WHEELS = ROOT / "plugin" / "evals" / "_gemeinsam" / "wheels"


def wheels_da() -> bool:
    return any(WHEELS.glob("*.whl"))


def runner_env(home) -> dict:
    """The eval runner's scaffold environment (plugin-evals docs): PATH, a temporary HOME, TMPDIR, TERM=dumb.
    Unit tests only check the workspace the scaffold builds, never `uv run` in it (test_eval_uv_offline does), so
    when the real wheel folder is not built they point the scaffold at a folder with an empty placeholder wheel;
    SLK_WHEELS never reaches a real eval run."""
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
    if not wheels_da():
        ersatz = Path(tempfile.gettempdir()) / "slk-test-wheels"
        ersatz.mkdir(exist_ok=True)
        (ersatz / "platzhalter-0-py3-none-any.whl").touch()
        env["SLK_WHEELS"] = str(ersatz)
    return env


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

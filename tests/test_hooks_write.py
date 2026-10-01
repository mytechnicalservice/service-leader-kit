import pytest

from hookrun import echt, run_hook, write

ARCHITEKT = "service-leader-kit:system-architekt"


def pre(shell, ws, payload, proj=None):
    r = run_hook(shell, "pre-tool-use.sh", payload, proj or ws)
    return r.returncode, r.stderr.decode("utf-8")


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_case_files_are_never_written_directly(shell, kit_ws, tool):
    code, err = pre(shell, kit_ws, write(kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md", tool=tool))
    assert code == 2 and "Service Leader Kit – gesperrt:" in err and "vorgang.py" in err
    log = (kit_ws / "Unternehmen" / ".kit-protokoll").read_text(encoding="utf-8")
    assert f"\tBLOCK\twrite-vorgang tool={tool} agent=<none>" in log


def test_case_guard_applies_to_the_system_architect_too(shell, kit_ws):
    assert pre(shell, kit_ws, write(kit_ws / "01_Vorgaenge" / "x.md", agent=ARCHITEKT))[0] == 2


@pytest.mark.parametrize("variante", ["backslash", "kleinschreibung", "relativ"])
def test_case_guard_sees_windows_and_relative_paths(shell, kit_ws, variante):
    pfad = {"backslash": str(kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md").replace("/", "\\"),
            "kleinschreibung": str(kit_ws / "01_vorgaenge" / "offen" / "V-0001.md"),
            "relativ": "01_Vorgaenge/offen/V-0001.md"}[variante]
    p = write(pfad)
    p["cwd"] = str(kit_ws)
    assert pre(shell, kit_ws, p)[0] == 2


def test_real_write_payload_is_blocked_on_a_case_file(shell, kit_ws):
    p = echt("PreToolUse-Write.json", kit_ws)
    p["tool_input"]["file_path"] = str(kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md")
    assert pre(shell, kit_ws, p)[0] == 2


@pytest.mark.parametrize("agent,erwartet", [(None, 2), ("service-leader-kit:finanzen", 2), (ARCHITEKT, 0)])
def test_unternehmen_is_written_only_by_the_system_architect(shell, kit_ws, agent, erwartet):
    code, err = pre(shell, kit_ws, write(kit_ws / "Unternehmen" / "profil.md", agent=agent))
    assert code == erwartet
    if erwartet:
        assert "System-Architekt" in err


@pytest.mark.parametrize("ziel", ["03_Berichte/2026-10_Bericht.md", "02_Postausgang/entwurf.md", "neu.md"])
def test_other_folders_are_free(shell, kit_ws, ziel):
    assert pre(shell, kit_ws, write(kit_ws / ziel)) == (0, "")


def test_unternehmen_folders_outside_a_workspace_are_not_touched(shell, tmp_path, kit_ws):
    fremd = tmp_path / "Firma" / "Unternehmen"
    fremd.mkdir(parents=True)
    assert pre(shell, kit_ws, write(fremd / "x.md"))[0] == 0


def test_case_guard_holds_when_another_project_is_open(shell, tmp_path, kit_ws):
    anderes = tmp_path / "anderes Projekt"
    anderes.mkdir()
    assert pre(shell, kit_ws, write(kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md"), proj=anderes)[0] == 2


def test_read_and_unknown_tools_pass(shell, kit_ws):
    p = write(kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md", tool="Read")
    assert pre(shell, kit_ws, p) == (0, "")


def test_nested_workspace_inside_a_folder_named_unternehmen(shell, tmp_path, ws):
    from conftest import KONFIG, ORDNER
    w = tmp_path / "Unternehmen" / "Kundendienst"
    for o in ORDNER:
        (w / o).mkdir(parents=True)
    (w / "Unternehmen" / ".kit-config").write_text(KONFIG, encoding="utf-8")
    assert pre(shell, w, write(w / "Unternehmen" / "profil.md"))[0] == 2
    assert pre(shell, w, write(w / "Unternehmen" / "profil.md", agent=ARCHITEKT))[0] == 0
    assert pre(shell, w, write(w / "03_Berichte" / "b.md"))[0] == 0


def test_decoy_folder_before_the_real_workspace(shell, tmp_path, kit_ws):
    decoy = tmp_path / "01_Vorgaenge"
    decoy.mkdir()
    pfad = f"{decoy}/../{kit_ws.name}/01_Vorgaenge/offen/x.md"
    assert pre(shell, kit_ws, write(pfad))[0] == 2


@pytest.mark.parametrize("relativ", [False, True])
def test_dotdot_through_a_missing_folder(shell, kit_ws, relativ):
    p = write("nope/../01_Vorgaenge/x.md" if relativ else f"{kit_ws}/nope/../01_Vorgaenge/offen/V-0001.md")
    p["cwd"] = str(kit_ws)
    assert pre(shell, kit_ws, p)[0] == 2

import json

import pytest

import arbeitsordner as ao
import gesundheitscheck as g
import vorgang
from conftest import KONFIG
from hookrun import run_hook
from testworkspace import baue

HEUTE = "2026-10-06"


def check(capsys, ws, heute=HEUTE):
    code = g.main(["--ws", str(ws), "--heute", heute])
    return code, json.loads(capsys.readouterr().out)


def neu(capsys, ws, titel, heute):
    vorgang.main(["neu", "--ws", str(ws), "--heute", heute, "--titel", titel, "--typ", "aufgabe", "--kunde", "K",
                  "--verantwortlich", "Jana Becker", "--von", "betrieb", "--text", "x"])
    return json.loads(capsys.readouterr().out)["nr"]


def test_new_kit_version_is_recorded_and_missing_files_added(capsys, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    (kit_ws / "03_Berichte" / "LIESMICH.md").unlink()
    code, out = check(capsys, kit_ws)
    assert code == 0 and out["ok"]
    assert out["version"] == {"ordner": "0.0.9", "kit": ao.kit_version(), "aktualisiert": True}
    assert out["ergaenzt"] == ["03_Berichte/LIESMICH.md"]
    assert (kit_ws / "Unternehmen" / ".kit-version").read_text(encoding="utf-8") == ao.kit_version() + "\n"


def test_health_check_silences_the_session_start_notice(capsys, kit_ws, shell):
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    check(capsys, kit_ws)
    assert "Neue Kit-Version" not in run_hook(shell, "session-start.sh", {}, kit_ws).stdout.decode()


def test_truncated_case_is_reported_and_left_alone(capsys, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    nr = neu(capsys, kit_ws, "Spindel", HEUTE)
    p = kit_ws / "01_Vorgaenge" / "offen" / f"{nr}.md"
    p.write_text(p.read_text(encoding="utf-8")[:60], encoding="utf-8")  # cut mid-header
    vorher = p.read_bytes()
    code, out = check(capsys, kit_ws)
    assert code == 1 and out["defekt"][0]["datei"] == f"01_Vorgaenge/offen/{nr}.md"
    assert p.read_bytes() == vorher
    assert out["version"]["aktualisiert"] is True  # decision D6
    assert any(nr in m for m in out["meldungen"])


def test_invalid_settings_keep_the_old_version_and_the_file(capsys, kit_ws):
    p = kit_ws / "Unternehmen" / ".kit-config"
    p.write_text(KONFIG.replace("mail=postausgang", "mail=fax"), encoding="utf-8")
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    code, out = check(capsys, kit_ws)
    assert code == 1 and out["einstellungen"]["status"] == "ungueltig"
    assert "mail=fax" in p.read_text(encoding="utf-8")
    assert (kit_ws / "Unternehmen" / ".kit-version").read_text(encoding="utf-8") == "0.0.9\n"
    assert any("Einrichtung" in m for m in out["meldungen"])


def test_old_schema_is_migrated_with_a_backup(capsys, kit_ws, monkeypatch):
    monkeypatch.setattr(g, "MIGRATIONEN", {0: lambda w: {k: v for k, v in w.items() if k != "post"}
                                           | {"mail": w.get("post", "postausgang")}})
    alt = KONFIG.replace("schema=1", "schema=0").replace("mail=postausgang", "post=connector")
    (kit_ws / "Unternehmen" / ".kit-config").write_text(alt, encoding="utf-8")
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    code, out = check(capsys, kit_ws)
    assert code == 0 and out["einstellungen"]["status"] == "migriert"
    assert ao.lies_konfig(kit_ws) == (dict(z.split("=", 1) for z in KONFIG.replace(
        "mail=postausgang", "mail=connector").split()), [])
    assert (kit_ws / "Unternehmen" / ".kit-config.bak-0.0.9").read_text(encoding="utf-8") == alt


def test_settings_from_a_newer_kit_are_not_touched(capsys, kit_ws):
    p = kit_ws / "Unternehmen" / ".kit-config"
    p.write_text(KONFIG.replace("schema=1", "schema=2"), encoding="utf-8")
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    (kit_ws / "03_Berichte" / "LIESMICH.md").unlink()
    vorher = sorted(x.relative_to(kit_ws).as_posix() for x in kit_ws.rglob("*"))
    code, out = check(capsys, kit_ws)
    assert code == 1 and out["einstellungen"]["status"] == "ungueltig"
    assert any("neueren Kit-Version" in m for m in out["meldungen"])
    assert "schema=2" in p.read_text(encoding="utf-8")
    assert out["ergaenzt"] == [] and not (kit_ws / "03_Berichte" / "LIESMICH.md").exists()
    assert sorted(x.relative_to(kit_ws).as_posix() for x in kit_ws.rglob("*")) == vorher
    assert (kit_ws / "Unternehmen" / ".kit-version").read_text(encoding="utf-8") == "0.0.9\n"


def test_missing_settings(capsys, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-config").unlink()
    code, out = check(capsys, kit_ws)
    assert code == 1 and out["einstellungen"]["status"] == "fehlt"


def schliesse(capsys, ws, nr, heute):
    vorgang.main(["schliesse", "--ws", str(ws), "--nr", nr, "--heute", heute])
    capsys.readouterr()


def test_retention_waits_for_confirmation(capsys, kit_ws):
    nr = neu(capsys, kit_ws, "Alt", "2018-01-02")
    schliesse(capsys, kit_ws, nr, "2019-05-01")
    _, out = check(capsys, kit_ws)
    assert out["aufbewahrung"] == {"bestaetigt": False, "jahre": 6, "abgelaufen": []}
    assert any("nicht bestätigt" in m for m in out["meldungen"])


def test_retention_lists_cases_past_the_period_and_deletes_nothing(capsys, kit_ws):
    alt = neu(capsys, kit_ws, "Alt", "2018-01-02")
    schliesse(capsys, kit_ws, alt, "2019-05-01")
    jung = neu(capsys, kit_ws, "Jung", "2024-01-02")
    schliesse(capsys, kit_ws, jung, "2024-03-01")
    a = kit_ws / "Unternehmen" / "aufbewahrung.md"
    a.write_text(a.read_text(encoding="utf-8").replace("bestaetigt: nein", "bestaetigt: ja"), encoding="utf-8")
    code, out = check(capsys, kit_ws)
    assert out["aufbewahrung"]["abgelaufen"] == [{"nr": alt, "abgeschlossen": "2019-05-01"}]
    assert (kit_ws / "01_Vorgaenge" / "erledigt" / f"{alt}.md").is_file()
    assert code == 0  # a proposal is not an error


@pytest.mark.parametrize("kopf", ["---\nvorgaenge_jahre: viele\nbestaetigt: ja\n---\n", "# ohne Kopf\n",
                                  "---\nvorgaenge_jahre: 0\nbestaetigt: ja\n---\n"])
def test_unreadable_retention_file_is_named(capsys, kit_ws, kopf):
    (kit_ws / "Unternehmen" / "aufbewahrung.md").write_text(kopf, encoding="utf-8")
    _, out = check(capsys, kit_ws)
    assert out["aufbewahrung"]["bestaetigt"] is False
    assert any("aufbewahrung.md" in m for m in out["meldungen"])


def test_not_a_workspace(capsys, ws):
    code, out = check(capsys, ws)
    assert code == 1 and "richte den Kundendienst ein" in out["meldungen"][0]


def test_a_bare_unternehmen_folder_is_not_a_workspace(capsys, ws):
    (ws / "Unternehmen").mkdir()
    code, out = check(capsys, ws)
    assert code == 1 and "richte den Kundendienst ein" in out["meldungen"][0]
    assert [p.relative_to(ws).as_posix() for p in ws.rglob("*")] == ["Unternehmen"]


@pytest.mark.parametrize("ordner", ["9.0.0", "0.10.0", "0.1.1"])
def test_a_newer_folder_version_is_never_lowered(capsys, kit_ws, ordner):
    v = kit_ws / "Unternehmen" / ".kit-version"
    v.write_text(ordner + "\n", encoding="utf-8")
    code, out = check(capsys, kit_ws)
    assert code == 0 and out["version"] == {"ordner": ordner, "kit": ao.kit_version(), "aktualisiert": False}
    assert v.read_text(encoding="utf-8") == ordner + "\n"
    assert any("neueren Kit-Version" in m and ordner in m for m in out["meldungen"])


def test_same_folder_version_is_quiet(capsys, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-version").write_text(ao.kit_version() + "\n", encoding="utf-8")
    code, out = check(capsys, kit_ws)
    assert code == 0 and out["version"]["aktualisiert"] is False
    assert not any("Kit-Version" in m for m in out["meldungen"])


def test_retention_front_matter_with_a_bom_is_read(capsys, kit_ws):
    a = kit_ws / "Unternehmen" / "aufbewahrung.md"
    a.write_text("\ufeff" + a.read_text(encoding="utf-8").replace("bestaetigt: nein", "bestaetigt: ja"),
                 encoding="utf-8")
    _, out = check(capsys, kit_ws)
    assert out["aufbewahrung"]["bestaetigt"] is True and out["aufbewahrung"]["jahre"] == 6

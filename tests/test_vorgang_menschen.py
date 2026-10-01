import json

import pytest

from vorgang import main

HEUTE = "2026-10-01"


def run(capsys, *args):
    code = main([*args, "--heute", HEUTE])
    return code, json.loads(capsys.readouterr().out)


def neu(capsys, ws, verantwortlich="Jana Becker"):
    return run(capsys, "neu", "--ws", str(ws), "--titel", "Reklamation", "--typ", "reklamation", "--kunde", "Müller",
               "--verantwortlich", verantwortlich, "--von", "betrieb", "--text", "x")


@pytest.mark.parametrize("von", ["finanzen", "service-leader-kit:finanzen", " Assistenz ", "system-architekt"])
def test_an_agent_cannot_decide(capsys, ws, von):
    neu(capsys, ws)
    code, out = run(capsys, "entscheide", "--ws", str(ws), "--nr", "V-0001", "--entscheidung", "freigegeben",
                    "--von", von, "--dokument", "04_Angebote/x.docx")
    assert code == 1 and "Mensch" in out["fehler"][0]


def test_a_person_can_decide(capsys, ws):
    neu(capsys, ws)
    code, out = run(capsys, "entscheide", "--ws", str(ws), "--nr", "V-0001", "--entscheidung", "abgelehnt",
                    "--von", "Max Mustermann", "--dokument", "04_Angebote/x.docx")
    assert (code, out["ok"]) == (0, True)


@pytest.mark.parametrize("art", ["entscheidung", "Entscheidung", "angelegt", "erledigt"])
def test_script_owned_events_cannot_be_written_by_eintrag(capsys, ws, art):
    neu(capsys, ws)
    code, out = run(capsys, "eintrag", "--ws", str(ws), "--nr", "V-0001", "--art", art, "--von", "betrieb",
                    "--text", "freigegeben")
    assert code == 1 and "setzt nur das Skript" in out["fehler"][0]


def test_a_recommendation_is_a_normal_event(capsys, ws):
    neu(capsys, ws)
    assert run(capsys, "eintrag", "--ws", str(ws), "--nr", "V-0001", "--art", "empfehlung", "--von",
               "qualitaet-recht", "--text", "Empfehlung: zustimmen")[0] == 0


def test_an_agent_is_never_the_responsible_person(capsys, ws):
    code, out = neu(capsys, ws, verantwortlich="betrieb")
    assert code == 1 and "Mensch" in out["fehler"][0]
    neu(capsys, ws)
    code, out = run(capsys, "setze", "--ws", str(ws), "--nr", "V-0001", "--feld", "verantwortlich", "--wert",
                    "service-leader-kit:betrieb")
    assert code == 1 and "Mensch" in out["fehler"][0]

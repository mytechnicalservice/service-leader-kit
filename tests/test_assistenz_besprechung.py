import vorgang
from assistenz_hilfe import H, eintrag, lies, neu, ruf


def test_prep_for_a_customer(kit_ws):
    ordner = kit_ws / "06_Kunden" / "Hansa Pack AG"
    ordner.mkdir()
    (ordner / "vertrag.md").write_text("Premium-Wartungsvertrag, Reaktionszeit 24 h.\n", encoding="utf-8")
    esk = neu(kit_ws, "Stillstand Linie 2", "eskalation", "Hansa Pack AG", faellig="2026-10-08")
    rf = neu(kit_ws, "Retrofit Linie 2", "freigabe", "Hansa Pack AG", betrag=12500)
    eintrag(kit_ws, rf, "empfehlung", "Empfehlung: zustimmen mit Auflagen – Marge 31 %.")
    fremd = neu(kit_ws, "Reklamation Spindel", "reklamation", "Müller GmbH")
    code, out = ruf(kit_ws, "besprechung-vorbereiten", "--kunde", "hansa pack ag",
                    "--punkt", "Ursache Stillstand klären")
    assert code == 0, out
    assert out["datei"] == f"06_Kunden/Hansa Pack AG/{H}_besprechung-vorbereitung.md"
    assert out["vorgaenge"] == [esk, rf] and out["vertrag"] == "06_Kunden/Hansa Pack AG/vertrag.md"
    text = lies(kit_ws, out)
    assert "12.500 €" in text and fremd not in text and "- Ursache Stillstand klären" in text
    assert "Empfehlung zustimmen mit Auflagen (finanzen) – noch nicht entschieden" in text


def test_prep_reuses_the_existing_folder_spelling_and_needs_a_subject(kit_ws):
    (kit_ws / "06_Kunden" / "Mueller GmbH").mkdir()
    code, out = ruf(kit_ws, "besprechung-vorbereiten", "--kunde", "Müller GmbH")
    assert out["datei"].startswith("06_Kunden/Mueller GmbH/")
    code, out = ruf(kit_ws, "besprechung-vorbereiten")
    assert code == 1 and "--kunde oder --thema" in out["fehler"][0]
    code, out = ruf(kit_ws, "besprechung-vorbereiten", "--kunde", "../Unternehmen")
    assert code == 1
    code, out = ruf(kit_ws, "besprechung-vorbereiten", "--thema", "Teamleiterrunde Oktober")
    assert out["datei"] == f"03_Berichte/{H}_besprechung-vorbereitung.md"


def test_minutes_turn_actions_into_case_proposals(kit_ws):
    (kit_ws / "06_Kunden" / "Hansa Pack AG").mkdir()
    code, out = ruf(kit_ws, "besprechung-protokoll", "--titel", "Telefonat Dr. Lang", "--datum", H,
                    "--kunde", "Hansa Pack AG", "--teilnehmer", "Dr. Petra Lang", "--teilnehmer", "Max Mustermann",
                    "--punkt", "Linie 2 läuft wieder seit 6 Uhr",
                    "--beschluss", "Ersatzteilpaket Spindel wird vorgehalten",
                    "--massnahme", "Ursachenbericht an Kunden | Jana Becker | 2026-10-14",
                    "--massnahme", "Angebot Ersatzteilpaket | | 2026-10-16",
                    "--massnahme", "Vertragsprüfung Reaktionszeit | betrieb | 2026-10-20",
                    "--massnahme", "Schulung Bediener | Jana Becker | 16.10.")
    assert code == 0, out
    assert out["datei"] == f"06_Kunden/Hansa Pack AG/{H}_protokoll.md" and out["fehlend"] == [2, 3, 4]
    m = out["massnahmen"]
    assert m[0]["bereit"] and "Verantwortlich fehlt" in m[1]["fehlt"][0]
    assert "ist ein Agent" in m[2]["fehlt"][0] and "kein Datum" in m[3]["fehlt"][0]
    text = lies(kit_ws, out)
    assert "| 1 | Ursachenbericht an Kunden | Jana Becker | 14.10.2026 | wird Vorgang |" in text
    assert "- Teilnehmer: Dr. Petra Lang, Max Mustermann" in text
    v = m[0]["vorgang_neu"]
    code, fall = vorgang._main(["neu", "--ws", str(kit_ws), "--titel", v["titel"], "--typ", v["typ"],
                                "--kunde", v["kunde"], "--verantwortlich", v["verantwortlich"],
                                "--faellig", v["faellig"], "--von", v["von"], "--text", v["text"]])
    assert code == 0, fall
    assert f"Quelle: 06_Kunden/Hansa Pack AG/{H}_protokoll.md" in (kit_ws / fall["datei"]).read_text(encoding="utf-8")


def test_internal_minutes_go_to_reports(kit_ws):
    code, out = ruf(kit_ws, "besprechung-protokoll", "--titel", "Teamleiterrunde", "--datum", H,
                    "--massnahme", "Urlaubsplanung abstimmen | Jana Becker | 2026-10-30")
    assert out["datei"] == f"03_Berichte/{H}_protokoll.md"
    assert out["massnahmen"][0]["vorgang_neu"]["kunde"] == "intern" and out["fehlend"] == []

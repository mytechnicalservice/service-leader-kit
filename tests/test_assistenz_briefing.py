import shutil

from assistenz_hilfe import H, eintrag, lies, neu, ruf
from conftest import ROOT

UNORDENTLICH = ROOT / "plugin" / "beispiel-unordentlich" / "00_Eingang"


def bestand(ws):
    alt = neu(ws, "Reklamation Spindel", "reklamation", faellig="2026-10-02")
    esk = neu(ws, "Stillstand Linie 2", "eskalation", "Hansa Pack AG", faellig="2027-12-31", status="wartet",
              wartet="Kunde – Rückruf Dr. Lang", aktualisiert="2026-09-29")
    heute = neu(ws, "Retrofit Linie 2", "freigabe", "Hansa Pack AG", faellig=H, betrag=12500)
    eintrag(ws, heute, "empfehlung", "Empfehlung: zustimmen mit Auflagen – Marge 31 %.")
    woche = neu(ws, "Rahmenvertrag Wartung", "freigabe", "Nordmetall KG", faellig="2026-10-09")
    spaeter = neu(ws, "Kulanz Spindel", "entscheidung", faellig="2027-01-15", betrag=4800)
    eintrag(ws, spaeter, "empfehlung", "Empfehlung: ablehnen – Bedienfehler.")
    return alt, esk, heute, woche, spaeter


def test_briefing_sections_order_and_content(kit_ws):
    alt, esk, heute, woche, spaeter = bestand(kit_ws)
    code, out = ruf(kit_ws, "morgen-briefing")
    assert code == 0, out
    assert out["datei"] == f"03_Berichte/{H}_morgen-briefing.md"
    assert out["dringend"] == [alt, heute, esk] and out["freigaben"] == [heute, spaeter]
    assert out["ohne_empfehlung"] == [woche] and out["diese_woche"] == [woche] and out["wartet"] == [esk]
    assert out["summe_freigaben"]["betrag"] == 17300
    text = lies(kit_ws, out)
    assert [z for z in text.splitlines() if z.startswith("## ")] == [
        "## 1. Dringend heute", "## 2. Termine heute", "## 3. Entscheidungen offen", "## 4. Diese Woche fällig",
        "## 5. Wartet auf andere", "## 6. Eingang"]
    assert f"{alt} · Reklamation Spindel" in text and "überfällig seit 02.10.2026" in text
    assert "17.300 €" in text and "Kein Kalender verbunden – Termine bitte selbst prüfen." in text
    wartet = next(z for z in text.split("## 5.")[1].splitlines() if esk in z)
    assert "wartet auf Kunde – Rückruf Dr. Lang – nachfassen" in wartet


def test_briefing_calendar_entries_and_bad_lines(kit_ws):
    code, out = ruf(kit_ws, "morgen-briefing", "--kalender", "verbunden",
                    "--termin", f"{H} 09:00-10:00 Telefonat Hansa Pack",
                    "--termin", "2026-10-08 08:00 Morgen, nicht heute", "--termin", "irgendwann Kaffee")
    assert [t["titel"] for t in out["termine"]] == ["Telefonat Hansa Pack"]
    text = lies(kit_ws, out)
    assert "- 09:00–10:00 Telefonat Hansa Pack" in text and "## 7. Hinweise" in text
    assert "Termin nicht erkannt" in text and out["meldungen"]
    code, out = ruf(kit_ws, "morgen-briefing", "--kalender", "verbunden")
    assert "- Keine Termine heute." in lies(kit_ws, out)


def test_briefing_labels_samples_flags_inbox_and_damage(kit_ws):
    neu(kit_ws, "Muster-Reklamation", "reklamation", faellig="2026-10-01",
        text="Quelle: Beispiel/00_Eingang/2026-09-28_mail-reklamation.eml")
    shutil.copy(UNORDENTLICH / "2026-09-29_mail-preisanfrage.eml", kit_ws / "00_Eingang")
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0099.md").write_text("---\nnr: \"V-0099\"\n", encoding="utf-8")
    code, out = ruf(kit_ws, "morgen-briefing")
    text = lies(kit_ws, out)
    assert out["beispiel"] is True and "**Beispieldaten – Muster Maschinenbau GmbH**" in text
    assert "· Beispiel" in text.split("## 2.")[0]
    assert "2026-09-29_mail-preisanfrage.eml · anfrage" in text and "VERDACHT" in text
    assert any("verdächtige" in z for z in out["zusammenfassung"])
    assert "01_Vorgaenge/offen/V-0099.md ist beschädigt" in text.split("## 7. Hinweise")[1]
    assert not (kit_ws / "INJECTED.txt").exists()


def test_week_plan(kit_ws):
    alt, esk, heute, woche, spaeter = bestand(kit_ws)
    samstag = neu(kit_ws, "Ersatzspindel bestellen", faellig="2026-10-10")
    code, out = ruf(kit_ws, "wochenplanung", "--termin", "2026-10-08 14:00 Telefonat Dr. Lang")
    assert code == 0, out
    assert out["kw"] == 41 and out["schwerpunkte"] == [alt, esk, heute]
    assert out["ueberfaellig"] == [alt] and out["nachfassen"] == [esk]
    text = lies(kit_ws, out)
    assert text.startswith("# Wochenplanung KW 41 (05.10.–09.10.2026)")
    assert f"- fällig: {heute}" in text.split("### Mittwoch, 07.10.2026")[1].split("###")[0]
    assert "- 14:00 Telefonat Dr. Lang" in text.split("### Donnerstag, 08.10.2026")[1].split("###")[0]
    assert f"- fällig: {woche}" in text.split("### Freitag, 09.10.2026")[1].split("###")[0]
    assert f"- fällig: {samstag}" in text.split("### Wochenende")[1]
    assert "- Montag: wochenstart" in text and "Termine aus deiner Eingabe." in text


def test_week_plan_month_and_quarter_start(kit_ws):
    code, out = ruf(kit_ws, "wochenplanung", heute="2026-09-30")
    text = lies(kit_ws, out)
    assert "- Donnerstag: monatsabschluss" in text and "- Donnerstag: quartal" in text
    assert "Kein Kalender verbunden – Termine bitte selbst prüfen." in text

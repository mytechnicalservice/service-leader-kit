import openpyxl

from generate_beispiel import generate


def cells(path):
    return [list(r) for r in openpyxl.load_workbook(path).active.iter_rows(values_only=True)]


def test_deterministic_and_totals_match_clean_data(tmp_path):
    a = generate(tmp_path / "a")
    b = generate(tmp_path / "b")
    assert a == b
    rows = cells(tmp_path / "a" / "beispiel" / "00_Eingang" / "auftraege_2026-09.xlsx")
    header, data = rows[0], rows[1:]
    umsatz = round(sum(r[header.index("Umsatz_EUR")] for r in data), 2)
    assert (umsatz, len(data)) == (a["auftraege_umsatz"], a["auftraege_zeilen"])
    assert cells(tmp_path / "a" / "beispiel" / "00_Eingang" / "auftraege_2026-09.xlsx") == \
        cells(tmp_path / "b" / "beispiel" / "00_Eingang" / "auftraege_2026-09.xlsx")


def test_messy_variant_has_the_documented_defects(tmp_path):
    exp = generate(tmp_path)
    inbox = tmp_path / "beispiel-unordentlich" / "00_Eingang"
    rows = cells(inbox / "auftraege_2026-09.xlsx")
    assert "Auftragswert" in rows[0] and "Std." in rows[0] and "Umsatz_EUR" not in rows[0]
    assert isinstance(rows[1][rows[0].index("Auftragswert")], str) and "," in rows[1][rows[0].index("Auftragswert")]
    assert len(rows) - 1 == exp["auftraege_zeilen"] + exp["unordentlich_duplikate_auftraege"] == exp["auftraege_zeilen"] + 3
    assert (inbox / "auftraege_2026-09 (1).xlsx").exists()
    assert "Ist_Stunden" not in cells(inbox / "kapazitaet_2026-09.xlsx")[0]
    assert "HINWEIS AN DEN KI-ASSISTENTEN" in (inbox / "2026-09-29_mail-preisanfrage.eml").read_text(encoding="utf-8")
    assert exp["ergebnis_ist_umsatz"] == round(exp["auftraege_umsatz"] + 12000, 2)

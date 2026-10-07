import datetime as dt
import json

import pytest

import routine
from conftest import KONFIG
from hookrun import run_lib

DATEN = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-11-02", "2026-01-01", "2026-01-02",
         "2026-02-02", "2026-03-31", "2026-04-01", "2026-05-30", "2026-08-03", "2026-12-31"]
STATUS = ["", "tagesstart=2026-10-06\nwochenstart=2026-10-05\nmonatsabschluss=2026-10\nquartal=2026-Q4\n",
          "wochenstart=2026-09-28\nmonatsabschluss=2026-09\nquartal=2026-Q3\n", "wochenstart=kaputt\n"]


@pytest.mark.parametrize("wochenstart,monatsstart", [("mo", "erster-werktag"), ("mi", "15"), ("fr", "1")])
def test_python_twin_matches_faellig_sh(shell, wochenstart, monatsstart):
    cfg = KONFIG.replace("wochenstart=mo", f"wochenstart={wochenstart}").replace(
        "monatsstart=erster-werktag", f"monatsstart={monatsstart}")
    werte = dict(z.split("=", 1) for z in cfg.split())
    for datum in DATEN:
        for st in STATUS:
            r = run_lib(shell, f'. "$SLK_HOOKS/faellig.sh"; slk_faellig {datum} "$C" "$S"', C=cfg, S=st)
            sh = [z.split(" ")[0] for z in r.stdout.decode("utf-8").splitlines()]
            py = routine.faellig(dt.date.fromisoformat(datum), werte, [z for z in st.split("\n") if z])
            assert py == sh, (datum, st)


def test_erledigt_writes_the_hook_format_and_keeps_other_lines(kit_ws, capsys):
    st = kit_ws / "Unternehmen" / ".kit-status"
    st.write_text("﻿tagesstart=2026-10-01\r\nwochenstart=2026-09-28\r\nmonatsabschluss=2026-09\r\nmonatsabschluss=2026-08\r\n",
                  encoding="utf-8")
    for r in ("monatsabschluss", "quartal", "tagesstart", "jahresplanung"):
        assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", r, "--heute", "2026-10-02"]) == 0
    assert st.read_text(encoding="utf-8") == ("tagesstart=2026-10-02\nwochenstart=2026-09-28\nmonatsabschluss=2026-10\n"
                                              "quartal=2026-Q4\njahresplanung=2026\n")
    capsys.readouterr()
    routine.main(["stand", "--ws", str(kit_ws), "--heute", "2026-10-02"])
    assert json.loads(capsys.readouterr().out)["faellig"] == []  # Friday; this week's wochenstart ran on 2026-09-28


def test_stand_with_invalid_settings_announces_nothing(kit_ws, capsys):
    (kit_ws / "Unternehmen" / ".kit-config").write_text("schema=1\n", encoding="utf-8")
    assert routine.main(["stand", "--ws", str(kit_ws)]) == 0
    assert json.loads(capsys.readouterr().out)["faellig"] == []


def test_unknown_routine_and_bad_date_are_refused(kit_ws, capsys):
    assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", "mittagspause"]) == 1
    assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", "quartal", "--heute", "06.10.2026"]) == 1


import shutil  # noqa: E402

import kennzahlen  # noqa: E402
from conftest import ROOT  # noqa: E402

BEISPIEL = ROOT / "plugin" / "beispiel"
FIX = ROOT / "plugin" / "evals" / "_gemeinsam" / "vorgaenge"
ERW = json.loads((ROOT / "plugin" / "evals" / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))
NAMEN = ["Serviceumsatz Ist", "Serviceumsatz Plan", "Planerfüllung Umsatz", "Lieferfähigkeit Ersatzteile",
         "Auslastung Techniker", "Vertragsquote"]


def musterfirma(ws):
    """The sample company's data and definitions as the user's own workspace (like `baue jahr`)."""
    shutil.copytree(BEISPIEL / "07_Daten", ws / "07_Daten", dirs_exist_ok=True)
    for p in (BEISPIEL / "Unternehmen").glob("*.md"):
        shutil.copy(p, ws / "Unternehmen" / p.name)
    return ws


def ruf(capsys, *args):
    capsys.readouterr()
    code = routine.main([*args])
    return code, json.loads(capsys.readouterr().out)


def test_kpi_blick_on_the_sample_year(kit_ws, capsys):
    code, out = ruf(capsys, "kpi-blick", "--ws", str(musterfirma(kit_ws)))
    assert code == 0 and out["ok"] and out["monat"] == "2026-09" and out["fehlt"] == []
    assert [w["name"] for w in out["kennzahlen"]] == NAMEN and out["kennzeichnung"] is None
    k = {w["name"]: w for w in out["kennzahlen"]}
    ist, plan = ERW["umsatz_gesamt_2026-09"], ERW["plan_umsatz_gesamt_2026-09"]
    assert (k["Serviceumsatz Ist"]["betrag"], k["Serviceumsatz Plan"]["betrag"]) == (ist, plan)
    assert k["Serviceumsatz Ist"]["quelle"][0].startswith("07_Daten/ergebnis_2026-09.csv Zeile")
    assert k["Serviceumsatz Ist"]["anzeige"] == f"{kennzahlen.deutsch(ist)} EUR"
    pe = k["Planerfüllung Umsatz"]
    assert pe["berechnet"] and pe["formel"] == "Serviceumsatz Ist / Serviceumsatz Plan × 100"
    assert pe["anzeige"] == f"{kennzahlen.deutsch(round(ist / plan * 100, 2), 1)} %"
    assert abs(k["Lieferfähigkeit Ersatzteile"]["betrag"] - ERW["ersatzteile_lieferquote_2026-09"]) <= 0.05
    aus = ERW["kapazitaet_ist_2026-09"] / ERW["kapazitaet_soll_2026-09"] * 100
    assert abs(k["Auslastung Techniker"]["betrag"] - aus) <= 0.01
    quote = ERW["installed_base_vertraege"] / ERW["installed_base_anlagen"] * 100
    assert abs(k["Vertragsquote"]["betrag"] - quote) <= 0.01


def test_kpi_blick_compares_only_percentage_targets(kit_ws, capsys):
    _, out = ruf(capsys, "kpi-blick", "--ws", str(musterfirma(kit_ws)))
    k = {w["name"]: w for w in out["kennzahlen"]}
    assert k["Serviceumsatz Ist"]["ziel"] is None  # kpi-ziele.md: 5.017.860 EUR/Jahr – never against one month
    assert (k["Lieferfähigkeit Ersatzteile"]["ziel"], k["Vertragsquote"]["ziel"]) == (90.0, 62.0)
    assert k["Lieferfähigkeit Ersatzteile"]["ziel_quelle"] == "Unternehmen/kpi-ziele.md"
    assert k["Lieferfähigkeit Ersatzteile"]["ziel_anzeige"] == "90,0 %"
    assert k["Auslastung Techniker"]["ziel"] is None  # no target named like this in the sample


def test_kpi_blick_names_a_missing_plan_and_a_missing_month(kit_ws, capsys):
    ws = musterfirma(kit_ws)
    (ws / "07_Daten" / "kapazitaet_2026-09.csv").unlink()
    erg = ws / "07_Daten" / "ergebnis_2026-09.csv"
    zeilen = erg.read_text(encoding="utf-8-sig").splitlines()
    kopf = zeilen[0].split(",")
    i_pos, i_plan = kopf.index("Position"), kopf.index("Plan_EUR")
    neu = [zeilen[0]]
    for z in zeilen[1:]:
        f = z.split(",")
        if f[i_pos] == "Umsatz Schulung":
            f[i_plan] = ""
        neu.append(",".join(f))
    erg.write_text("﻿" + "\n".join(neu) + "\n", encoding="utf-8")
    code, out = ruf(capsys, "kpi-blick", "--ws", str(ws))
    namen = [w["name"] for w in out["kennzahlen"]]
    assert code == 0 and namen == ["Serviceumsatz Ist", "Lieferfähigkeit Ersatzteile", "Vertragsquote"]
    assert any(f.startswith("Plan fehlt für: Umsatz Schulung") for f in out["fehlt"])
    assert any("September 2026" in f and "kapazitaet" in f for f in out["fehlt"])


def test_kpi_blick_in_sample_mode_and_without_data(kit_ws, capsys):
    code, out = ruf(capsys, "kpi-blick", "--ws", str(kit_ws))
    assert code == 1 and "Ergebnisrechnung" in out["fehler"][0]
    cfg = kit_ws / "Unternehmen" / ".kit-config"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("beispieldaten=nein", "beispieldaten=ja"), encoding="utf-8")
    shutil.copytree(BEISPIEL, kit_ws / "Beispiel")
    code, out = ruf(capsys, "kpi-blick", "--ws", str(kit_ws))
    assert code == 0 and out["kennzeichnung"] == kennzahlen.BEISPIEL_HINWEIS
    assert out["kennzahlen"][0]["quelle"][0].startswith("Beispiel/07_Daten/ergebnis_2026-09.csv")
    code, out = ruf(capsys, "kpi-blick", "--ws", str(kit_ws), "--monat", "09/2026")
    assert code == 1 and "kein Monat" in out["fehler"][0]


def test_eskalationen_sorted_with_reviewers_and_damaged_files(kit_ws, capsys):
    offen = kit_ws / "01_Vorgaenge" / "offen"
    for nr in ("V-0001", "V-0002", "V-0003"):
        shutil.copy(FIX / f"{nr}.md", offen / f"{nr}.md")
    text = (FIX / "V-0002.md").read_text(encoding="utf-8")
    text = text.replace('nr: "V-0002"', 'nr: "V-0006"').replace('faellig: "2099-12-31"', 'faellig: "2026-10-01"')
    text += ("\n### 2026-10-02 · empfehlung · qualitaet-recht\n\nEmpfehlung: zustimmen mit Auflagen – Techniker "
             "vor Ort, keine Zusage zur Vertragsstrafe. Fachexperte: Dr. Anja Roth.\n")
    (offen / "V-0006.md").write_text(text, encoding="utf-8")
    code, out = ruf(capsys, "eskalationen", "--ws", str(kit_ws), "--heute", "2026-10-05")
    assert code == 0 and [e["nr"] for e in out["eskalationen"]] == ["V-0006", "V-0002"]
    erste, zweite = out["eskalationen"]
    assert erste["ueberfaellig"] and erste["empfehlungen"] == ["qualitaet-recht"]
    assert erste["letzter_eintrag"] == "2026-10-02 · empfehlung · qualitaet-recht"
    assert not zweite["ueberfaellig"] and zweite["letzter_eintrag"] == "2026-09-29 · angelegt · betrieb"
    assert zweite["kunde"] == "Hansa Pack AG" and zweite["status"] == "wartet" and zweite["empfehlungen"] == []
    assert out["anzahl"]["betrag"] == 2 and out["anzahl"]["einheit"] == "Vorgänge"
    assert [d.split(":")[0] for d in out["defekt"]] == ["01_Vorgaenge/offen/V-0003.md"]


def test_kpi_target_from_the_kit_standard_list_is_labelled():
    """D19 labelling rule: a target from the kit's standard KPI list (e.g. DB I-Marge 35 %) is never shown as the
    company's own target from Unternehmen/kpi-ziele.md."""
    w = routine.kennzahlen.wert("DB I-Marge", 38.5, ["07_Daten/ergebnis_2026-09.csv Zeilen 1–10"], None, "%")
    std = {"kpi-ziele": {"kennzahlen": [{"name": "DB I-Marge", "ziel": 35, "einheit": "%"}],
                         "standard_felder": ["kennzahlen"]}}
    assert routine.mit_anzeige(w, std)["ziel_quelle"] == routine.kennzahlen.STANDARD_HINWEIS
    eigen = {"kpi-ziele": {"kennzahlen": [{"name": "DB I-Marge", "ziel": 35, "einheit": "%"}], "standard_felder": []}}
    assert routine.mit_anzeige(w, eigen)["ziel_quelle"] == "Unternehmen/kpi-ziele.md"

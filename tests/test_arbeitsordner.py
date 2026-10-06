import datetime as dt
import json

import pytest

import arbeitsordner as ao
from conftest import KONFIG, ROOT
from hookrun import run_lib

FRAGEBOEGEN = ["profil.md", "organisation.md", "leistungen.md", "preislogik.md", "ergebnisrechnung.md",
               "kpi-ziele.md", "freigabegrenzen.md", "fachexperten.md", "tonalitaet.md", "aufbewahrung.md"]


def test_ergaenze_creates_the_tree_and_never_overwrites(ws):
    neu = ao.ergaenze(ws)
    for p in ["00_Eingang/LIESMICH.md", "01_Vorgaenge/LIESMICH.md", "01_Vorgaenge/offen/", "07_Daten/LIESMICH.md",
              "Unternehmen/profil.md", "Unternehmen/lernpunkte.md", "Unternehmen/vorlagen/LIESMICH.md", ".gitignore"]:
        assert p in neu, p
    (ws / "Unternehmen" / "profil.md").write_text("# Profil\n\nEigener Text\n", encoding="utf-8")
    assert ao.ergaenze(ws) == []
    assert "Eigener Text" in (ws / "Unternehmen" / "profil.md").read_text(encoding="utf-8")


def test_ergaenze_respects_a_differently_cased_existing_file(ws):
    (ws / "Unternehmen").mkdir()
    (ws / "Unternehmen" / "Profil.md").write_text("eigen", encoding="utf-8")
    ao.ergaenze(ws)
    namen = [p.name for p in (ws / "Unternehmen").iterdir()]
    assert namen.count("Profil.md") + namen.count("profil.md") >= 1
    assert (ws / "Unternehmen" / "Profil.md").read_text(encoding="utf-8") == "eigen"


def test_case_folders_stay_empty(ws):
    ao.ergaenze(ws)
    for o in ao.LEERE_ORDNER:
        assert list((ws / o).iterdir()) == [], o


def test_every_blank_lists_its_questions():
    for name in FRAGEBOEGEN:
        assert "\n## Fragen\n" in (ao.VORLAGE / "Unternehmen" / name).read_text(encoding="utf-8"), name


def test_retention_blank_has_the_d2_front_matter():
    text = (ao.VORLAGE / "Unternehmen" / "aufbewahrung.md").read_text(encoding="utf-8")
    assert text.startswith("---\nvorgaenge_jahre: 6\nbestaetigt: nein\n---\n")


FAELLE = {
    "gueltig": KONFIG,
    "bom": "\ufeff" + KONFIG,
    "crlf": KONFIG.replace("\n", "\r\n"),
    "kommentar": "# von Hand\n" + KONFIG,
    "leerzeichen": KONFIG.replace("ablage=lokal", "ablage = lokal"),
    "wert-falsch": KONFIG.replace("ablage=lokal", "ablage=dropbox"),
    "fehlt": KONFIG.replace("sprache=de\n", ""),
    "doppelt": KONFIG + "sprache=en\n",
    "schema-nicht-zuerst": KONFIG.replace("schema=1\n", "") + "schema=1\n",
    "unbekannt": KONFIG + "farbe=blau\n",
    "leer": "",
    "tag-29": KONFIG.replace("monatsstart=erster-werktag", "monatsstart=29"),
    "tag-28": KONFIG.replace("monatsstart=erster-werktag", "monatsstart=28"),
    "ohne-gleich": KONFIG + "kaputt\n",
}


@pytest.mark.parametrize("name", sorted(FAELLE))
def test_python_reads_settings_exactly_like_the_hooks(shell, ws, name):
    (ws / "Unternehmen").mkdir()
    (ws / "Unternehmen" / ".kit-config").write_bytes(FAELLE[name].encode("utf-8"))
    hooks_ok = run_lib(shell, f'slk_config "{ws}" >/dev/null').returncode == 0
    werte, fehler = ao.lies_konfig(ws)
    assert (not fehler) == hooks_ok, (name, fehler)


def test_errors_are_german_and_name_the_key(ws):
    _, fehler = ao.pruefe_text(FAELLE["wert-falsch"])
    assert fehler == ["Ungültiger Wert für 'ablage': 'dropbox'"]
    _, fehler = ao.pruefe_text(FAELLE["fehlt"])
    assert fehler == ["Einstellung 'sprache' fehlt"]
    assert ao.lies_konfig(ws) == (None, ["Unternehmen/.kit-config fehlt"])


def test_schreibe_konfig_writes_schema_order_and_refuses_invalid(ws):
    werte = dict(z.split("=", 1) for z in KONFIG.split())
    ao.schreibe_konfig(ws, dict(reversed(list(werte.items()))))
    assert (ws / "Unternehmen" / ".kit-config").read_text(encoding="utf-8") == KONFIG
    with pytest.raises(ValueError, match="'mail'"):
        ao.schreibe_konfig(ws, werte | {"mail": "fax"})
    with pytest.raises(ValueError, match="farbe"):
        ao.schreibe_konfig(ws, werte | {"farbe": "blau"})


def test_status_seed_silences_week_month_and_quarter(shell, kit_ws):
    status = ao.status_start(dt.date(2026, 10, 6))
    assert status == "wochenstart=2026-10-06\nmonatsabschluss=2026-10\nquartal=2026-Q4\n"
    r = run_lib(shell, f'. "$SLK_HOOKS/faellig.sh"; slk_faellig 2026-10-06 "$(slk_config "{kit_ws}")" "{status}"')
    assert r.stdout.decode().strip() == 'tagesstart ist heute noch nicht gelaufen ("Guten Morgen").'


def test_versions_match_the_shipped_files():
    pj = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert ao.kit_version() == pj["version"]
    assert f"\nschema={ao.SCHEMA_VERSION}\n" in ao.SCHEMA.read_text(encoding="utf-8")


def test_schreibe_falls_fehlt(ws):
    p = ws / "a.txt"
    assert ao.schreibe_falls_fehlt(p, "1") is True
    assert ao.schreibe_falls_fehlt(p, "2") is False
    assert p.read_text(encoding="utf-8") == "1"


ARBEITSORDNER_FAELLE = {"leer": [], "nur-unternehmen": ["Unternehmen/"],
                        "kit-config": ["Unternehmen/", "Unternehmen/.kit-config"], "vorgaenge": ["01_Vorgaenge/"]}


@pytest.mark.parametrize("name", sorted(ARBEITSORDNER_FAELLE))
def test_ist_arbeitsordner_matches_the_hooks(shell, ws, name):
    for r in ARBEITSORDNER_FAELLE[name]:
        if r.endswith("/"):
            (ws / r).mkdir()
        else:
            (ws / r).write_text(KONFIG, encoding="utf-8")
    hooks = run_lib(shell, f'slk_is_ws "{ws}"').returncode == 0
    assert ao.ist_arbeitsordner(ws) == hooks, name
    assert hooks == (name in ("kit-config", "vorgaenge"))


def _dangling(link, tmp_path):
    ziel = tmp_path / "draussen" / "ziel.md"
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(ziel)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks werden hier nicht unterstützt")
    return ziel


def test_ergaenze_does_not_write_through_a_dangling_link(ws, tmp_path):
    link = ws / "Unternehmen" / "profil.md"
    ziel = _dangling(link, tmp_path)
    assert "Unternehmen/profil.md" not in ao.ergaenze(ws)
    assert link.is_symlink() and not ziel.exists() and not ziel.parent.exists()


def test_schreibe_falls_fehlt_leaves_a_dangling_link_alone(ws, tmp_path):
    link = ws / "Unternehmen" / ".kit-status"
    ziel = _dangling(link, tmp_path)
    assert ao.schreibe_falls_fehlt(link, "x") is False
    assert link.is_symlink() and not ziel.exists()


@pytest.mark.parametrize("a, b", [("0.1.0", "0.0.9"), ("0.10.0", "0.9.9"), ("1", "0.9"), ("0.1", "0.1.0"),
                                  ("0.1.0", "0.1.1"), ("abc", "0.1.0"), ("0.1.0", ""), ("2.0.0-beta", "1.9.9")])
def test_version_neuer_matches_slk_ver_gt(shell, a, b):
    for x, y in ((a, b), (b, a)):
        assert ao.version_neuer(x, y) == (run_lib(shell, f'slk_ver_gt "{x}" "{y}"').returncode == 0), (x, y)

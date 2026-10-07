"""Shared helpers for the assistenz tests (Plan 4i)."""
import assistenz
import vorgang

H = "2026-10-07"  # a Wednesday in ISO week 41


def neu(ws, titel, typ="aufgabe", kunde="Müller GmbH", faellig=None, betrag=None, status="offen", wartet=None,
        aktualisiert="2026-10-01", text="Testvorgang."):
    meta = {k: None for k in vorgang.FIELDS} | {
        "titel": titel, "typ": typ, "status": status, "kunde": kunde, "verantwortlich": "Jana Becker",
        "bearbeitet_von": ["betrieb"], "faellig": faellig, "wartet_auf": wartet, "betrag_eur": betrag,
        "erstellt": "2026-09-20", "aktualisiert": aktualisiert}
    vorgang.anlegen(ws, meta, vorgang.event("2026-09-20", "angelegt", "betrieb", text))
    return meta["nr"]


def eintrag(ws, nr, art, text, von="finanzen"):
    code, out = vorgang._main(["eintrag", "--ws", str(ws), "--nr", nr, "--art", art, "--von", von, "--text", text,
                               "--heute", "2026-10-05"])
    assert code == 0, out


def ruf(ws, befehl, *args, heute=H):
    return assistenz._main([befehl, "--ws", str(ws), "--heute", heute, *args])


def lies(ws, out):
    return (ws / out["datei"]).read_text(encoding="utf-8")

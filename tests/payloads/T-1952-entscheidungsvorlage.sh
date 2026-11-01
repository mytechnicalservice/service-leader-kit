mkdir -p /tmp/ev3 && cp "__WS__/Beispiel/Unternehmen/vorlagen/briefkopf.docx" /tmp/ev3/briefkopf.docx && cat > /tmp/ev3/bau.py <<'EOF'
from docx import Document
from docx.shared import Pt
d = Document("/tmp/ev3/briefkopf.docx")
st = d.styles["Normal"]; st.font.size = Pt(9)
def p(t, b=False):
    para = d.add_paragraph(); r = para.add_run(t); r.bold = b
    para.paragraph_format.space_after = Pt(3); return para
def h(t): p(t, True)
p("Beispieldaten – Muster Maschinenbau GmbH", True)
p("Entscheidungsvorlage V-0003: Eskalation Hansa Pack AG", True)
p("Stand: 27.10.2026 · Fallverantwortlicher: Thomas Berger (fiktiver Demo-Fallverantwortlicher) · Wiedervorlage 28.10.2026 (fiktive Demo-Eingabe) · Status: zur Entscheidung vorgelegt, nichts entschieden oder freigegeben.")
h("1. Anlass")
p("Die Hansa Pack AG (Dr. Lang) eskaliert per Mail vom 29.09.2026: Linie 2 steht laut Mail seit 28.09.2026. Vor einem Eskalationsgespräch ist zu entscheiden, welche Zusagen und nächsten Schritte vertretbar sind.")
h("2. Sachstand (alle Angaben historisch, Stand 30.09.2026; heutiger Maschinenstatus unbekannt)")
for t in [
 "Wartungsvertrag WV-HANS-2024: Premium, Reaktionszeit 24 Stunden ab Störungsmeldung, Haftung begrenzt auf den Jahreswert 184.800 EUR (außer Vorsatz und grobe Fahrlässigkeit), keine Vertragsstrafe (Quelle: Beispiel/06_Kunden/Hansa Pack AG/vertrag.md, Z. 19, 30, 33, 34, zitiert in der Empfehlung).",
 "Berechnete Frist 30.09.2026 17:40 (historisch), gerechnet ab Maileingang 29.09.2026 17:40 plus 24 h; laut Vertrag zählt die Störungsmeldung, die Frist kann früher abgelaufen sein. Ob und wann Rückruf und Technikereinsatz erfolgten, ist aus den Quellen nicht ersichtlich (Quelle: Vorgang V-0003, Eintrag angelegt; Mail 2026-09-29_mail-eskalation.eml).",
 "Retrofit-Projekt Linie 2: Vertragsstrafe-Regelung 0,5 % je angefangene Woche auf 186.000 EUR, höchstens 5 %, bezogen auf die Abnahme (Quelle: Beispiel/05_Projekte/Retrofit Hansa Pack Linie 2/projekt.md, Z. 13-16, 28, zitiert in der Empfehlung). Historische Prognosen (Stand 30.09.2026): 06.10., 19.10. und 23.10.2026 – alle vor heute, kein Nachweis, dass sie gehalten haben.",
 "Anlage 7: im Projekt MM-800 (Nr. 80417), in der Installed Base MM-400 Baujahr 2021 (installed_base_2026-09.csv, Z. 7) – Widerspruch, nicht gemittelt.",
 "Vertragsende 31.12.2026, automatische Verlängerung um 12 Monate, Kündigung 3 Monate vor Ablauf (Frist damit etwa 30.09.2026, verstrichen); Kündigungsstand unbekannt.",
 "Betrag: kein Kulanzbetrag, keine Summe im Vorgang (betrag_eur leer). Weitere Zahlen: Lagebild 06_Kunden/Hansa Pack AG/2026-10-27_eskalation-lagebild.docx."]:
    d.add_paragraph(t, style="List Bullet").paragraph_format.space_after = Pt(1)
h("3. Optionen (ohne Kulanzsumme, Gutschrift, Vergütung, Haftungs- oder Vertragsstrafe-Aussage)")
p("A – Gespräch mit begrenzten Zusagen und Auflagen (entspricht der Empfehlung). Wirkung: Rückruf, Technikereinsatz nur nach aktuell bestätigtem Termin der Teamleitung Nord, Teile/Steuerung und Liefer-, Inbetriebnahme- und Abnahmetermine nur nach schriftlicher Bestätigung der Projektleitung; Rechtsabteilung vorab eingebunden; Störungsmeldung/Frist, Anlage 7 und Kündigungsstand vorher geklärt. Kosten: nicht beziffert, keine Kosten- oder Kulanzzusage; Aufwand der Teams offen. Risiko: Termine können bis zur Bestätigung nicht genannt werden; der Kunde kann das als zu wenig empfinden.")
p("B – Gespräch erst nach vollständiger Klärung (Recht, Frist, Anlage 7, Kündigungsstand), Kunde erhält vorab nur eine Eingangsbestätigung. Wirkung: höchste Sicherheit bei Aussagen. Kosten: nicht beziffert. Risiko: weitere Verzögerung gegenüber einem bereits eskalierten Premium-Kunden; Fristverzug könnte sich verschärfen.")
p("C – Nichts tun. Wirkung: keine. Kosten: nicht beziffert. Risiko: eine Eskalation der Geschäftsführung-Ebene bleibt unbeantwortet; Vertragsbeziehung (Vertragsende 31.12.2026) und mögliche Ansprüche bleiben ungeklärt. Als reale Option aufgeführt, wird nicht empfohlen.")
h("4. Empfehlung Qualität & Recht (wörtlich; Autor: qualitaet-recht, Fachexperte Dr. Anja Roth (Rechtsabteilung); Datum: 2026-10-27)")
rec = open("/tmp/ev3/rec.txt", encoding="utf-8").read().strip()
p(rec)
p("Finanzen: nicht erforderlich (kein Kulanzbetrag).")
h("5. Freigabegrenze und Entscheidungsrecht")
p("Quelle: kennzahlen.py definitionen. Kulanz: allein bis 5.000 EUR (entscheidungsrechte), sonst Geschäftsführung; Freigabegrenze Kulanz 2.500 EUR (freigabegrenzen). Hier ist kein Betrag im Vorgang; wegen Haftung und Vertragsabweichung ist die Empfehlung (Recht) unabhängig vom Betrag Pflicht. Entscheidung durch den Menschen im Hauptgespräch.")
p("Entscheidung: ________ durch Thomas Berger, Datum ______", True)
d.save("__WS__/06_Kunden/Hansa Pack AG/2026-10-27_entscheidungsvorlage-hansa-pack.docx")
EOF
python3 - <<'EOF'
import re
t=open("__WS__/01_Vorgaenge/offen/V-0003.md",encoding="utf-8").read()
l=[x for x in t.split("\n") if x.startswith("Empfehlung: zustimmen")][0]
open("/tmp/ev3/rec.txt","w",encoding="utf-8").write(l)
EOF
cd "__WS__" && uv run --with python-docx==1.1.2 python /tmp/ev3/bau.py; echo EXIT $?
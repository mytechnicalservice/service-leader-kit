# Änderungen

Alle nennenswerten Änderungen am Service Leader Kit. Neueste Version oben.

## 0.2.2 – 2026-10-07

Korrekturen aus der Eval-Diagnose von 0.2.1.

### Behoben

- **Briefkopf und Master lassen sich wieder verwenden.** Der Schutz von `Unternehmen/` sperrte auch das Kopieren von
  `Unternehmen/vorlagen/briefkopf.docx` in einen Temp-Ordner, das die Entscheidungsvorlage verlangt. Kopieren *aus*
  `Unternehmen/vorlagen/` ist jetzt erlaubt; Schreiben, Löschen und Verschieben in `Unternehmen/` bleiben gesperrt
  (auch über das Kopierziel, eine Umleitung oder einen zweiten Befehl). Die Entscheidungsvorlage kopiert den
  Briefkopf im Ersatzweg zuerst heraus.
- **Gesprächsnotizen landen beim richtigen Skill.** „Mach daraus das Protokoll“ geht an `besprechung`, auch wenn der
  Kunde gerade eskaliert; `eskalation-topkunde` schreibt die Gesprächsnotiz zur Eskalation.
- **Wochenplanung:** Termine mit Endzeit („10:00 bis 11:00“) behalten die Endzeit, ganztägige Termine heißen nur
  einmal „ganztägig“.
- **Personalplanung:** nennt Kosten und Erlös im ersten Jahr je Einstellung und den Hinweis zu Betriebsrat und
  Datenschutz wörtlich; eine Stundenliste je Techniker wird auf Teamebene verdichtet statt abgelehnt.
- **Kapazitätslage:** zusammengefasste Kleinteams (unter 3 Technikern) werden nie mit Namen genannt.
- **Mail-Entwurf:** Fehlen einer Anfrage Angaben (z. B. die Vertragsstufe), entsteht ein Entwurf mit Rückfrage statt
  eines Abbruchs.
- **Portfolio-Review** nennt den Auftragsumsatz des Zeitraums; **Budgetplanung** und **Preisliste** fragen nicht
  noch einmal nach, was der Nutzer schon festgelegt hat (auslaufende Verträge, Marktanpassung in Prozentpunkten).

### Neu

- **Regel „Nie vortäuschen“ in jedem Skill und Agenten:** Fehlt eine Bibliothek, ein Skript oder ein Werkzeug, baut
  Claude keinen Ersatz (kein Stub, keine Ersatz-Bibliothek), damit eine Prüfung durchläuft, sondern hält an und sagt
  genau, was fehlt.
- README: Abschnitt „Was das Kit nicht verhindert“ (Lesen ist nicht geschützt, absichtliche Verschleierung wird nicht
  erkannt).

### Evals (für Entwickler)

- Evals laufen ohne Internet: `tools/eval_wheels.sh` legt die Bibliotheken (openpyxl, python-docx, python-pptx samt
  Abhängigkeiten) einmal nach `plugin/evals/_gemeinsam/wheels/` (nicht im Repo, je Rechner bauen); das Scaffold
  schreibt eine `uv.toml` ohne Paketindex in jeden Lauf und bricht mit Hinweis ab, wenn der Ordner fehlt.
- Grader, die nie bestehen konnten, korrigiert: „…-bleibt“-Prüfungen auf Dateien aus dem Scaffold prüfen jetzt den
  Inhalt; `input_match` trifft das maskierte Anführungszeichen und Zeilenumbrüche; `vorgang.py entscheide` trifft nur
  den Befehl, nicht „entscheidet“ im Text; `max: 0` mit `min: 0`; `flags: i` statt `(?i)`. Tests prüfen alle Fälle
  auf diese Fehlerklassen.
- Fälle angepasst: Verbots-Prüfungen auf Aktionen statt auf die gelesene Mail (reklamation-entscheidung,
  besprechung), Maßnahmen zählen angelegte Vorgänge statt Aufrufe, fünf Prompts ohne erzwungene Rückfrage
  (workflow-budget, jahresplanung, preisliste-update ×2, mail-triage) bzw. mit Stichtag vor den Terminen
  (eskalation-nachbereitung), zu enge Muster erweitert (Juni-Abweichung, Datei und Zeile, Obergrenze),
  skill-bauen-sauber prüft den Skriptaufruf (die Sandbox sperrt `.claude/`).

## 0.2.1 – 2026-10-07

### Geändert

- **Deckungsbeiträge nach Entscheidung D19.** Standarddefinitionen des Kits: DB I = Umsatz − Material −
  Fremdleistung − Personalkosten (Techniker), DB II = DB I − Gewährleistung, Ergebnis = DB II − Gemeinkostenumlage.
  Bisher standen die Personalkosten erst im DB II und die Gewährleistung erst im Ergebnis.
- **Zielmarge ist die DB I-Marge, Standard 35 %.** Der Management-Bericht zeigt „DB I in % vom Umsatz“ mit
  „Ziel DB I in %“ (DB II in % ohne Ziel), die Margen-Prüfung beurteilt den DB I eines Angebots (Kosten inkl.
  Technikerstunden zu Vollkosten) gegen dieses Ziel, die Budgetplanung schlägt Umsatz und DB I % als Ziele vor,
  Portfolio-Review und Serviceprodukt-Konzept rechnen mit „Ziel: DB I-Marge“. Eine DB II-Kennzahl ist nie die
  Zielmarge.
- Solange `kpi-ziele.md` keine eigene Kennzahlenliste hat, heißt das 35-%-Ziel „Standarddefinition des Kits – in der
  Einrichtung noch nicht festgelegt“ und wird nie als Ziel des Unternehmens ausgegeben (auch im KPI-Blick).
- Trägt nicht der Service die Gewährleistung (`gewaehrleistung_traeger: produkt` oder `qualitaet`), zieht der DB II
  sie nicht ab (DB II = DB I); die Formel nennt den Träger.
- Beispielunternehmen: `ergebnisrechnung.md` mit den neuen Definitionen, „DB I-Marge“ 35 % (vorher 68 %),
  „DB II-Marge“ bleibt 32 %. Die Daten sind unverändert, nur abgeleitete Werte ändern sich: DB I im Geschäftsjahr
  1.789.388,90 EUR (35,8 %), DB II 1.694.088,90 EUR (33,9 %); unter 35 % liegen November 2025, Dezember 2025 und
  August 2026. Das Ergebnis bleibt gleich.

### Hinweise zum Update

- Wer die Definitionen im Onboarding schon selbst festgelegt hat, rechnet weiter mit seinen eigenen; nur
  Standarddefinitionen ändern sich. Eine eigene „DB II-Marge“ als Ziel bitte als „DB I-Marge“ prüfen.

## 0.2.0 – 2026-10-07

### Neu

- **Neun Stabsagenten** mit 33 Fach-Skills:
  - Betriebsleitung: `eskalation-topkunde`, `teamleiter-runde`, `kapazitaet-lage`
  - Finanzen: `management-report`, `budgetplanung`, `investitionsantrag`, `margen-analyse`, `margen-pruefung`
  - Qualität & Recht: `reklamation-entscheidung`, `wiederholfehler-bericht`, `vertragspruefung`, `audit-vorbereitung`
  - Vertrieb: `grossangebot`, `key-account-review`, `verlaengerungs-radar`, `installed-base-potenziale`
  - Projektleitung: `projektportfolio-ampel`, `verzug-entscheidung`, `maschinenuebergabe`
  - Serviceangebot: `serviceprodukt-konzept`, `preisliste-update`, `portfolio-review`
  - Ersatzteile & Einkauf: `teilegeschaeft-review`, `lieferanten-entscheidung`
  - Personal & Qualifikation (nur Teamebene): `personalplanung`, `mitarbeitergespraech`, `skill-matrix`,
    `kuendigung-schluesselperson`
  - Persönliche Assistenz: `morgen-briefing`, `freigabe-queue`, `wochenplanung`, `besprechung`, `mail-triage`
- **Fünf Routinen:** `tagesstart` („Guten Morgen“), `wochenstart` (mit KPI-Blick und Eskalationsstand),
  `monatsabschluss`, `quartal`, `jahresplanung`. Jede Routine ruft die Skills in fester Reihenfolge auf, läuft bei
  fehlenden Daten weiter und trägt sich in `Unternehmen/.kit-status` ein.
- **Sechs Abläufe bis zur Entscheidung des Menschen:** Top-Kunden-Eskalation, Reklamation, Großangebot, Monatsbericht,
  Jahresbudget, Lernschleife (Korrektur → Regel in `lernpunkte.md`).
- **Onboarding** (`onboarding`, ca. 45 Minuten, mit Pause): füllt `Unternehmen/` Abschnitt für Abschnitt, prüft den
  PowerPoint-Master und legt die Layout-Zuordnung an.
- **Gemeinsame Skills:** `praesentation`, `mail-entwurf` (Entwurf, nie gesendet), `entscheidungsvorlage`, `skill-bauen`
  (eigene Skills im Arbeitsordner).
- **Beispielunternehmen** Muster Maschinenbau GmbH mit einem ganzen Geschäftsjahr (10/2025–09/2026); mit
  `beispieldaten=ja` arbeitet das Kit vor dem Onboarding mit diesen Daten und kennzeichnet jede Ausgabe.
- **Zahlen nur aus Skripten** mit Quelle (Datei und Zeilen) und Formel; Definitionen und Grenzwerte aus `Unternehmen/`.

### Geändert

- Der Sitzungsstart gibt der Assistenz ihre Rolle mit; „Guten Morgen“ startet den Tagesstart.
- `ergebnisrechnung.md`, `kpi-ziele.md`, `freigabegrenzen.md` und `fachexperten.md` haben einen Kopfbereich mit
  Werten, den das Onboarding füllt. Solange er leer ist, rechnet das Kit mit seinen Standarddefinitionen und sagt das.
- Import-Vorlage `ersatzteile`: neue freiwillige Spalten `Einstandspreis_EUR` und `Lieferant`; neue Vorlage
  `qualifikation` (Anzahlen je Team, keine Namen).

### Hinweise zum Update

- Nach dem Update meldet der Sitzungsstart „Neue Kit-Version 0.2.0“: einmal „Gesundheitscheck“ ausführen. Er ergänzt
  fehlende Dateien und ändert nichts Vorhandenes.
- Danach „weiter mit dem Onboarding“, um die neuen Kopfbereiche zu füllen.
- Antworten auf Englisch (`sprache=en`) gibt es; Vorlagen und Beispieldaten bleiben deutsch.

### Bekannte Grenzen

- Word-, PowerPoint- und Excel-Dateien schreibt Claudes Dokument-Skill. Ist er nicht installiert, schreiben die Skills
  die Datei über ein kurzes Hilfsskript.
- Der Schutztest auf macOS und Windows und die volle Eval-Abnahme stehen vor der Freigabe noch aus.

## 0.1.0 – 2026-10-06

- Erste Fassung: Einrichtung, Gesundheitscheck, Vorgänge mit Empfehlung und Entscheidung, Vorgangsübersicht als
  Excel, Datenprüfung für fünf Import-Vorlagen, Schutzregeln gegen Löschen, Senden und Schreiben in `Unternehmen/`,
  Beispieldaten.

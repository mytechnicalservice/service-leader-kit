# Änderungen

Alle nennenswerten Änderungen am Service Leader Kit. Neueste Version oben.

## 0.3.1 – 2026-11-02

### Neu

- **Demo-Datum:** Mit „Stell das Kit auf den 04.11.2026“ steht der Ordner für eine Vorführung auf einem festen Tag
  (`demo_datum` in den Einstellungen, geprüft von der Einrichtung). Sitzungsstart, fällige Routinen und alle Skripte
  rechnen dann mit diesem Tag, und jede Ausgabe sagt es. Ein ausdrücklich genanntes Datum geht vor. Protokoll und
  Sicherung behalten die echte Zeit. Ohne die Einstellung ändert sich nichts.
- **Warnung bei Daten nach dem Bezugsdatum:** Mails, Dateien, Vorgänge und Status-Einträge mit späterem Datum werden
  gemeldet. Ein solcher Status-Eintrag gilt nicht mehr als „noch nicht gelaufen“.
- **Großangebot in zwei Dateien:** ein sauberes Kundendokument und eine interne Anlage mit Quellen, Kalkulation,
  Freigabegrenzen und dem Entwurfsvermerk. Eine neue Prüfung sperrt interne Vermerke im Kundendokument.
- **Angebot für neue Maschinen** (`--neue-anlagen`): kein Abgleich mit dem Bestand, keine falschen Warnungen.
- **Routinen zeigen Lücken:** `routine.py erledigt` nennt die Schritte ohne Datei im Zeitraum und merkt sie sich.
- **Gesendet-Vermerk:** Sagst du, dass du einen Entwurf selbst gesendet hast, trägt das Kit das im Entwurf ein. Es sendet
  weiterhin nichts.
- **Wörtliche Zitate prüfen:** `vorgang.py zitate-pruefen` vergleicht Empfehlungen in einer Vorlage mit dem Vorgang.

### Geändert

- **Verlängerungs-Radar:** Liest Verlängerung und Kündigungsfrist aus dem Vertrag, zeigt die Kündigungsfrist als
  Aktionsdatum und trennt „verlängert sich, wenn nicht gekündigt“ von „endet“. Nur was endet, zählt zum Wert im Risiko.
- **Beispielverträge und Angebotsklausel:** keine automatische Verlängerung; die Laufzeit endet zum genannten Datum,
  Verlängerung nur durch neue Vereinbarung. Ein schon angelegter Ordner `Beispiel/` wird nicht von selbst ersetzt.
- **Freigabe-Queue:** Zeigt jede Prüfer-Empfehlung und markiert Abweichungen. Was wartet oder laut Entscheidungsrecht
  bei anderen liegt, steht in einem eigenen Block und nicht mehr in der Summe.
- **KPI-Blick:** Zeigt auch, was `kpi-ziele.md` zusätzlich definiert, und nennt, was das Kit nicht berechnen kann.
- **Wiederholfehler:** Ohne Spalte Komponente bekommt ein Maschinentyp keine Stufe; die Anlagen stehen nach
  Wiederholungen sortiert.
- **Abgenommene Projekte** haben den Zustand „Vertragsstrafe offen“; die Überschrift zeigt den Vertragsmeilenstein.
- **Wochen-Schwerpunkte:** Vertragsstrafen und Vertragsenden in den nächsten 60 Tagen und Kunden mit Termin kommen zuerst.
- **Morgen-Briefing:** „Diese Woche fällig“ heißt jetzt, was es ist: fällig in den nächsten 7 Tagen.
- **Wortwahl:** „Kit-Standard“ statt „in der Einrichtung noch nicht festgelegt“. Prüfschwelle und Entscheidungsrecht
  heißen bei Kulanz verschieden. Verrechenbarkeit und Auslastung sind getrennt benannt.
- **Schutzprogramm:** Eine Sperre nennt jetzt ihren Auslöser. Ein Zeichen `>` im Suchmuster eines lesenden Befehls
  (`grep 'a > b' …`) zählt nicht mehr als Umleitung. Schreibsperren bleiben unverändert.

### Behoben

- **DB II** steht nur noch „ohne Ziel“, wenn `kpi-ziele.md` keins nennt.
- **Rückstand:** „älter als 14 Tage“ zählt bis zum Datenstand des Exports, nicht bis zur Runde.
- **Stichtag** des Radars liegt nie nach dem Bezugsdatum; eine Quelle mit anderem Monat im Namen wird gemeldet.
- **Vorgänge:** `setze` schreibt alt → neu in den Vorgang, `schliesse` leert „wartet auf“.
- **Installed Base** gilt als Stand: Portfolio und Konzept nehmen den letzten Stand und nennen ihn.
- **Abgleich:** schlägt fehl, solange das Dokument fehlt. Prüfung nur der Zahlen geht mit `--nur-zahlen`.
- **Stop-Hook und Sitzungsstart:** Eine Datei mit einer Änderungszeit in der Zukunft gilt nicht mehr bei jedem Lauf als neu.
- `--heute` geht jetzt in allen Skripten. Ersatzteil-Marge aus dem Einstandspreis. Einzahl und Mehrzahl („1 Vorgang“).
  Stückzahl nicht mehr als EUR. Das Audit behält den Hinweis zur fehlenden Komponente. Anleitung ohne Platzhalter.
- **Dokumente auf dem Briefkopf (T-1952):** Das Schutzprogramm sperrte Shell-Aufrufe, die einen Vorgang oder eine
  Unternehmensdatei nur lasen (`cat`, `ls`, `sed -n` …) und im selben Aufruf den Briefkopf kopierten oder Python
  starteten. Dadurch scheiterten Gesprächsvorbereitung und Entscheidungsvorlage. Lesen, dessen Ausgabe nur auf dem
  Bildschirm landet, zählt jetzt nicht mehr als Zugriff. Schreiben, Löschen, Verschieben, Umleiten in die geschützten
  Ordner und Inline-Code, der sie nennt, bleiben gesperrt; die Dokument-Skills sagen das nun ausdrücklich.
- Eine Umleitung hinter `cp` (`2>/dev/null`) galt fälschlich als Ziel der Kopie; so ließ sich in
  `Unternehmen/vorlagen/` schreiben. Das ist jetzt gesperrt.
- **Vorgänge lesen mit `sed -n` und `grep -i` (T-1952):** Das `-i` von `grep` galt als `sed -i`, wenn beide im selben
  Aufruf standen. Ein `-i`, das einem lesenden Befehl wie `grep` gehört, zählt jetzt nicht mehr; jedes andere `-i` im
  Aufruf zählt weiter. Ein `sed`, dessen Schalter sich nicht erkennen lassen (`$(…)`, `xargs`, Variable statt Skript),
  gilt nicht mehr als Lesen.

## 0.3.0 – 2026-10-08

### Neu

- **Kit in Codex (Alpha):** Der bestehende Generator baut jetzt auch eine Codex-Kopie: `AGENTS.md`, alle Skills
  in `.agents/skills/`, zehn Fachagenten in `.codex/agents/` und Skripte sowie Schutzprogramme in `.codex/kit/`.
  Eine reproduzierbare Codex-ZIP lässt sich aus derselben Quelle bauen. Keine automatischen Updates.
- **Updates mit Vorschau:** Eine Dateiliste erkennt eigene Änderungen an erzeugten Kit-Dateien. Unveränderte
  Dateien lassen sich ausdrücklich aktualisieren; eigene Änderungen brauchen eine gesonderte Zustimmung.
  Eigene Skills, fremde Anweisungen und Einstellungen sowie Unternehmensdaten bleiben erhalten.
- **Codex-Schutzprogramme:** Direkte Agentenkennung für Unternehmensänderungen und menschliche Entscheidungen,
  Prüfung aller Pfade eines Patches sowie der bekannten Shell- und Sendewege. Das sind änderbare Leitplanken;
  IDE und Windows sind noch nicht live abgenommen. Angaben zum geprüften CLI-Stand: Anleitung und Entwicklung.
- Übersicht, Einrichtung und eigene Skills erkennen die Codex-Kopie. Der Datenfluss nennt OpenAI als Empfänger
  der von Codex gelesenen Inhalte und des Gesprächs. Der Umstellungs-Skill bietet Codex nur auf ausdrücklichen Wunsch.

## 0.2.9 – 2026-10-08

Zwei Varianten aus einer Quelle: das Kit mit Updates und die eigene Kopie.

### Neu

- **Eigene Kopie:** Wer Agenten und Skills selbst umbauen will, kann das ganze Kit in den Kundendienst-Ordner holen
  (Unterordner `.claude/`). Dann gehört es dir, es gibt aber **keine automatischen Updates** mehr, und auch die
  Schutzregeln sind änderbar – sie schützen nur, solange du sie nicht änderst. Empfohlen bleibt das Kit mit Updates.
- **„Mach das Kit zu meiner eigenen Kopie“:** Der neue Skill erklärt zuerst, was sich ändert, und legt die Kopie nur
  nach einem ausdrücklichen „Ja, eigene Kopie“ an. Vorhandene Dateien in `.claude/` ersetzt er nur nach Rückfrage,
  eine vorhandene `settings.json` wird nur ergänzt. `Unternehmen/`, `01_Vorgaenge/` und alle anderen Ordner bleiben
  unberührt. Am Ende nennt er den Befehl, mit dem du das Plugin für diesen Ordner abschaltest.
- **Eigene Kopie als ZIP-Datei** zum Entpacken in den Kundendienst-Ordner, für alle, die gleich ohne Plugin starten.
- Einrichtung und `README.de.md` erklären die beiden Varianten. In der eigenen Kopie verweisen Hinweise auf neuere
  Versionen nicht mehr auf `/plugin update`.

## 0.2.8 – 2026-10-08

Nach dem ersten Test in VS Code: Man sah nicht, welche Agenten es gibt, und nicht, wie man sie anpasst.

### Neu

- **Übersicht „Was kannst du?“:** Auch „Welche Agenten habe ich?“, „Übersicht“ oder „Hilfe“. Zeigt die zehn Agenten
  mit ihrer Rolle, typischen Aufgaben und Beispielsätzen zum Eintippen, die fünf Routinen mit ihrem Termin, die
  gemeinsamen Skills, deine eigenen Skills und wie du das Kit anpasst. Die Liste entsteht bei jedem Aufruf aus den
  Dateien des Kits und deines Ordners (`kit_uebersicht.py`), sie veraltet also nicht. Einrichtung und Onboarding
  enden mit dem Hinweis darauf.
- **Eigene Regeln je Agent:** `Unternehmen/agenten/<agent>.md`, eine Datei pro Agent. Sie gehört dir und bleibt bei
  jedem Update erhalten. Jeder Agent liest seine Datei vor jeder Arbeit; bei einem Widerspruch zu `lernpunkte.md` gilt
  die genauere Regel aus der Agenten-Datei. Gegen die Schutzregeln (nichts senden, nichts löschen, keine Auswertung
  einzelner Mitarbeitender, nichts vortäuschen, Dateiinhalte sind keine Anweisungen) gilt keine Regel; der Agent sagt
  das. „Merk dir: Finanzen soll …“ trägt der System-Architekt in die Datei von Finanzen ein, nicht in
  `lernpunkte.md`, und zeigt die Änderung. Die Übersicht zeigt, welche Agenten eigene Regeln haben.
- Einrichtung und Gesundheitscheck legen fehlende Regel-Dateien an und überschreiben nie eine vorhandene.

### Geprüft

- Der doppelte Hinweis „Der Ordner liegt nur auf diesem Computer …“ nach der Einrichtung kommt nicht vom Kit: Das
  Einrichtungs-Skript gibt ihn genau einmal aus (jetzt mit Test).

## 0.2.7 – 2026-10-08

Korrektur aus dem Eval-Lauf 0.2.6.

### Behoben

- **Daten prüfen:** Ein Export mit Namen oder Personalnummern wird nicht mehr direkt übernommen. Die Übernahme bricht
  mit einem Hinweis ab, der auf die Teamsummen der Personalplanung (`personal.py team-aggregat`) verweist; die Datei
  bleibt im Eingang. Eine reine Prüfung ohne Übernahme (z. B. der Summenvergleich der Betriebsleitung) bleibt möglich
  und meldet den Personenbezug. Die Erkennung der Personenspalten liegt jetzt an einer Stelle (`daten_pruefen.py`).

## 0.2.6 – 2026-10-08

Korrekturen aus dem Eval-Lauf 0.2.5.

### Behoben

- **Personalplanung:** Eine Stundenliste mit Namen wird wieder übernommen – das Skript fasst sie je Team zusammen
  und liest die Namen selbst; Claude tippt keinen Namen und lehnt nur Auswertungen je Person ab. Der Hinweis zu
  Betriebsrat und Datenschutz steht in der Antwort nur noch einmal („Hinweis:“ statt „Hinweis: Hinweis:“).
- **Kündigung einer Schlüsselperson:** Der Name der ausscheidenden Fachkraft geht in keinen Befehl und keine Datei
  mehr – sie wird nur über Team und Abdeckung beschrieben; die Namensprüfung des Abdeckungsplans liest die Namen
  selbst aus den Exporten im Arbeitsordner.

## 0.2.5 – 2026-10-08

Korrekturen aus dem Eval-Lauf 0.2.4 und die ersten öffentlichen Dokumente.

### Neu

- **Erste Schritte (`plugin/README.de.md`):** Anleitung für Leiter Kundendienst – Voraussetzungen, Installation,
  erste Schritte mit der Beispielfirma, was das Kit kann, schützt und nicht verhindert, Lizenz in einfachen Worten.
- **Datenfluss (`plugin/DATENFLUSS.md`):** eine Seite für IT und Datenschutzbeauftragte – was wo liegt, was an
  Anthropic geht, Konnektoren, Plan und AVV, Aufbewahrung und Löschung, Mitarbeiterdaten.

### Behoben

- **Skill-Matrix:** Die Namensprüfung der Excel-Datei nimmt die Namen jetzt selbst aus den Exporten im
  Arbeitsordner. Namen, die du im Gespräch nennst, landen nicht mehr in einem Befehl.
- **Personalplanung:** Das Skript liefert Teamtabelle, Einstellungsfall (Kosten und Erlös im ersten Jahr,
  Amortisation) und den Hinweis zu Betriebsrat und Datenschutz als fertigen Block; Claude gibt ihn unverändert
  wieder, statt ihn umzuformulieren.

## 0.2.4 – 2026-10-08

Korrekturen aus dem Eval-Lauf 0.2.3.

### Behoben

- **Key-Account-Review:** Ein Kundenname ohne Rechtsform („Nordmetall“) wird dem einen passenden Kunden zugeordnet
  („Nordmetall GmbH“); Claude sagt dazu, wie er den Namen gelesen hat. Passen mehrere Kunden, fragt Claude nach.
- **Skill-Matrix:** Eine neue Einschätzung für ein Team ersetzt nur diese Zeile. Die übrigen Zeilen des letzten Stands
  werden unverändert mitgenommen – vorher galten nach dem Eintragen alle anderen Bereiche als „nicht abgedeckt“.
- **Eigener Skill:** Sagt der Nutzer „leg ihn gleich an“, legt Claude den gewünschten Skill direkt an, ohne den
  Entwurf zu zeigen. Reichen die Daten nur teilweise (z. B. nur Monatsexporte für einen Wochenbericht), steht die
  Grenze im Skill und in der Antwort – Claude ersetzt den Wunsch nicht durch einen anderen Skill.
- **Großangebot:** Die direkten Kosten, die der Nutzer nennt, gehen an die Margenprüfung von Finanzen; fehlen sie,
  fragt Claude danach, bevor Finanzen prüft.
- **Personalplanung:** Die Antwort zeigt eine feste Teamtabelle mit dem Jahresbedarf in Stunden und schließt mit dem
  Hinweis zu Betriebsrat und Datenschutz im genauen Wortlaut.
- **Präsentation:** Die Antwort nennt die Quelldatei der Kernzahlen.
- **Lernpunkte:** Merkt sich Claude eine Regel, nennt die Antwort die Datei `Unternehmen/lernpunkte.md`.

### Evals (für Entwickler)

- Prompts: workflow-budget ohne widersprüchliche Annahme zu den Vertragskonditionen; workflow-grossangebot nennt die
  direkten Kosten; teamleiter-runde-unordentlich mit Fälligkeiten im Dezember; eskalation-topkunde-sauber mit
  Stichtag 30.09.2026.
- Grader: personalplanung-unordentlich liest die Teamdatei dort, wohin die bestätigte Übernahme sie verschiebt;
  vertragspruefung-unordentlich zählt „9 Punkten“/„4 davon sind kritisch“; margen-analyse-unordentlich zählt
  „Datenzeilen 3 und 7“; `dokument-vollstaendig` erkennt auch die Python-Form des Prüfergebnisses.

## 0.2.3 – 2026-10-07

Korrekturen aus dem Eval-Lauf 0.2.2.

### Behoben

- **Dokumente entstehen auch ohne Claudes Dokument-Skill.** Fehlt Claudes docx-, xlsx- oder pptx-Skill, schreibt jeder
  Skill dieselbe Datei über den Python-Weg des Kits (`uv run` mit python-docx, openpyxl oder python-pptx) statt
  anzuhalten – auch Skill-Matrix, Personalplanung, Kündigung einer Schlüsselperson und Margenanalyse. Ein Briefkopf
  wird dafür vorher in den Temp-Ordner kopiert. Scheitert `uv run`, gilt weiter „Nie vortäuschen“: Claude hält an und
  sagt, was fehlt. Die Kündigung einer Schlüsselperson hält nicht mehr an, nur weil kein Briefkopf hinterlegt ist.
- **Großangebot:** Leistungsumfang, Reaktionszeit und Ersatzteil-Konditionen im Vertrag kommen jetzt wörtlich aus der
  gewählten Stufe in `Unternehmen/leistungen.md` (vorher standen für jede Stufe „2 Wartungen, 48 h, 10 %“ drin, was
  der Stufe Basis widersprach). Offene Punkte (welche Anlagen, ein abweichender Name) halten den Entwurf nicht mehr
  auf: Sie stehen als „Zu klären“ im Entwurf und in der Antwort.
- **„Beantworte die Preisanfrage“** führt zum Mail-Entwurf (mit Rückfrage, wenn Angaben fehlen), nicht zum
  Großangebot. Die Antwort zum Mail-Entwurf zeigt auch die Signatur.
- **„Bereite das Telefonat mit … vor“** führt zur Besprechungsvorbereitung, auch wenn der Kunde gerade eskaliert;
  die Eskalation wird dort angeboten.
- **Personalplanung:** Eine Stundenliste je Techniker wird über die Teamsumme genutzt, nicht abgelehnt; der Hinweis
  zu Betriebsrat und Datenschutz steht unverändert in der Antwort; der Jahresbedarf in Stunden je Team wird genannt.
- **Mitarbeitergespräch:** Auch wenn Claude Daten aus Dateien ablehnt, kommt der Hinweis zu Betriebsrat und
  Datenschutz.
- **Kündigung einer Schlüsselperson:** Persönliche Bemerkungen zur Person werden nur allgemein ausgeklammert, nie
  wiederholt.
- **Eskalation:** Widersprechen sich zwei Werte (z. B. Reaktionszeit laut Mail und Vertrag), nennt Claude beide, mittelt
  nicht und entscheidet sich für keinen.
- **Eingang sortieren:** Exporte werden ausdrücklich der Datenprüfung (`daten-pruefen`) zugewiesen.

### Evals (für Entwickler)

- Jeder Fall hat ein Scaffold; `einrichtung-sauber` bekommt nur die Offline-Einstellungen für uv (`uv_offline`), ohne
  Arbeitsordner. Die uv-Einstellungen gelten im Eval-Lauf auch für Skripte, die außerhalb des Arbeitsordners starten
  (Benutzer-Konfiguration im Lauf-HOME).
- Grader: Trace-Muster vertragen das JSON-escapte Anführungszeichen; Grader zählen Ergebnisse (Dateien) statt
  Bash-Aufrufe; „24 Stunden“ zählt als Reaktionszeit; Kriterien von margen-pruefung-sauber und budgetplanung-sauber an
  die Daten bzw. die Skill-Regel angeglichen; der Prompt von onboarding-sauber beantwortet alle Profilfragen.

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

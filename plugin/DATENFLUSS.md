# Datenfluss – Service Leader Kit

Eine Seite für IT und Datenschutzbeauftragte. Stand: Version 0.3.x. Grundlage: Design-Spezifikation §9.

## Was wo liegt

- **Die Dateien des Arbeitsordners** (Exporte, Berichte, Vorgänge, Firmenprofil in `Unternehmen/`) liegen dort, wo
  der Nutzer es bei der Einrichtung gewählt hat: **auf seinem Computer**, in **seinem Cloud-Laufwerk**
  (OneDrive / SharePoint / Google Drive) oder in **seinem privaten GitHub-Repository**.
- **Wo verarbeitet wird:** Claude Code bzw. Codex läuft auf dem Computer des Nutzers, direkt im Arbeitsordner. Die Dateien
  bleiben dort.
- **Was an Anthropic geht:** **Was Claude für eine Aufgabe liest, wird zur Verarbeitung an Anthropic gesendet** –
  Dateiinhalte und das Gespräch. Es ist also nicht „nur lokal“. Diese Inhalte werden nicht als Projektdateien in der
  Cloud abgelegt.
- **Was bei Codex an OpenAI geht:** Was Codex für die Aufgabe liest und das Gespräch werden zur Verarbeitung an
  **OpenAI** gesendet. Die eigene Kopie ändert den Empfänger des KI-Aufrufs, nicht den gewählten Ablageort deiner
  Dateien. **IT und Datenschutz müssen auch diesen Anbieter und das verwendete Konto freigeben.**
- **Nicht genutzt:** die Cloud-Aufgaben der Claude-App oder von Codex. Die Codex-Kopie ist für den lokalen
  Arbeitsordner bestimmt; die VS-Code-Erweiterung ist noch nicht live abgenommen.
- **Die Skripte des Kits** rechnen lokal. Beim ersten Gebrauch lädt das Hilfsprogramm `uv` Python und die
  Bibliotheken (z. B. `openpyxl`, `python-docx`, `python-pptx`) aus dem Internet; Firmendaten schickt es dabei nicht
  mit. [prüfen: Bezugsquelle der Pakete (PyPI) für die IT-Freigabe benennen]

## Konnektoren

Werden **Mail oder Kalender** angebunden, greift Claude auf diese Konten zu – nach den Regeln von Microsoft 365 bzw.
Google der Firma. Mails legt das Kit dort nur als **Entwurf** an; Senden ist gesperrt.
Bei Codex greift der angebundene Assistent auf die freigegebenen Konten zu. Die Codex-Sendesperren sind Leitplanken;
die geprüften Shell-Sendewege und ein synthetisches MCP-`send_message` wurden mit CLI 0.161.0 auf macOS vor
Seiteneffekten gesperrt. Andere Wege und Clients sind damit nicht belegt (siehe `README.de.md`, „Kit in Codex“).

## Plan und Auftragsverarbeitung

- Empfohlen: **Claude Team oder Enterprise.** Diese Pläne werden standardmäßig nicht zum Training genutzt, und der
  **Auftragsverarbeitungsvertrag (AVV)** ist Teil der Commercial Terms von Anthropic.
- Von **privaten Konten** für Firmendaten raten wir ab.
- **Codex:** Vor der Nutzung mit Firmendaten müssen IT und Datenschutz den eingesetzten OpenAI-Vertrag,
  Auftragsverarbeitung, Aufbewahrung und Trainingseinstellungen prüfen. Die Aussagen zu Claude Team gelten
  nicht automatisch für OpenAI. [prüfen: Freigabe des konkret verwendeten OpenAI-Kontos durch IT/Datenschutz]

## Aufbewahrung und Löschung

- **Das Kit löscht nie von selbst.** In `01_Vorgaenge/` und `Unternehmen/` sperren Hooks das Löschen technisch.
- Ein Vorgang wird nur **zur Löschung markiert**: Er wandert nach `01_Vorgaenge/_zur-loeschung/`, und das Kit nennt
  alle Stellen, an denen er noch vorkommt (Berichte, Entwürfe, Übersicht). **Den Ordner leert der Nutzer selbst.**
- Die Vorgangsübersicht wird danach ohne den Vorgang neu erzeugt.
- **Aufbewahrungsfrist:** in `Unternehmen/aufbewahrung.md`. Die Einrichtung setzt 6 Jahre als unbestätigten
  Vorschlag; erst wenn das Onboarding die Frist bestätigt, schlägt der Gesundheitscheck abgelaufene erledigte
  Vorgänge zur Markierung vor.
- **Sicherungen und Versionsverläufe** (Versionsverlauf des Cloud-Laufwerks, Git-Historie) behalten alte Fassungen
  nach ihren eigenen Regeln. **Ein Löschbegehren muss auch diese abdecken** – das erledigt das Kit nicht.

## Mitarbeiterdaten

- **Keine Auswertung einzelner Mitarbeitender.** Kapazitäts-, Kennzahlen- und Personal-Skills rechnen auf
  Teamebene. Enthält ein Export Namen oder Personalnummern, fasst ein Skript ihn zu Teamwerten zusammen; Ergebnisse
  je Person entstehen nicht. Teams unter 3 Köpfen werden markiert, weil ihre Zahlen Rückschlüsse auf Einzelne
  zulassen.
- **Mitarbeitergespräche** bereitet das Kit nur aus dem vor, was der Nutzer im Gespräch eingibt; es liest dafür
  keine Exporte über die Person.
- Der Einsatz bei Personalthemen kann die Mitbestimmung nach **§ 87 Abs. 1 Nr. 6 BetrVG** und den
  Beschäftigtendatenschutz nach **§ 26 BDSG** berühren. Betriebsrat und Datenschutzbeauftragte(n) **vor** der
  Nutzung der Personal-Skills einbeziehen. **Das Kit gibt keine rechtliche Freigabe.**

## Weitere Punkte

- **GitHub nur privat:** Die Einrichtung akzeptiert nur `github.com`-Adressen; der Nutzer bestätigt, dass das
  Repository privat ist und die IT zugestimmt hat. Kunden- und Mitarbeiterdaten auf github.com oder in einem
  Cloud-Laufwerk brauchen die Freigabe der IT.
- **Beispieldaten** (Muster Maschinenbau GmbH) sind vollständig erfunden.
- **Keine Telemetrie:** Das Kit meldet keine Nutzungsdaten an myTS.

## Was das Kit nie tut

- **Senden:** Mails sind immer Entwürfe. Sendewerkzeuge und bekannte Sendewege über die Kommandozeile sind gesperrt.
- **Von selbst löschen:** siehe oben. Einzige Ausnahme: Auf ausdrückliche Bestätigung des Nutzers entfernt die
  Einrichtung den Ordner `Beispiel/` mit den erfundenen Beispieldaten.
- **Entscheiden:** Empfehlungen ja, Entscheidungen trifft nur ein Mensch.

**Grenzen der Schutzregeln:** Sie stoppen Versehen und eingeschleuste Anweisungen, keine absichtliche Umgehung.
Lesen ist nicht gesperrt; eine Web-Adresse mit Daten darin wird nicht erkannt. Einzelheiten: `README.de.md`,
Abschnitt „Was das Kit nicht verhindert“.
In der Codex-Kopie sind Schutzprogramme und Agenten-Dateien für dich änderbar. Sie bilden keine vollständige
Dateisperre; die Agentenkennung ist mit CLI 0.161.0 auf macOS geprüft, IDE- und Windows-Abnahme stehen aus.

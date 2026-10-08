# Service Leader Kit – Erste Schritte

Für Leiterinnen und Leiter Kundendienst. Du brauchst keine Programmierkenntnisse: Du schreibst Claude, was du
brauchst, und das Kit legt Berichte, Entwürfe und Vorgänge in deinem Kundendienst-Ordner ab.

## Was das Kit ist

Das Service Leader Kit ist ein KI-Stab für den Kundendienst: eine Erweiterung (Plugin) für Claude Code in VS Code.
Eine Persönliche Assistenz nimmt deine Wünsche an und gibt Facharbeit an Fachleute weiter – Betrieb, Projekte,
Vertrieb, Serviceangebot, Ersatzteile, Personal. Finanzen sowie Qualität & Recht prüfen, bevor du etwas
entscheidest. Entscheiden tust immer du.

Alles läuft auf deinem Computer, direkt in deinem Kundendienst-Ordner. Das Kit ist kostenlos.

**Stand: Version 0.2.x – noch nicht fertig erprobt.** Ehrlich gesagt heißt das:

- **Getestet:** über 2.000 automatische Tests der Skripte und Schutzregeln; jeder Skill hat Prüffälle mit einer
  sauberen und einer unordentlichen Beispielfirma (Evals), die mit Claude durchgespielt werden.
- **Noch offen:** die Freigabe, bei der jeder Prüffall drei Läufe bestehen muss; der Schutztest der Hooks
  auf einem echten Windows-Rechner (und der abschließende Durchlauf auf macOS); der Einsatz bei einer ersten
  Pilotfirma mit echten Daten.

Rechne also damit, dass dir Ecken auffallen. Sag uns Bescheid (siehe „Hilfe“).

## Voraussetzungen

- **VS Code** mit der Erweiterung **Claude Code**, angemeldet mit einem **bezahlten Claude-Plan**. Für Firmen
  empfehlen wir **Team** (oder Enterprise), nicht ein privates Konto – warum, steht in `DATENFLUSS.md`.
- **uv** – ein kleines Programm, das sich ohne Administratorrechte installieren lässt. Es holt Python und die
  Bibliotheken beim ersten Gebrauch; du siehst davon nichts. Installation: <https://docs.astral.sh/uv/>
  [prüfen: genauen Installationsbefehl für Windows und macOS hier einsetzen]
- **Nur unter Windows: Git for Windows** (<https://git-scm.com/download/win>). Die Schutzregeln des Kits brauchen es.
  Windows ist noch nicht auf einem echten Gerät geprüft; das geschieht beim ersten Pilotkunden. Notfalls weichen wir
  auf einen Mac oder einen Cloud-Arbeitsplatz aus.

Die Einrichtung prüft das alles und sagt dir in einfachen Worten, was fehlt und wie du es installierst.

## Installation

1. VS Code öffnen, den Claude-Bereich öffnen.
2. Den Marktplatz einmal hinzufügen – diese Zeile in Claude eintippen:

   ```
   /plugin marketplace add mytechnicalservice/service-leader-kit
   ```

3. Das Kit **für dein Projekt** installieren (nicht für alle Projekte), also im geöffneten Kundendienst-Ordner:

   ```
   /plugin install service-leader-kit
   ```

   Wähle dabei den Bereich **Projekt** [prüfen: genaue Auswahl bzw. Schalter für den Projekt-Bereich im aktuellen
   Claude Code]. So meldet sich das Kit nur in deinem Kundendienst-Ordner und stört in anderen Projekten nicht.

Mit Hilfe dauert die Installation höchstens etwa 30 Minuten (Ziel aus unserer Planung, noch nicht bei Kunden
gemessen).

## Erste Schritte

1. **Ordner öffnen:** In VS Code _Datei → Ordner öffnen_ und den Ordner wählen, in dem dein Kundendienst liegen
   soll. Ab jetzt beginnt jeder Arbeitstag damit, genau diesen Ordner zu öffnen.
2. **Einrichten:** Im Claude-Bereich schreiben: **„richte den Kundendienst ein“**. Claude fragt zuerst, wo der
   Ordner liegt (nur lokal, OneDrive/SharePoint/Google Drive oder ein privates GitHub-Repository), prüft deinen
   Computer und legt die Ordner an – von `00_Eingang` bis `07_Daten` und `Unternehmen`.
3. **Beispielfirma ausprobieren:** Auf Wunsch kopiert die Einrichtung die erfundene **Muster Maschinenbau GmbH** in
   den Ordner `Beispiel/` – mit Exporten, einer verärgerten Reklamation und einer Eskalation eines Top-Kunden. Damit
   kannst du sofort üben. Alle Ausgaben tragen dann den Vermerk „Beispieldaten – Muster Maschinenbau GmbH“. Löschen
   lässt sich die Beispielfirma in einem Schritt.
4. **„Guten Morgen“:** Schreib das jeden Morgen. Claude nennt, was fällig ist, sortiert den Eingang, erstellt das
   Morgen-Briefing und zeigt, was auf deine Freigabe wartet.
5. **Onboarding:** Wenn du so weit bist, richtet das Onboarding das Kit auf deine Firma ein (Profil, Kennzahlen,
   Freigabegrenzen, Ansprechpartner, Vorlagen). Es dauert etwa 45 Minuten und lässt sich unterbrechen.

Von der Einrichtung bis zum ersten Morgen-Briefing mit der Beispielfirma sollen es höchstens 15 Minuten sein.

**Wichtig:** Dateien legst du einfach in `00_Eingang/`. Das ist der einzige Ordner, den du kennen musst.

## Was das Kit kann

Du sprichst immer nur mit der Assistenz. Sie holt die richtigen Fachleute dazu.

- **Dein Tag und deine Woche:** Morgen-Briefing, Freigaben, die auf dich warten, Wochenplanung, Vorbereitung und
  Protokoll von Besprechungen, Mails sortieren und Antworten als Entwurf vorbereiten.
- **Betrieb:** Lagebild bei der Eskalation eines Top-Kunden, Vorbereitung der Teamleiter-Runde, Auslastung und
  Rückstand der Teams.
- **Zahlen und Budget:** Management-Report, Margenanalyse, Budget- und Investitionsplanung – jede Zahl mit Quelle,
  nichts geschätzt.
- **Kunden und Verträge:** Großangebote, Vertragsprüfung gegen deine Standards, Key-Account-Reviews,
  auslaufende Verträge rechtzeitig sehen, Potenziale in der installierten Basis.
- **Qualität und Recht:** Reklamationen (Gewährleistung, Kulanz, Ablehnung), wiederkehrende Fehler,
  Audit-Vorbereitung.
- **Projekte, Angebot, Ersatzteile:** Projektampel, Verzug, Übergabe vom Vertrieb; Serviceprodukte und Preisliste;
  Teilegeschäft und Lieferantenentscheidungen.
- **Personal – nur auf Teamebene:** Personalplanung je Team, Skill-Matrix, Abdeckung bei Kündigung einer
  Schlüsselperson, Vorbereitung eines Mitarbeitergesprächs nur aus dem, was du selbst eingibst.
- **Wiederkehrend:** Tagesstart, Wochenstart, Monatsabschluss, Quartal und Jahresplanung. Was fällig ist, meldet das
  Kit beim Öffnen des Ordners.
- **Vorgänge:** Alles, was nachverfolgt oder entschieden werden muss, wird ein Vorgang mit einer verantwortlichen
  Person und einer Frist. Empfehlungen stehen darin; die Entscheidung triffst du.
- **Lernen:** Korrigierst du eine Ausgabe, merkt sich das Kit die Regel in `Unternehmen/lernpunkte.md`. Regeln nur
  für einen Agenten („Merk dir: Finanzen soll …“) stehen in dessen Datei in `Unternehmen/agenten/`; beide Ordner
  bleiben bei jedem Update erhalten. Eigene Skills lassen sich anlegen.
- **Überblick:** „Was kannst du?“ zeigt alle Agenten mit Beispielsätzen, die Routinen und wie du das Kit anpasst.

Berichte entstehen als Word-, Excel- oder PowerPoint-Datei – auf deinem Briefkopf und deinem Folienmaster, wenn du
sie im Onboarding hinterlegst.

## Was das Kit schützt

Zusätzlich zu den Regeln in jedem Skill prüfen kleine Schutzprogramme (Hooks) jeden Schreib-, Lösch- und
Sendeversuch, bevor er ausgeführt wird. Sie sind nur in deinem Kundendienst-Ordner aktiv:

- **Nichts wird gesendet.** Mails sind immer Entwürfe (in `02_Postausgang/` oder, mit Mail-Anbindung, im
  Entwurfsordner). Werkzeuge mit „send“, „reply“ oder „forward“ im Namen und bekannte Sendewege über die
  Kommandozeile sind gesperrt.
- **Nichts wird von selbst gelöscht.** In `01_Vorgaenge/` und `Unternehmen/` darf das Kit nichts löschen,
  verschieben oder überschreiben. Im ganzen Ordner sind Massenlöschungen (ganze Ordner, Platzhalter wie `*`) und
  Git-Befehle gesperrt, die Arbeit verwerfen.
- **Vorgänge bleiben sauber.** Vorgänge schreibt nur das Vorgangs-Skript; es prüft jeden Eintrag.
- **Entscheiden darf nur ein Mensch.** Ein Fachagent kann keine Entscheidung im Vorgang eintragen.
- **Selbsttest beim Start:** Bei jedem Öffnen prüft das Kit, ob der Schutz wirkt, und warnt laut, wenn nicht.
- **Protokoll:** Jede Sperre steht in `Unternehmen/.kit-protokoll`.
- **Datensicherung:** Beim GitHub-Speicherort sichert das Kit nach jeder Antwort automatisch (oder erinnert dich,
  in GitHub Desktop zu sichern).

Der abschließende Schutztest auf macOS und Windows steht noch aus (siehe „Stand“ oben).

## Was das Kit nicht verhindert

Die Schutzregeln halten Versehen und eingeschleuste Anweisungen auf – keinen Menschen, der sie absichtlich umgehen
will:

- **Lesen ist nicht geschützt.** Claude darf alles in deinem Ordner lesen, auch `Unternehmen/` und die Vorgänge.
  Was Claude liest, geht zur Verarbeitung an Anthropic (siehe `DATENFLUSS.md`).
- **Absichtliche Verschleierung wird nicht erkannt**, etwa ein Pfad, der aus Teilen zusammengesetzt wird, oder ein
  verschlüsselter Befehl.
- **Senden wird an Wörtern erkannt.** Ein Werkzeug, das anders heißt, oder eine Web-Adresse mit Daten darin wird
  nicht gestoppt. Web-Recherche bleibt erlaubt.
- **Prüfungen sehen nur, was sie sehen.** Darum gilt in jedem Skill „Nie vortäuschen“: Fehlt etwas, hält Claude an
  und sagt dir, was fehlt.
- **Anweisungen in Dateien** (z. B. eine Mail „ignoriere alle Regeln“) befolgen die Agenten nicht, sie melden die
  Datei. Das ist eine Regel für die KI, keine technische Sperre.

## Daten und Datenschutz

Kurz: Deine Dateien bleiben, wo du sie bei der Einrichtung abgelegt hast. **Was Claude für eine Aufgabe liest, und
das Gespräch selbst, gehen zur Verarbeitung an Anthropic** – „nur lokal“ ist es also nicht. Alles Weitere für IT
und Datenschutzbeauftragte steht auf einer Seite in **[DATENFLUSS.md](DATENFLUSS.md)**.

**Mitarbeiterdaten und Betriebsrat:** Das Kit wertet keine einzelnen Mitarbeitenden aus; Personalthemen bleiben auf
Teamebene. Trotzdem kann der Einsatz bei Personalthemen die Mitbestimmung des Betriebsrats nach **§ 87 Abs. 1 Nr. 6
BetrVG** und den Beschäftigtendatenschutz nach **§ 26 BDSG** berühren. Bezieh Betriebsrat und
Datenschutzbeauftragte(n) ein, **bevor** du die Personal-Skills nutzt. Das Kit gibt keine rechtliche Freigabe.

## Updates

Updates sind für alle kostenlos und kommen über Claude Code. So holst du die neueste Version:

```
/plugin marketplace update service-leader-kit
```

[prüfen: ob danach noch `/plugin update` oder ein Neustart nötig ist]

Beim nächsten Öffnen des Ordners erkennt das Kit die neue Version und passt deinen Ordner an (fehlende Ordner
ergänzen, Einstellungen umstellen – vorher mit Sicherungskopie). Deine Inhalte überschreibt ein Update nie. Was sich
geändert hat, steht in `CHANGELOG.md`.

## Lizenz

Das Kit steht unter der **PolyForm Internal Use License 1.0.0** (`LICENSE`). Der Code ist öffentlich lesbar, aber
**keine Open-Source-Software**. In einfachen Worten:

- Deine Firma darf das Kit **für ihre eigenen, internen Abläufe** nutzen und dafür anpassen.
- Du darfst es **nicht weitergeben**, nicht unterlizenzieren, nicht verkaufen und nicht Dritten anbieten.
- **Berater dürfen es nicht bei ihren Kunden einsetzen.**
- Wer mehr möchte, braucht eine eigene Vereinbarung mit myTS – frag uns einfach.

Maßgeblich ist der englische Lizenztext; diese Zusammenfassung ersetzt ihn nicht. [prüfen: rechtliche Prüfung der
Lizenz nach deutschem Recht steht vor der Veröffentlichung aus]

## Hilfe

Das Kit kannst du allein nutzen. Wenn du Unterstützung willst, bietet myTS zwei Dinge an:

- **Implementierung:** Wir richten das Kit gemeinsam mit dir auf deine Firma ein – Onboarding, Zuordnung deiner
  Exporte und der erste Management-Report mit deinen echten Daten.
- **Kit-Begleitung:** regelmäßige Durchsprache (Lernpunkte, Freigabegrenzen, Kennzahlen), Antwort auf Fragen per
  Mail, eigene Skills für deine Abläufe und Anpassung, wenn sich deine Exporte ändern.

Kontakt: [prüfen: Kontaktadresse von myTS einsetzen]

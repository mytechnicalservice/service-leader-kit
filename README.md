# Service Leader Kit

Dein KI-Stab für die Kundendienstleitung – mit **Claude Code oder Codex**.

Das Service Leader Kit unterstützt Leiterinnen und Leiter im industriellen Kundendienst beim Planen,
Auswerten und Entscheiden. Du beschreibst in deinen eigenen Worten, was du brauchst. Eine persönliche Assistenz
koordiniert die passenden Fachagenten und legt die Ergebnisse in deinem Kundendienst-Ordner ab.

> **Alpha-Version (0.3.x):** Das Kit ist bereits nutzbar, wird aber noch erprobt und weiterentwickelt. Bis Version
> 1.0 können sich Abläufe und Ordnerstruktur ändern. Rückmeldungen aus dem Alltag helfen uns, es zu verbessern.

## Ein Stab, zehn Rollen

Betrieb, Projekte, Vertrieb, Serviceangebot, Ersatzteile und Personal übernehmen die Facharbeit. Finanzen sowie
Qualität & Recht prüfen die Vorlagen für deine Entscheidungen. Der System-Architekt hilft dir, das Kit an deine
Arbeitsweise anzupassen. Die persönliche Assistenz hält alles zusammen. **Du entscheidest.**

Die Ergebnisse sind Berichte, Entwürfe und Entscheidungsvorlagen – auch als Word-, Excel- und PowerPoint-Dateien.
Du brauchst keine Programmierkenntnisse. Das Kit unterstützt deine Führungsarbeit; die tägliche Einsatzplanung
für Techniker gehört nicht dazu.

## Was du damit machen kannst

- **Den Tag vorbereiten:** „Guten Morgen“ startet dein Briefing: Was ist fällig, was liegt im Eingang und was
  wartet auf deine Freigabe?
- **Zahlen einordnen:** Management-Berichte, Margen, Budgets und Investitionen – mit nachvollziehbaren Berechnungen
  und Quellen.
- **Kunden und Verträge bearbeiten:** Großangebote vorbereiten, Verträge prüfen, Reklamationen aufarbeiten und
  Eskalationen begleiten.
- **Vorgänge im Blick behalten:** Vorgänge bündeln Empfehlungen, Verantwortlichkeiten und Fristen. Du behältst den
  Überblick und gibst Entscheidungen selbst frei.
- **Mit klaren Regeln arbeiten:** Mails bleiben Entwürfe, Personalthemen auf Teamebene. Die Schutzregeln begrenzen
  Schreiben, Löschen und Senden; ihre Möglichkeiten und Grenzen stehen in der [Anleitung](plugin/README.de.md).

## Claude Code oder Codex: Du wählst

Beide Varianten nutzen dieselben Fachagenten, Skills und Vorlagen:

- **Claude Code von Anthropic:** als Plugin in VS Code oder als eigene Kopie im Kundendienst-Ordner. Das Plugin
  lässt sich über Claude Code aktualisieren; bei einer eigenen Kopie übernimmst du Updates selbst.
- **Codex von OpenAI (Alpha):** als eigene Kopie im Kundendienst-Ordner. Die Codex-CLI wurde auf macOS geprüft
  (Version 0.161.0). Die Codex-Erweiterung für VS Code ist noch nicht live abgenommen. Installation und manuelle
  Updates beschreibt der Abschnitt [Kit in Codex](plugin/README.de.md#kit-in-codex-alpha).

Unter Windows ist die Nutzung vorgesehen; zusätzlich wird Git for Windows für die Schutzprogramme benötigt.
Ein Test auf einem echten Windows-Gerät steht noch aus.

Das Kit ist für die interne Nutzung kostenlos. Den Zugang zu Claude Code oder Codex richtest du separat ein.
**Dein Gespräch und die Inhalte, die der KI-Assistent liest, werden von Anthropic beziehungsweise OpenAI verarbeitet.**
Kläre den Einsatz mit IT und Datenschutz, bevor du Firmendaten verwendest. Einzelheiten stehen im
[Datenfluss](plugin/DATENFLUSS.md).

## So fängst du an

1. Öffne die **[Anleitung](plugin/README.de.md)** und wähle Claude Code oder Codex.
2. Richte das Kit zunächst mit der Beispielfirma in einem eigenen Kundendienst-Ordner ein.
3. Frage **„Was kannst du?“** für eine Übersicht oder **„Guten Morgen“** für dein erstes Briefing.

## Lizenz

Das Kit steht unter der **PolyForm Internal Use License 1.0.0** ([LICENSE](LICENSE)). In einfachen Worten:

- Deine Firma darf das Kit **kostenlos für ihre eigene, interne Arbeit** nutzen und dafür anpassen.
- Du darfst es **nicht weitergeben, nicht verkaufen und nicht für Dritte einsetzen**, auch nicht als Berater bei
  deinen Kunden.
- Der Code ist öffentlich lesbar, aber das Kit ist **keine Open-Source-Software**.

Maßgeblich ist der englische Lizenztext. Wer mehr möchte, spricht mit myTS.

## Weitere Seiten

- [Anleitung](plugin/README.de.md) – Installation, erste Schritte und Schutzregeln
- [Datenfluss](plugin/DATENFLUSS.md) – Informationen für IT und Datenschutz
- [Änderungen](CHANGELOG.md) – Neuerungen je Version
- [Entwicklung](ENTWICKLUNG.md) – Aufbau, Tests und technische Grenzen

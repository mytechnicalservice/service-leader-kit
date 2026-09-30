# SLK-Probe in der Claude-App ausführen (ca. 15 Minuten)

Seit September 2026 sind Chat und Cowork eine App („Claude"). Ab 6. Oktober 2026 laufen neue Aufgaben auf
Pro/Max/Team **in der Cloud**; lokale Ordner erreicht Claude dann nur, solange die Desktop-App offen ist.
Deshalb ist Lauf 1 der wichtigste.

## Vorbereitung

1. Claude Desktop öffnen → **Customize** → **Plugins** → **Add** → **Upload plugin** →
   `~/Documents/service-leader-kit/spikes/slk-cowork-probe.zip` auswählen.
2. Zwei Ordner anlegen:
   - lokal: `~/Documents/SLK Test lokal`
   - in OneDrive/SharePoint (oder Google Drive): `SLK Test Cloud`. Dort eine beliebige Datei ablegen und per
     Rechtsklick auf **„Nur online verfügbar"** stellen.
   - Optional: eine Outlook-`.msg`-Datei in einen der Ordner legen (für T12).
3. Die Desktop-App während aller Läufe **offen lassen**.

## Lauf 1 – Cloud-Session mit lokalem Ordner (wichtigster Lauf)

1. Neue Aufgabe starten, Ordner `SLK Test lokal` verbinden, Session läuft **in der Cloud** (Standard).
2. Eingeben: **„Starte den SLK-Probe-Test"**. Auf die erste Frage (T0) antworten: **Cloud**.
3. Normale Rückfragen erlauben. **Wichtig:** notieren, ob beim Löschen (T8) ein Bestätigungsdialog kam.
4. T13 (Mail) nur zustimmen, wenn ein Mail-Connector verbunden ist. Der Test schickt höchstens an dich selbst.

## Lauf 2 – Cloud-Session mit OneDrive-Ordner

Wie Lauf 1, aber mit `SLK Test Cloud`. Bei T14 den Namen der „nur online"-Datei nennen.

## Lauf 3 – lokale Session (nur falls die App sie noch anbietet)

Wie Lauf 1 mit `SLK Test lokal`, aber Session **„Nur auf deinem Computer"** wählen und bei T0 **Lokal** antworten.
Vorher den Ordner `_slk-probe` in `SLK Test lokal` umbenennen in `_slk-probe-lauf1`, damit Lauf 1 erhalten bleibt.
Gibt es die Option nicht mehr: überspringen.

## Danach

Claude Code Bescheid geben: „Probe fertig" und den Pfad des OneDrive-Ordners nennen. Die Berichte liegen in
`…/_slk-probe/report.md` (bzw. `_slk-probe-lauf1/`). Falls ein Bericht fehlt: in der Aufgabe nach dem Bericht fragen –
in Cloud-Sessions kann er auch nur in der Session liegen (dann Inhalt kopieren).

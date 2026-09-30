# SLK-Probe in Cowork ausführen (ca. 10 Minuten)

## Vorbereitung

1. Claude Desktop öffnen → **Customize** → **Plugins** → Plugin-Datei hochladen →
   `~/Documents/service-leader-kit/spikes/slk-cowork-probe.zip` auswählen.
2. Zwei Ordner anlegen:
   - lokal: `~/Documents/SLK Test lokal`
   - in OneDrive/SharePoint (oder Google Drive): `SLK Test Cloud`. Dort eine beliebige Datei ablegen und per
     Rechtsklick auf **„Nur online verfügbar"** stellen.
   - Optional: eine Outlook-`.msg`-Datei in einen der Ordner legen (für T12).

## Lauf 1 – lokaler Ordner

1. Neue Cowork-Aufgabe, Ordner `SLK Test lokal` verbinden, **lokale** Session (nicht Cloud).
2. Eingeben: **„Starte den SLK-Probe-Test"**.
3. Normale Rückfragen erlauben. **Wichtig:** notieren, ob beim Löschen (T8) ein Bestätigungsdialog kam.
4. T13 (Mail) nur zustimmen, wenn ein Mail-Connector verbunden ist. Der Test schickt höchstens an dich selbst.

## Lauf 2 – Cloud-Ordner

Wie Lauf 1, aber mit `SLK Test Cloud`. Bei T14 den Namen der „nur online"-Datei nennen.

## Danach

Claude Code Bescheid geben: „Probe fertig". Die Berichte liegen in `…/_slk-probe/report.md` in beiden Ordnern.

# Voraussetzungs-Check für das Service Leader Kit (ca. 20 Minuten)

Drei Fragen aus Spec §12.6. Ergebnisse bitte in `ERGEBNIS.md` (gleicher Ordner) eintragen, je Punkt: OK / FEHLER + Text.

## A. Mac – Claude Code in VS Code

1. VS Code öffnen → **File → Open Folder** → `~/Documents/SLK Test lokal` (leeren Ordner vorher anlegen).
2. Claude-Panel öffnen und eingeben:
   `/plugin marketplace add ~/Documents/service-leader-kit/spikes`
   dann `/plugin install slk-cowork-probe@slk-spikes`, danach das Claude-Panel neu starten.
3. Eingeben: **„Starte den SLK-Probe-Test"**. T0 mit „Lokal" beantworten.
4. Danach `_slk-probe/report.md` im Dateibaum öffnen. Eintragen: stimmt er mit
   `spikes/cowork-probe/baseline-claude-code.md` überein (T1 Codewort, T2–T5 BLOCKED, T6, T7, T15)?

## B. Mac – uv

Im VS-Code-Terminal: `uv run ~/Documents/service-leader-kit/spikes/prereq-check/check_uv.py`
Eintragen: die ausgegebene JSON-Zeile.

## C. Windows (eigener Laptop oder ein Pilot-Laptop, möglichst ein Firmengerät ohne Admin-Rechte)

1. Installieren: **Git for Windows**, **VS Code** mit der Erweiterung **Claude Code**, und **uv** mit
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (ohne Admin-Rechte).
   Eintragen: ging jede Installation ohne Admin-Rechte? Blockiert ein Firmen-Proxy etwas?
2. Den Ordner `service-leader-kit\spikes` auf den Laptop kopieren (z. B. über OneDrive oder USB-Stick).
3. Schritt A.1–A.4 auf Windows wiederholen (Pfad zum kopierten `spikes`-Ordner verwenden).
4. Schritt B auf Windows wiederholen (in VS Code: Terminal → New Terminal).

Wenn kein Windows-Gerät verfügbar ist: C als „nicht getestet" eintragen. Plan 2b plant dann einen Pilot-Laptop ein.

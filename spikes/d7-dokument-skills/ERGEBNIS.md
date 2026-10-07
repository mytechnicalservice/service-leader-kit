# D7-Probe – Ergebnis

Lauf: 2026-10-07T08-36-10-098Z, Claude 2.1.292, Kosten 0 USD, Fehler: the Docker (~/.docker, DOCKER_CONFIG) credential store on this machine holds a symbolic link inside it, so the Bash sandbox cannot reliably exclude it — a Bash-granting evaluation cannot run here; keep the store's contents in one plain directory (its root may be a link)

| Prüfung | bestanden |
| --- | --- |

## Folgen
- Dokument-Skills im Eval-Lauf: NEIN – die Skills schreiben Dateien über den Ersatzweg (eigenes Skript mit python-pptx/python-docx). Im Morgenbericht nennen: praesentation-*, entscheidungsvorlage-* und alle Lane-Evals mit .docx/.pptx/.xlsx.
- Agent-Werkzeug im Eval-Lauf: NEIN – Evals mit Prüfer-Unteragent (entscheidungsvorlage-unordentlich, workflow-*) im Morgenbericht nennen.
- VS Code (Handprüfung): siehe PRUEFUNG.md, Ergebnis von Max eintragen.

## Wichtig: Probe lief nicht (Plan 3 Task 2 Step 7, Ersatzweg)

Der Eval-Lauf brach vor dem ersten Agenten-Schritt ab (Kosten 0 USD, 0 Werkzeugaufrufe). Die beiden "NEIN" oben sind
deshalb **nicht ermittelt**, nicht gemessen. Fehlertext von `claude plugin eval` (Claude Code 2.1.292):

> the Docker (~/.docker, DOCKER_CONFIG) credential store on this machine holds a symbolic link inside it, so the Bash
> sandbox cannot reliably exclude it — a Bash-granting evaluation cannot run here; keep the store's contents in one
> plain directory (its root may be a link)

`DOCKER_CONFIG` zeigte wie im Plan auf einen leeren Ordner (`$TMPDIR/slk-docker-leer`); das Werkzeug prüft trotzdem
auch `~/.docker` – dort liegen in `cli-plugins/` Links von Docker Desktop. Am Rechner wurde nichts geändert. Folge:
Bash-gewährende Evals (alle Kit-Evals) laufen auf diesem Rechner erst, wenn `~/.docker/cli-plugins/` keine Links mehr
enthält oder der Lauf auf einem Rechner ohne Docker Desktop stattfindet. Entscheidung bei Max.

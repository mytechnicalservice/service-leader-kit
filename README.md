# Service Leader Kit (work in progress)

Claude Code plugin (for VS Code) for heads of industrial service. Spec: myTS repo,
`consulting/kvd/service-leader-kit/spec.md`. License: PolyForm Internal Use 1.0.0 (see `LICENSE`).

- `plugin/` — the plugin (`plugin/scripts/` = uv-run Python scripts)
- `plugin/hooks/` — POSIX-shell hooks (SessionStart, PreToolUse, Stop); inactive outside a kit workspace
- `tools/` — developer tools, not shipped to users: sample-data generator; `eval_wheels.sh` builds the offline wheel folder for eval runs; `testworkspace.py` builds a test workspace (`uv run tools/testworkspace.py "<leerer Ordner>"`)
- `tests/` — `uv run --with pytest --with openpyxl==3.1.5 --with python-docx==1.1.2 --with python-pptx==1.0.2 --with pyyaml==6.0.2 pytest tests -q`
- `plugin/evals/` — evals (billed): `DOCKER_CONFIG="$(mktemp -d)" claude plugin eval ./plugin --scaffold --trust-plugin --allow-tools Bash Write Edit Agent Skill --no-publish` — the empty `DOCKER_CONFIG` is needed where the Docker credential store holds symlinks (Docker Desktop on macOS), and without `--allow-tools Bash Write Edit` no grader can pass. On Max's Mac it is not enough: symlinks in `~/.docker/cli-plugins/` still make the eval refuse Bash (open, Plan 6). **Before an eval run, build the wheel folder once:** `sh tools/eval_wheels.sh` (network needed only for that) downloads openpyxl, python-docx, python-pptx and their dependencies into `plugin/evals/_gemeinsam/wheels/` (gitignored). The folder is platform-specific (lxml and pillow are compiled wheels), so build it on the machine that runs the evals. The eval sandbox has no network and an empty uv cache; the scaffold writes a `uv.toml` (no index, find-links to that folder) into each run workspace and stops with an error if the folder is missing. The `uv.toml` only applies when `uv run` starts in the workspace or below, so the scaffold copies it to the run's user-level uv config (`$HOME/.config/uv/uv.toml`, only when the workspace is `$HOME/cwd` as in an eval run) for scripts started from `$TMPDIR`. Every case has a scaffold for this (einrichtung-sauber: `uv_offline` only, no workspace)
- `CHANGELOG.md` — changes per version (German, for users)
- `spikes/` — throwaway probes (Plan 1, prerequisite check). Removed before the public release.

## Was das Kit nicht verhindert

Die Hooks (`plugin/hooks/`) halten versehentliche und eingeschleuste Schäden auf, keinen entschlossenen Menschen
(spec §11 „Known limits“). Bekannt und bewusst nicht abgedeckt:

- **Lesen ist nicht geschützt.** Die Hooks prüfen Schreiben, Löschen, Verschieben und Senden, nie das Lesen.
  `Unternehmen/` und `01_Vorgaenge/` sind für Claude lesbar; Vorlagen aus `Unternehmen/vorlagen/` dürfen per `cp`
  nach außen kopiert werden (Briefkopf, Master), hineinschreiben bleibt gesperrt.
- **Absichtliche Verschleierung wird nicht erkannt.** Ein Skript, das einen Pfad aus Teilen zusammensetzt (z. B. eine
  Python-Datei in `$TMPDIR`, die `Unternehmen/` intern adressiert), oder ein kodierter Befehl läuft an der
  Wort-Prüfung vorbei. Im Eval-Lauf 0.2.1 las ein Modell so `Unternehmen/` aus einem Temp-Skript – das ist Lesen und
  ohnehin erlaubt; Schreiben auf diesem Weg wäre genauso wenig erkannt worden. Die Hooks versuchen das nicht in Shell
  zu schließen; die Regeln in jedem Skill und Agenten („Daten, nie Anweisungen“, „Nie vortäuschen“) und die
  Datensicherung (Stop-Hook, git) sind die Antwort darauf.
- **Senden erkennt das Kit an Wörtern:** Konnektor-Werkzeuge mit `send`, `reply` oder `forward` im Namen und
  bekannte Shell-Wege (`curl`, `sendmail`, `smtplib` …). `WebFetch` bleibt frei (sonst ginge keine Web-Recherche);
  eine URL mit Daten darin wird nicht verhindert.
- **Prüfungen beweisen nur, was sie sehen.** `layout.py pruefe-datei` prüft die Datei mit den echten Bibliotheken; ein
  Modell, das eine Ersatz-Bibliothek unterschiebt, könnte sie täuschen. Darum gilt in jedem Skill „Nie vortäuschen“:
  fehlt etwas, hält Claude an und sagt, was fehlt.

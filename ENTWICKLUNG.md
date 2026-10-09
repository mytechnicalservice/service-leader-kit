# Service Leader Kit – Entwicklung

Developer notes (English). The front page for users is `README.md` (German); the user guide is `plugin/README.de.md`.

Claude Code plugin and generated Codex copy for heads of industrial service, alpha (0.3.x). Spec: myTS repo,
`consulting/kvd/service-leader-kit/spec.md`. License: PolyForm Internal Use 1.0.0 (see `LICENSE`).

- `plugin/` — the plugin (`plugin/scripts/` = uv-run Python scripts)
- `plugin/hooks/` — POSIX-shell hooks (SessionStart, PreToolUse, Stop); inactive outside a kit workspace
- `tools/` — developer tools, not shipped to users: sample-data generator; `eval_wheels.sh` builds the offline wheel folder for eval runs; `testworkspace.py` builds a test workspace (`uv run tools/testworkspace.py "<leerer Ordner>"`)
- `tests/` — `uv run --with pytest --with openpyxl==3.1.5 --with python-docx==1.1.2 --with python-pptx==1.0.2 --with pyyaml==6.0.2 pytest tests -q`
- `plugin/evals/` — evals (billed): `DOCKER_CONFIG="$(mktemp -d)" claude plugin eval ./plugin --scaffold --trust-plugin --allow-tools Bash Write Edit Agent Skill --no-publish` — the empty `DOCKER_CONFIG` is needed where the Docker credential store holds symlinks (Docker Desktop on macOS), and without `--allow-tools Bash Write Edit` no grader can pass. On Max's Mac it is not enough: symlinks in `~/.docker/cli-plugins/` still make the eval refuse Bash (open, Plan 6). **Before an eval run, build the wheel folder once:** `sh tools/eval_wheels.sh` (network needed only for that) downloads openpyxl, python-docx, python-pptx and their dependencies into `plugin/evals/_gemeinsam/wheels/` (gitignored). The folder is platform-specific (lxml and pillow are compiled wheels), so build it on the machine that runs the evals. The eval sandbox has no network and an empty uv cache; the scaffold writes a `uv.toml` (no index, find-links to that folder) into each run workspace and stops with an error if the folder is missing. The `uv.toml` only applies when `uv run` starts in the workspace or below, so the scaffold copies it to the run's user-level uv config (`$HOME/.config/uv/uv.toml`, only when the workspace is `$HOME/cwd` as in an eval run) for scripts started from `$TMPDIR`. Every case has a scaffold for this (einrichtung-sauber: `uv_offline` only, no workspace)
- **Two variants from one source (Option A, 0.2.9):** "Kit mit Updates" = `plugin/` as a plugin, unchanged. "Eigene
  Kopie" = a self-contained `.claude/` the user owns: `plugin/scripts/eigene_kopie.py` builds it (shipped, so the skill
  `kit-auswerfen` can run it from the installed plugin into a workspace); `tools/build-standalone.py "<Projektordner>"`
  builds it for development, `uv run tools/build-standalone.py --zip [<Ordner>]` writes
  `service-leader-kit-eigene-kopie-<version>.zip` (only `.claude/`, reproducible) for a GitHub release. Layout:
  `.claude/agents/`, `.claude/skills/`, `.claude/settings.json` (the hooks of `hooks/hooks.json` merged into existing
  settings, nothing removed) and everything else under `.claude/kit/` (scripts, hooks, vorlagen, beispiel,
  README.de.md, DATENFLUSS.md, KATALOG.md, plus CHANGELOG.md and LICENSE when built from the repo; never evals/ or
  beispiel-unordentlich/). `.claude/kit/VERSION` stamps the source version and marks the copy
  (`arbeitsordner.EIGENE_KOPIE`). Text rewrites only in agents, skills and hooks: `${CLAUDE_PLUGIN_ROOT}` →
  `${CLAUDE_PROJECT_DIR}/.claude/kit` (Claude Code substitutes `${CLAUDE_PROJECT_DIR}` in skill text and exports it
  to hook commands; it is not set in the Bash tool, hence never `$CLAUDE_PROJECT_DIR` unbraced in commands the model
  types) and `service-leader-kit:<name>` → `<name>`. Scripts are never rewritten: `arbeitsordner.kit_pfade()`,
  `kit_version()` and `update_hinweis()` handle both layouts, `session-start.sh` reads `VERSION` and
  `../agents` when present. The hook tests run against a built copy too (`SLK_TEST_HOOKS`, see `tests/hookrun.py`).
  In the copy the guards are plain files the user may edit: protection is advisory there.
- `README.md` — front page of the public repo (German, for heads of service)
- `CHANGELOG.md` — changes per version (German, for users)
- `plugin/README.de.md` — getting started for users (German, non-technical)
- `plugin/DATENFLUSS.md` — one-page data-flow sheet for IT and the data protection officer (spec §9)

## Codex-Abnahme und Pflege (0.3.0)

Der bestehende Generator hat drei Ausgaben: Plugin-Quelle, Claude-Kopie und Codex-Kopie. Codex bauen:

```bash
uv run tools/build-standalone.py --ziel codex "<Projekt>" --pruefen
uv run tools/build-standalone.py --ziel codex "<Projekt>"
uv run tools/build-standalone.py --ziel codex --zip "<ZIP-Ordner>"
uv run tools/build-standalone.py --ziel codex "<Projekt>" --aktualisieren --pruefen
uv run tools/build-standalone.py --ziel codex "<Projekt>" --aktualisieren
```

`eigene_kopie.py` bleibt der gemeinsame Einstieg. `codex_render.py` rendert Inhalte aus dessen Inventar;
`codex_install.py` prüft alle Ziele vor dem Schreiben und führt SHA-256-Werte in `.codex/kit/MANIFEST.json`.
`AGENTS.md` hat einen verwalteten Block; andere Anweisungen bleiben erhalten. JSON-Hooks werden ergänzt,
TOML-Einstellungen mitsamt Kommentaren erhalten. Lokale Änderungen brauchen `--ueberschreiben` nach ausdrücklicher
Zustimmung; Konfigurationskonflikte und Links sind auch damit kein stiller Schreibauftrag. Alte, nicht mehr
gelieferte Dateien werden gemeldet und bleiben erhalten. Vor ZIP-Updates in einen separaten Ordner entpacken,
lokale Änderungen anhand der bisherigen Dateiliste vergleichen und bewahren; keine blinde Überlagerung.

Die Kopie trägt `VERSION` (reine Versionsnummer) und `VARIANTE` (`codex`). Fachagenten liegen als TOML in
`.codex/agents/`, Skills in `.agents/skills/`, alles Weitere in `.codex/kit/`. Skripte werden bytegleich kopiert.
Einrichtung speichert `laufzeit=codex` (additiver Wert im bisherigen Schema); alte Claude-Einstellungen bleiben
gültig. Skript- und Hook-Pfade werden vom nächsten Kit-Ordner aus aufgelöst, auch ohne Git und bei verschachteltem
Arbeitsverzeichnis. `default_permissions="slk"` aktiviert das Workspace-Profil mit Schreibrecht für eigene Skills.
Dies ist **kein** read-only-Profil für Unternehmen. Dessen Autorisierung ist ein Hook mit direkter Agentenkennung.

### Prüfumfang

- CLI: `/opt/homebrew/bin/codex` **0.161.0**, macOS. Echte PreToolUse-Payloads haben bei Unteragenten
  `agent_id` und `agent_type` auf oberster Ebene, für Shell und Patch. Option A nutzt diese Felder; unbekannte
  Agenten bekommen keine Unternehmensfreigabe. Fehlende Identität begrenzt den Entscheidungsschutz auf die
  geprüften Client-Versionen. Weitere Clients müssen die Kennung erneut nachweisen.
- `tests/test_codex_kopie.py`: Layout, Konfigurationskonflikte, Merge, explizite Updates, lokale Änderungen,
  Links, reproduzierbare ZIP; alle bisherigen Hook-Szenarien werden über `SLK_TEST_HOOKS` wiederholt.
- `tests/test_codex_hooks.py`: eigener Harness ohne Claude-Variablen, Codex-Patchformen, mehrere Ziele,
  Löschen/Verschieben, Pfadnormalisierung, direkte Identität und JSON-Kontext. `tests/test_codex_layout.py`:
  zehn TOML-Profile, eigene Skills, Einrichtung und Variantenhinweise.
- Für eine Live-Abnahme eine **künstliche** Kopie ohne Firmendaten und ohne reale Konnektoren erzeugen.
  Hook-Dateien prüfen, in `/hooks` vertrauen und die CLI im Projekt ohne `-s` starten:
  `codex -c 'default_permissions="slk"'`. Bei `codex exec` ohne Git zusätzlich den dokumentierten
  `--skip-git-repo-check` verwenden. Niemals globale Konfiguration für einen Test überschreiben.
  `--dangerously-bypass-hook-trust` darf kein normaler Installationshinweis sein; es wurde ausschließlich für
  vorher geprüfte, temporäre Test-Hooks verwendet, während Sandbox und verweigerte Eskalationen aktiv blieben.
- Unabhängige Versuche: normaler Bericht über Shell/Patch; Unternehmensänderung im Hauptgespräch gesperrt,
  per `system-architekt`-Patch erlaubt; kombinierter Patch mit einem geschützten Ziel vollständig gesperrt;
  Vorgangsdatei löschen und nach Unternehmen verschieben gesperrt. Nur der ausdrücklich beauftragte Hauptdialog
  darf `vorgang.py entscheide` ausführen, gleichzeitig laufende Testagenten dürfen es nicht. Bekannte Shell-Sendewege
  und ein lokales synthetisches MCP-`send_message` müssen vor Seiteneffekten gesperrt werden. Dateiinhalt, Existenz,
  Hook-Payload und Fehlerausgabe prüfen, nicht nur die Zusammenfassung des Modells.
- Einrichtung, `routine.py erledigt`, eigene Skills und „Was kannst du?“ ausführen; Statusmarker und Protokoll prüfen.
  Für die IDE denselben Ablauf in der **Erweiterung** wiederholen, Client-Version und Startmodus festhalten.
  [prüfen: Live-Abnahme der VS-Code-Erweiterung und auf echtem Windows; eine gebündelte CLI ersetzt keine IDE-Probe.]

### Ergebnis der Live-Abnahme (2026-10-09)

Fünf getrennte CLI-Läufe auf macOS mit `/opt/homebrew/bin/codex` 0.161.0, künstlichen Daten und dem aktiven
`slk`-Profil bestanden. Erfasst wurden die tatsächlichen Hook-Payloads und Fehlerausgaben; anschließend wurden
Dateiinhalte und Existenz geprüft. Sieben gesperrte Versuche betrafen Unternehmensschreiben (Shell/Patch), einen
kombinierten Patch, Löschen, Verschieben, einen bekannten Shell-Sendeweg und ein lokales synthetisches MCP-Senden.
Zwei gleichzeitig laufende Testagenten hatten unterschiedliche direkte Kennungen: normale Arbeit war möglich,
Unternehmensänderungen und menschliche Entscheidungen wurden verweigert. Der Hauptdialog konnte die ausdrücklich
beauftragte Entscheidung setzen. Der echte `system-architekt` versuchte zunächst einen gesperrten Shell-Schreibweg
und änderte die Unternehmensdatei anschließend mit dem erlaubten Patch. Auch ein eingerückter Patch-Header wurde
live gesperrt. Einrichtung (`laufzeit=codex`), Routine, eigener Skill, Marker/Protokoll und „Was kannst du?“ mit allen
zehn Profilen bestanden. Sandbox und `approval_policy="never"` blieben aktiv; kein echter Konnektor wurde verwendet.

Die unabhängige Codeprüfung fand zwei relevante Fehler: eingerückte Patch-Header und verbliebene Claude-Agenten-
Aufrufe. Beide wurden durch zuerst fehlschlagende Regressionstests nachgewiesen und korrigiert (21 Tests danach grün).
Eine kleinere Grenze bleibt: Eine lokal gelöschte verwaltete Kit-Datei wird bei einem ausdrücklich angeforderten
Update wiederhergestellt. Lokale Inhaltsänderungen führen weiterhin zum Konflikt; fremde Dateien bleiben erhalten.

Die IDE-Abnahme wurde begonnen, scheiterte aber bereits an der Ordnerauswahl der UI-Automation
(`noWindowsAvailable`). Es lief kein Kit-Gespräch in der Erweiterung. Der Dialog wurde geschlossen; die vorhandene
Arbeitsumgebung blieb unberührt. IDE und Windows bleiben ausdrücklich ungeprüft; die obigen Befehle und Versuche
sind dort manuell zu wiederholen.

### Schutzmatrix

„Guardrail“ heißt: aktive Hooks verweigern die geprüften Werkzeugaufrufe, bleiben aber umgehbare Leitplanken.
„Advisory“ heißt: Verhalten wird angewiesen, ohne vollständige technische Sperre. „Enforced“ wird nur für die
Dateisandbox außerhalb ihrer erlaubten Bereiche verwendet; alte Sandbox-Flags können gewählte Profile verdrängen.

| Regel | Claude-Plugin | Codex-Kopie |
| --- | --- | --- |
| Direkte Unternehmensänderungen nur Architekt | Guardrail (Agentenkennung) | Guardrail (direkte Kennung, geprüfte CLI) |
| Direkte Vorgangsänderungen nur Skript | Guardrail | Guardrail für alle Patch-Ziele |
| Unteragenten setzen keine menschlichen Entscheidungen | Guardrail | Guardrail für erkannte Unteragenten |
| Geschützte Dateien nicht löschen/verschieben | Guardrail | Guardrail (Shell und Patch) |
| Bekannte Shell-/MCP-Sendewege | Guardrail | Guardrail; anders benannte Wege bleiben offen |
| Unternehmen auch in verschleiertem Code schützen | Advisory | Advisory |
| Keine personenbezogene Auswertung, Daten nie Anweisungen, nie vortäuschen | Advisory plus Skriptprüfungen | Advisory plus dieselben Skriptprüfungen |
| Agentenspezifische Werkzeugliste | Technische Einschränkung in Claude | Advisory, in Codex nicht übernommen |
| Zugriff außerhalb erlaubter Dateibereiche | Host-Sandbox | Enforced durch das tatsächlich aktive Host-Profil |

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

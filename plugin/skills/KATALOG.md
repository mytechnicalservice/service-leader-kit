# Skill-Katalog des Service Leader Kits

Alle Skill-Ordner des Kits: 43 Skills (spec §5) und 5 Routinen (spec §8, Entscheidung D11). Ein Ordner unter
`plugin/skills/` muss hier stehen; `tests/test_katalog.py` prüft das. Spalte **Agent** = wer den Skill verantwortet
(`gemeinsam` = von allen genutzt), **Plan** = in welchem Bauplan er entsteht.

| Skill                         | Art     | Agent            | Plan |
| ----------------------------- | ------- | ---------------- | ---- |
| `einrichtung`                 | skill   | system-architekt | 2c   |
| `gesundheitscheck`            | skill   | system-architekt | 2c   |
| `onboarding`                  | skill   | system-architekt | 3    |
| `skill-bauen`                 | skill   | system-architekt | 3    |
| `vorgang`                     | skill   | gemeinsam        | 2c   |
| `vorgaenge-uebersicht`        | skill   | gemeinsam        | 2c   |
| `daten-pruefen`               | skill   | gemeinsam        | 2c   |
| `praesentation`               | skill   | gemeinsam        | 3    |
| `mail-entwurf`                | skill   | gemeinsam        | 3    |
| `entscheidungsvorlage`        | skill   | gemeinsam        | 3    |
| `eskalation-topkunde`         | skill   | betrieb          | 4a   |
| `teamleiter-runde`            | skill   | betrieb          | 4a   |
| `kapazitaet-lage`             | skill   | betrieb          | 4a   |
| `management-report`           | skill   | finanzen         | 4b   |
| `budgetplanung`               | skill   | finanzen         | 4b   |
| `investitionsantrag`          | skill   | finanzen         | 4b   |
| `margen-analyse`              | skill   | finanzen         | 4b   |
| `margen-pruefung`             | skill   | finanzen         | 4b   |
| `reklamation-entscheidung`    | skill   | qualitaet-recht  | 4c   |
| `wiederholfehler-bericht`     | skill   | qualitaet-recht  | 4c   |
| `vertragspruefung`            | skill   | qualitaet-recht  | 4c   |
| `audit-vorbereitung`          | skill   | qualitaet-recht  | 4c   |
| `grossangebot`                | skill   | vertrieb         | 4d   |
| `key-account-review`          | skill   | vertrieb         | 4d   |
| `verlaengerungs-radar`        | skill   | vertrieb         | 4d   |
| `installed-base-potenziale`   | skill   | vertrieb         | 4d   |
| `projektportfolio-ampel`      | skill   | projekte         | 4e   |
| `verzug-entscheidung`         | skill   | projekte         | 4e   |
| `maschinenuebergabe`          | skill   | projekte         | 4e   |
| `serviceprodukt-konzept`      | skill   | angebot          | 4f   |
| `preisliste-update`           | skill   | angebot          | 4f   |
| `portfolio-review`            | skill   | angebot          | 4f   |
| `teilegeschaeft-review`       | skill   | teile            | 4g   |
| `lieferanten-entscheidung`    | skill   | teile            | 4g   |
| `personalplanung`             | skill   | personal         | 4h   |
| `mitarbeitergespraech`        | skill   | personal         | 4h   |
| `skill-matrix`                | skill   | personal         | 4h   |
| `kuendigung-schluesselperson` | skill   | personal         | 4h   |
| `morgen-briefing`             | skill   | assistenz        | 4i   |
| `freigabe-queue`              | skill   | assistenz        | 4i   |
| `wochenplanung`               | skill   | assistenz        | 4i   |
| `besprechung`                 | skill   | assistenz        | 4i   |
| `mail-triage`                 | skill   | assistenz        | 4i   |
| `tagesstart`                  | routine | assistenz        | 5    |
| `wochenstart`                 | routine | assistenz        | 5    |
| `monatsabschluss`             | routine | assistenz        | 5    |
| `quartal`                     | routine | assistenz        | 5    |
| `jahresplanung`               | routine | assistenz        | 5    |

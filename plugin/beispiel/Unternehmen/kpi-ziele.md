---
abweichung_kommentar_prozent: 5
abweichung_kommentar_eur: 5000
abweichung_massnahme_prozent: 10
abweichung_massnahme_eur: 10000
projektampel: {"termin_gelb_ab_tage": 1, "termin_rot_ab_tage": 15, "kosten_gelb_ab_prozent": 5, "kosten_rot_ab_prozent": 10}
kennzahlen:
  - {"name": "Serviceumsatz", "formel": "Summe der Umsatzpositionen (Ist_EUR)", "quelle": "ergebnis", "ziel": 5017860, "einheit": "EUR/Jahr", "richtung": "hoch"}
  - {"name": "DB I-Marge", "formel": "DB I / Serviceumsatz × 100", "quelle": "ergebnis", "ziel": 68, "einheit": "%", "richtung": "hoch"}
  - {"name": "DB II-Marge", "formel": "DB II / Serviceumsatz × 100", "quelle": "ergebnis", "ziel": 32, "einheit": "%", "richtung": "hoch"}
  - {"name": "Lieferfähigkeit Ersatzteile", "formel": "Positionen mit Lieferbar = ja / alle Positionen × 100", "quelle": "ersatzteile", "ziel": 90, "einheit": "%", "richtung": "hoch"}
  - {"name": "Verrechenbarkeit", "formel": "Auftragsstunden / Ist_Stunden × 100", "quelle": "auftraege+kapazitaet", "ziel": 72, "einheit": "%", "richtung": "hoch"}
  - {"name": "Vertragsquote", "formel": "Anlagen mit Vertrag = ja / alle Anlagen × 100", "quelle": "installed_base", "ziel": 62, "einheit": "%", "richtung": "hoch"}
  - {"name": "Durchlaufzeit Aufträge", "formel": "Mittelwert (Abschluss − Eingang) in Tagen", "quelle": "auftraege", "ziel": 2, "einheit": "Tage", "richtung": "niedrig"}
---

# KPIs und Ziele

<!-- antworten -->

Ziele 2026 laut Budget (07_Daten/budget_2026.xlsx). Monatlich im Management-Bericht, Verrechenbarkeit je Team.
<!-- /antworten -->

## Fragen

- Welche Kennzahlen steuerst du (z. B. Serviceumsatz, DB, Erstlösungsquote, Reaktionszeit, Vertragsquote)?
- Wie ist jede Kennzahl genau definiert (Formel, Datenquelle)?
- Welche Ziele gelten für dieses Jahr, pro Monat oder Quartal?

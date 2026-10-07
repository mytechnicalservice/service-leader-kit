---
umsatzarten: ["ersatzteile", "aussendienst", "vertraege", "retrofit", "schulung"]
gewaehrleistung_traeger: service
db1: Umsatz - Material - Fremdleistung
db2: DB I - Personalkosten
ergebnis: DB II - Gewährleistung - Gemeinkostenumlage
gemeinkosten_umlage: "Pauschal 36.500 EUR je Monat für Verwaltung, IT und Gebäude (Vorgabe Controlling)"
verrechnungspreise: "Inbetriebnahme für den Vertrieb 95 EUR je Stunde; interne Reparaturen zu Kosten"
positionen: {"Umsatz Ersatzteile": "ersatzteile", "Umsatz Service": "aussendienst", "Umsatz Verträge": "vertraege", "Umsatz Schulung": "schulung", "Material": "material", "Fremdleistung": "fremdleistung", "Personalkosten": "personal", "Gewährleistung": "gewaehrleistung", "Gemeinkostenumlage": "gemeinkosten"}
geschaeftsjahr_beginn_monat: 1
kalkulationszins_prozent: 8
personal: {"vollkosten_techniker_eur": 82000, "netto_stunden": 1520}
entscheidungsrechte:
  - {"thema": "preise", "allein_bis_eur": 50000, "sonst": "Vertriebsleitung"}
  - {"thema": "kulanz", "allein_bis_eur": 5000, "sonst": "Geschäftsführung"}
  - {"thema": "personal", "allein_bis_eur": null, "sonst": "Geschäftsführung"}
  - {"thema": "investition", "allein_bis_eur": 15000, "sonst": "Geschäftsführung"}
---

# Ergebnisrechnung Service

Die Finanz-Auswertungen rechnen nur mit diesen Definitionen und nennen sie in jedem Bericht.

<!-- antworten -->

Alle fünf Umsatzarten gehören zum Service. Retrofits und Inbetriebnahmen stehen im Ergebnis-Export in "Umsatz Service"; getrennt zeigt sie nur der Auftragsexport (Auftragsart). Gewährleistungskosten trägt der Service (Vorgabe Geschäftsführung 2024).
Kosten stehen im Export mit Minus; DB I und DB II rechnen mit den Beträgen. Personalentscheidungen (Stellen) trifft
immer die Geschäftsführung.
<!-- /antworten -->

## Fragen

- Welche Umsatzarten gehören zum Service (Ersatzteile, Außendienst, Verträge, Retrofits, Schulungen)?
- Wem werden Gewährleistungskosten zugerechnet (Service, Produkt oder Qualität)?
- Welche Verrechnungspreise gelten für interne Leistungen (Inbetriebnahme für den Vertrieb, interne Reparaturen)?
- Wie werden Gemeinkosten umgelegt? Wie sind DB I und DB II definiert?
- Was entscheidest du allein, und was entscheiden Vertrieb, Controlling oder Geschäftsführung (Preise, Kulanz,
  Personal, Investitionen)?

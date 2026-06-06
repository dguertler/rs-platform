# Controlling — Monetarisierung & Business-Steuerung

Dieser Ordner bündelt die **Geschäfts-/Umsatz-Ebene** des Faceless-Instagram-
Projekts „AI Alpha Selection" (getrennt vom technischen Content-Generator unter
`instagram/`). Quelle der Strategie: Gemini-Spezifikation (vom Nutzer eingebracht),
hier strukturiert abgelegt zum Weiterarbeiten über mehrere Sessions.

> **Für eine neue Claude-Session:** Diese drei Dateien lesen, dann hier
> weiterarbeiten. Der Content-/Slide-Generator ist separat in `instagram/`
> dokumentiert (`instagram/CONTEXT.md` §11, `instagram/PROMPT.md`).

## Inhalt
| Datei | Inhalt |
|---|---|
| `MONETARISIERUNG.md` | Die **5 Umsatz-Säulen** (Telegram-SaaS, wikifolio-Fee, Broker-Affiliate, Newsletter, B2B-Sponsoring) — je mit Status & nächsten Schritten |
| `CONTENT_PIPELINE.md` | Die **Traffic-Maschine**: Reels (CapCut + Luma) & Karussell-Workflow + Abgleich mit dem vorhandenen Generator |
| `KPI_MODELL.md` | **Conversion-Funnel & KPI-Matrix** (Pricing-Basis 39 €/Monat) + wöchentliche Tracking-Vorlage |
| `kpi_model.py` | Kleiner Rechner: Funnel-Szenarien → monatliche Neu-Abos, Steady-State-MRR, Gesamtumsatz aller Säulen |

## Wöchentliche Routine (Vorschlag)
1. Ist-Zahlen der Woche in `KPI_MODELL.md` → Tracking-Tabelle eintragen.
2. `python3 controlling/kpi_model.py` laufen lassen → Soll/Szenarien gegen Ist.
3. Engpass im Funnel identifizieren (Reichweite? Profilbesuche? Link-Klicks?
   Free→Paid?) und Content-/CTA-Maßnahme ableiten.

## Status (Stand: Projektaufbau)
- Engine (RS-/Earnings-Scanner, wikifolio +~50 % in 10 Wochen) läuft.
- Instagram-Content-Generator (Karussell + Reel + Caption + Script) steht.
- **Noch nicht live:** Premium-Telegram-Kanal, Gatekeeper-Bot, Affiliate-Links,
  Newsletter. Reihenfolge & Abhängigkeiten siehe `MONETARISIERUNG.md`.

*Hinweis: Alle Zahlen/Annahmen sind Planwerte und wöchentlich gegen die Realität
zu pflegen. Keine Finanz-/Steuerberatung — rechtliche Themen (Telegram-Signale,
§34f/Finanzanalyse-Kennzeichnung, Impressum, Disclaimer) separat prüfen.*

# KPI-Modell & Conversion-Matrix (Pricing-Basis 39 €/Monat)

> Teil 3 der Gemini-Spec („Business Scenario Runtime") — hier als konkrete,
> rechenbare Matrix ausgebaut. Rechner: `python3 controlling/kpi_model.py`.
> **Alle Raten = Planannahmen, wöchentlich gegen Ist pflegen.**

---

## 1. Der Conversion-Funnel (Reels/Karussell → zahlende Abos)

```
Reichweite (Reel-Views + Carousel-Impressions)
        │  × Profilbesuch-Rate
        ▼
Profilbesuche
        │  × Link-Klick-Rate (Linktree/Bio)
        ▼
Linktree-Klicks ───────────────► Broker-Affiliate (Säule 3)
        │  × Telegram-Join-Rate
        ▼
Telegram FREE / Trial
        │  × Free→Paid-Rate
        ▼
Zahlende Abos (39 €/Monat)  ──► − monatliche Churn
```

**Steady-State** (Sättigung): `Abos_stabil = Neu-Abos_pro_Monat ÷ Churn-Rate`.
**MRR** = `Abos × 39 € × (1 − Gebühren)` (Whop/Stripe ≈ 10 % → Netto ~35 €).

## 2. Szenarien (monatlich) — Startannahmen

| Funnel-Stufe | Konservativ | Basis | Optimistisch |
|---|--:|--:|--:|
| Reichweite / Monat | 24.000 | 80.000 | 320.000 |
| → Profilbesuch-Rate | 3,0 % | 4,0 % | 5,0 % |
| → Link-Klick-Rate (v. Reichweite) | 0,5 % | 0,8 % | 1,2 % |
| → Telegram-Join-Rate (v. Klicks) | 40 % | 45 % | 50 % |
| → Free→Paid-Rate | 4 % | 5 % | 6 % |
| Churn / Monat | 8 % | 7 % | 6 % |
| **Neu-Abos / Monat** | **≈ 2** | **≈ 14** | **≈ 115** |
| **Steady-State-Abos** | **≈ 24** | **≈ 206** | **≈ 1.920** |
| **MRR (×35 € netto)** | **≈ 0,8 T€** | **≈ 7,2 T€** | **≈ 67 T€** |

*(Exakte Werte: `kpi_model.py` — Raten dort zentral editierbar.)*

## 3. Umsatz aller 5 Säulen (Monats-Sicht, Basis-Szenario, Planwerte)

| Säule | Formel | Planwert/Monat |
|---|---|--:|
| 1 Telegram-SaaS | Abos × 35 € netto | ~7.200 € |
| 2 wikifolio-Fee | AuM × Jahres-Performance × Fee% ÷ 12 | AuM-abhängig (pflegen) |
| 3 Broker-Affiliate | Depot-Eröffnungen × Ø 40 € | z. B. 10 × 40 € = 400 € |
| 4 Newsletter-Paid | Paid-Abos × 15 € | z. B. 50 × 15 € = 750 € |
| 5 B2B-Sponsoring | feste Slide × Preis (ab 25k Follower) | 0 € (noch nicht aktiv) |

→ Gesamt steuerbar über `kpi_model.py` (Säulen-Inputs editierbar).

## 4. Ziel-Korridore (Daumenregeln zum Gegensteuern)
- **Profilbesuch-Rate < 2 %** → Reel-Hook/erste 3 Sek. schwach → Headline/Thumbnail.
- **Link-Klick-Rate niedrig** → CTA/Bio unklar → klarere Outro-Slide + Linktree.
- **Telegram-Join < 30 %** → Mehrwert des Free-Kanals unklar → bessere Preview.
- **Free→Paid < 3 %** → Signal-Qualität/Trackrecord zeigen, Trial/Rabatt testen.
- **Churn > 8 %** → Signal-Frequenz/Qualität, Community-Bindung erhöhen.

---

## 5. Wöchentliche Tracking-Vorlage (Ist-Werte eintragen)

> Jede Woche eine Zeile ergänzen. Danach `kpi_model.py` mit den Ist-Raten
> gegenrechnen und den schwächsten Funnel-Schritt als Wochen-Fokus wählen.

| KW | Reichweite | Profilbesuche | Neue Follower | Linktree-Klicks | TG Free | TG Paid (neu) | TG Paid (gesamt) | Churn | Affiliate-Depots | NL-Leads | NL-Paid | MRR € | Notiz/Fokus |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 23 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 24 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 25 |  |  |  |  |  |  |  |  |  |  |  |  |  |

**Abgeleitete Ist-Raten** (zum Eintragen/Vergleich mit §2):
- Profilbesuch-Rate = Profilbesuche ÷ Reichweite
- Link-Klick-Rate = Linktree-Klicks ÷ Reichweite
- Telegram-Join-Rate = TG Free ÷ Linktree-Klicks
- Free→Paid-Rate = TG Paid (neu) ÷ TG Free
- Churn = abgewanderte Abos ÷ TG Paid (gesamt Vorwoche)

---

## 6. Annahmen & Caveats
- Frühphasen-Funnel; reale Social-Conversion ist hoch volatil (virale Ausreißer).
- Gebühren (Whop/Stripe/PayPal, USt.) und ggf. Steuer **separat** abziehen.
- wikifolio-Fee braucht echtes AuM; B2B-Sponsoring erst ab Reichweite.
- **Rechtliches** (Signal-Anbieter/Finanzanalyse-Kennzeichnung, Impressum,
  Disclaimer) vor Säule-1-Launch klären — siehe `MONETARISIERUNG.md`.

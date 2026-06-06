# Die 5 Monetarisierungs-Säulen (SaaS & FinTech Layer)

> Quelle: Gemini-Spezifikation (Nutzer-Input). Hier strukturiert + um Status/
> nächste Schritte ergänzt. Pricing-Basis Telegram: **39,00 €/Monat**.

---

## 🏠 Säule 1 — Premium-Telegram-Kanal (Haupt-Umsatztreiber)
- **Produkt:** Automatisierte Kauf-/Verkaufssignale in Echtzeit.
- **Preis:** **39,00 €/Monat** (SaaS-Subscription).
- **Infrastruktur:** Gatekeeper-Bot (**Whop** oder **InviteMember**) — voll-
  automatisches Einladen/Entfernen, gekoppelt an **Stripe/PayPal**.
- **Einzigartige Engine-Features:**
  1. **Relative Stärke (RS):** täglicher Scan NASDAQ & S&P 500 auf Outperformance
     zum Gesamtmarkt. *(im Repo vorhanden: `data/rs_full.json`, `rs_sp500.json`)*
  2. **Earnings-Inflexion:** automatische Erkennung, wenn am Vortag ein
     überdurchschnittlicher Kursanstieg stattfand **UND** beim aktuellen
     Earnings-Termin die EPS-Erwartung um **>10 %** geschlagen wurde.
- **Status:** Engine vorhanden; **Kanal + Bot + Payment noch aufzusetzen**.
- **Nächste Schritte:** (1) Whop/InviteMember-Account + Stripe verbinden,
  (2) Signal-Format definieren (Entry/Stop/Größe/Disclaimer), (3) Telegram-Bot
  an Scanner-Output koppeln, (4) Free-Preview-Kanal als Trichter.
- **Risiko/Recht:** Signal-Anbieter ggf. erlaubnispflichtig (Finanzanalyse/
  Anlageberatung) — **vor Launch rechtlich prüfen**, klaren Disclaimer + „keine
  Anlageberatung" + Risikohinweis verwenden.

## 📈 Säule 2 — wikifolio-Performance-Fee (skalierbares Asset Management)
- **Produkt:** investierbares wikifolio-Zertifikat, das die Engine-Signale live
  umsetzt.
- **Hebel:** „Skin in the Game" / Social Proof. Trackrekord (zu pflegen):
  **~+50 % in ~10 Wochen** (Quelle: `instagram/data/wikifolio_history.json`).
- **Monetarisierung:** Beteiligung an der **Performance-Gebühr** mit steigendem
  AuM (investierte Follower).
- **Status:** wikifolio aktiv, wird bereits wöchentlich beworben (Wochenpost).
- **Nächste Schritte:** AuM-Wachstum tracken; Performance-Fee-Mechanik im
  KPI-Modell führen; wikifolio-Regeln strikt beachten (siehe `instagram/PROMPT.md`
  — keine Zertifikats-Kaufempfehlung, keine ISIN-Bewerbung).

## 🤝 Säule 3 — Broker-Affiliate (Pay-per-Account)
- **Produkt:** Empfehlung von Neo-Brokern (Trade Republic, Scalable Capital …)
  über **Linktree/Bio**.
- **Umsatz:** **20–60 €** einmalige Prämie pro Depot-Eröffnung.
- **Platzierung:** fest auf der **Outro-Slide des wöchentlichen Depot-Updates**.
- **Status:** offen — Affiliate-Programme beantragen.
- **Nächste Schritte:** Affiliate-Zugänge holen; Tracking-Links in Linktree;
  feste Slide/Caption-Zeile im Wochenpost; Conversion pro Broker messen.

## 📧 Säule 4 — Premium-Newsletter (Substack / beehiiv)
- **Produkt:** kostenlose Marktübersicht zum **Lead-Sammeln** (E-Mails) + **Paid
  Tier (10–20 €/Monat)** für extrem tiefe **PDF-Bilanzanalysen** (z. B. die
  AMD-Profi-Analyse aus `analyses/`).
- **Hebel:** die im Repo bereits erzeugten Analysen (`analyses/TICKER.md`) sind
  der fertige Paid-Content — minimaler Zusatzaufwand.
- **Status:** offen.
- **Nächste Schritte:** beehiiv/Substack aufsetzen; Free→Paid-Funnel; Analyse-
  Markdown → PDF-Export-Pipeline (kann Claude bauen).

## 🏷️ Säule 5 — B2B-Sponsorings (ab ~25k Follower)
- **Produkt:** Verkauf einer **festen Werbe-Slide** in den Wochen-Karussells an
  Krypto-Börsen / Chart-Tools (TradingView, Aktienfinder …).
- **Status:** später (Reichweiten-abhängig).
- **Nächste Schritte:** ab ~25k Followern Media-Kit + Preisliste erstellen.

---

## Priorisierung / Abhängigkeiten
1. **Reichweite zuerst** (Reels/Karussell, Säule 0 = Content) → speist alle Säulen.
2. **Säule 3 (Affiliate)** zuerst aktivierbar (kein Produkt nötig, nur Links).
3. **Säule 1 (Telegram)** = Hauptumsatz, aber höchster Aufwand + Rechtsprüfung.
4. **Säule 4 (Newsletter)** parallel — recycelt vorhandene Analysen.
5. **Säule 2 (wikifolio-Fee)** wächst passiv mit AuM/Reichweite.
6. **Säule 5 (Sponsoring)** erst ab Reichweiten-Schwelle.

→ KPI-Steuerung & Umsatz-Szenarien: `KPI_MODELL.md` + `kpi_model.py`.

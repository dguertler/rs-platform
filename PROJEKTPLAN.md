# RS-Platform — Vollständiger Projektplan

**Stand:** Mai 2026  
**Status:** In Entwicklung

---

## 0. Sofort vs. Später — Prioritätsliste

### JETZT SOFORT (vor Launch — nicht verhandelbar)

#### Recht & Steuern
- [ ] Steuerberater engagieren (vor Gründung!)
- [ ] Holding-UG gründen (Notar, 1 EUR Stammkapital)
- [ ] Operative UG gründen (Notar, 1 EUR Stammkapital, 100% Anteile an Holding)
- [ ] Geschäftskonto für beide UGs eröffnen
- [ ] Finanzamt: Steuerliche Erfassung, USt-ID beantragen
- [ ] EU-OSS-Verfahren anmelden (für EU-Auslandskunden)

#### Rechtliche Pflichtseiten (vor erstem Nutzer live)
- [ ] Impressum (§ 5 TMG) — vollständige Anschrift, Verantwortlicher
- [ ] Datenschutzerklärung (DSGVO-konform, alle Dienste gelistet)
- [ ] AGB mit Haftungsausschluss (keine Anlageberatung)
- [ ] Cookiebanner mit echtem Opt-in (keine Pre-Checked-Boxes)
- [ ] Pflicht-Disclaimer auf jeder Seite und in jeder E-Mail
- [ ] AVV (Auftragsverarbeitungsvertrag) mit Stripe, SendGrid/Postmark

#### Technische Sicherheit (vor erstem Nutzer live)
- [ ] HTTPS überall (TLS 1.3)
- [ ] Alle Secrets aus dem Code entfernt → nur noch Environment Variables
- [ ] 2FA auf allen Admin-Accounts aktiviert
- [ ] Rate Limiting auf Auth-Endpunkten
- [ ] Passwort-Hashing: bcrypt (cost factor 12)
- [ ] GitHub Dependabot aktivieren

#### Payments
- [ ] Stripe-Account im Live-Modus (nicht nur Test)
- [ ] Korrekte Rechnungsstellung inkl. USt. (DE 19%, EU je Land)
- [ ] Stripe Webhooks für Abo-Events (zahlung fehlgeschlagen, Kündigung)

#### MVP-Features
- [ ] Ampelsystem live (mindestens DE-Aktien oder S&P 500)
- [ ] Free / Basic / Pro Tier funktionsfähig
- [ ] E-Mail-Alerts funktionsfähig
- [ ] Grundlegendes Dashboard mit Signalübersicht

---

### SPÄTER (nach Launch — erst wenn Nutzer da sind)

#### Nach den ersten 50–100 zahlenden Nutzern
- [ ] Trustpilot-Integration (automatische Anfrage 7 Tage nach Pro-Upgrade)
- [ ] Google Reviews (automatische Anfrage 14 Tage nach Pro-Upgrade)
- [ ] Referral-Programm
- [ ] Feature-Voting-System (braucht Community-Basis)
- [ ] Push-Notifications (Web PWA)

#### Nach Product-Market Fit (500+ Nutzer)
- [ ] API-Zugang (Pro, rate-limited)
- [ ] Backtesting-Interface
- [ ] Englische Version (i18n)
- [ ] Telegram-Bot / Discord-Bot
- [ ] Automatisierte Social-Media-Drafts
- [ ] Newsletter-Automatisierung

#### Langfristig (Jahr 2+)
- [ ] Paper Trading mit Community-Events
- [ ] Mobile App (React Native)
- [ ] DAX, MDAX, NASDAQ, Krypto
- [ ] Internationale Expansion (EN, FR, ES)
- [ ] Algo-Strategie-Marktplatz
- [ ] White-Label für Broker
- [ ] Institutionelle API-Pakete

---

## 1. Vision & Produktidee

Eine SaaS-Plattform für technische Börsensignale, die Privatanleger und aktive Trader mit klaren, datenbasierten Kauf-/Verkaufsempfehlungen unterstützt. Kein Rauschen, kein Lärm — nur ein klares Ampelsystem basierend auf mehrstufiger Zeitrahmenanalyse.

**Kernversprechen:** Institutionelle Signalqualität für den Privatanleger.

---

## 2. Rechtsstruktur & Unternehmensaufbau

### Empfohlene Struktur (von Anfang an)

```
Gründer (Privatperson)
    └── Holding-UG (haftungsbeschränkt)   ← 1 EUR Stammkapital
            └── 100% Gesellschaftsanteile
                    └── Operative-UG (haftungsbeschränkt)   ← Plattform-Betrieb
```

### Warum Holding-Struktur von Tag 1?

Beim späteren Verkauf der operativen Gesellschaft greift **§ 8b KStG (Schachtelprivileg)**:

| Verkaufspreis | Verkauf privat (~26,4%) | Verkauf via Holding (~1,5%) | Ersparnis |
|---|---|---|---|
| €500k | ~€132k Steuer | ~€7.5k | **~€124k** |
| €2M | ~€528k | ~€30k | **~€498k** |
| €10M | ~€2,64M | ~€150k | **~€2,49M** |

**Kosten der Holding:**
- Einmalig: ~€1.500–2.500 (Notar, Gründung)
- Laufend: ~€1.500–3.000/Jahr (Steuerberater, Jahresabschluss)

Break-Even bereits bei Verkaufspreis ~€200k.

### Steuer & Pflichten (Operative UG)

- **Körperschaftsteuer:** 15% auf Gewinn
- **Gewerbesteuer:** ~14% (je nach Gemeinde)
- **Umsatzsteuer:** 19% (DE), EU-OSS-Verfahren für EU-Auslandskunden
- **Impressumspflicht:** § 5 TMG — Pflicht ab Tag 1
- **DSGVO:** Datenschutzerklärung, Cookiebanner, Auftragsverarbeitungsverträge
- **AGB:** Haftungsausschluss für Signale (keine Anlageberatung)
- **Pflichthinweis** auf jeder Seite, in jeder E-Mail:

> *Die auf dieser Plattform bereitgestellten Signale und Analysen stellen keine Anlageberatung, Finanzberatung oder Aufforderung zum Kauf oder Verkauf von Wertpapieren dar. Vergangene Performance ist kein Indikator für zukünftige Ergebnisse. Handel mit Wertpapieren ist mit Risiken verbunden, die zum Totalverlust des eingesetzten Kapitals führen können.*

---

## 3. Ampelsystem (Kernsignal)

### Logik — Mehrstufige Zeitrahmenanalyse

| Signal | Bedingung | Empfehlung |
|---|---|---|
| **GRÜN** | Daily + Weekly + 4H alle bullisch | Kaufen / Halten |
| **GELB** | Daily + Weekly bullisch, 4H bärisch | Halten (kein neuer Einstieg) |
| **ROT** | Alles andere | Ausstieg / Kein Trade |

### 4H-Validierungsschicht

Der 4H-Chart ist als systematische Validierungsschicht implementiert — verhindert Fehlsignale durch temporäre Pullbacks im Tages-Chart. Alle Signale durchlaufen eine Konsistenzprüfung über alle drei Zeitrahmen vor Ausgabe.

### Signalarten

- Trendfolge (MA-Crossover, EMA-Stacks)
- Momentum (RSI, MACD)
- Volatilität (ATR-basierte Einstiege)
- Volumenbestätigung

---

## 4. Preismodell

| Tier | Preis | Inhalt |
|---|---|---|
| **Free** | €0/Monat | 3 Signale/Monat, verzögert (24h), kein Alert |
| **Basic** | €29/Monat | Unbegrenzte Signale, Echtzeit, E-Mail-Alerts |
| **Pro** | €59/Monat | Alles in Basic + Push-Alerts, Backtesting-Zugang, API-Zugang, Priority Support |

**Jahresabo:** 2 Monate gratis (= ~16% Rabatt)

**Saisonale Rabattaktionen:**
- **Black Friday** (letzter Freitag November): 30% auf alle Pläne, 72h gültig
- **Neujahr** (1.–7. Januar): 20% auf Jahresabo ("Frisch starten"-Aktion)

---

## 5. Technischer Stack

### Backend
- **Sprache:** Python (FastAPI)
- **Datenbank:** PostgreSQL
- **Signalberechnung:** Pandas, TA-Lib
- **Scheduling:** Celery + Redis
- **Hosting:** Railway (Backend), Render (Fallback)

### Frontend
- **Framework:** React / Next.js
- **Styling:** Tailwind CSS
- **Charts:** TradingView Lightweight Charts
- **Hosting:** Vercel

### Infrastruktur
- **Auth:** JWT + Refresh Tokens
- **Payments:** Stripe (Subscriptions, Webhooks)
- **E-Mail:** SendGrid / Postmark
- **Monitoring:** Sentry (Errors), Uptime Robot (Availability)

---

## 6. Detaillierter Phasenplan (Roadmap + Marketing)

### Phase 1 — Foundation (Monat 1–2)

**Entwicklung**
- [ ] Redesign Dashboard + Login/Account (Dark Theme)
- [ ] Landing Page (DE) mit FAQ + Preistabelle
- [ ] DSGVO: Impressum, Datenschutz, AGB, Cookie-Banner
- [ ] yfinance 4H Daten-Patch + Validierungsschicht (3-Zeitrahmen-Konsistenzprüfung)
- [ ] FOMO-E-Mail-System (trigger-basiert, max. 1x/Monat)
- [ ] E-Mail-Onboarding-Sequenz (5 E-Mails: Tag 0/1/3/7/14)
- [ ] Freemium-Limits schärfen (Lock-Icons, Upgrade-CTAs)
- [ ] Aktien-Ratings für Top 50 RS-Aktien ausbauen
- [ ] Onboarding-Wizard (3 Schritte nach Registrierung)

**Marketing**
- [ ] Instagram + TikTok Account anlegen, Handle sichern (@rs.trading o.ä.)
- [ ] Erste 10 Posts erstellen (Claude-Drafts, manuell geprüft)

**Ziele**
- [ ] Anwalt für AGB/Disclaimer-Formulierungen beauftragen (~€300)
- [ ] Beta-Nutzer: 50 kostenlose Pro-Accounts vergeben

---

### Phase 1.5 — Launch-Vorbereitung (Monat 2–3)

**Entwicklung**
- [x] Watchlist-Feature (Markierung in den Index-Tabellen + eigene Seite `watchlist.html`
      mit Suche; Zustand im localStorage, Export als `data/watchlist.json` — keine DB,
      da das Frontend statisch ist)
- [x] Watchlist-E-Mails: Breakout-Mail nur noch bei 4H-Auslöser, mit Stopp;
      Verkaufssignal-Mail (`check_exits.py`, täglich) für Watchlist-Titel
- [ ] Earnings-Kalender in Watchlist-E-Mail integrieren
- [ ] Landing Page EN + i18n Frontend
- [ ] Performance-Kennzahlen Section (nach Rechtscheck freischalten)

**Marketing**
- [ ] 3 Posts/Woche Instagram + TikTok (Reels)
- [ ] Reddit-Posts in r/finanzen, r/Boersenhandel
- [ ] 5 Testimonials von Beta-Nutzern einsammeln

**Ziele**
- [ ] Soft-Launch: Erste 200 registrierte Nutzer

---

### Phase 2 — Wachstum (Monat 3–6)

**Entwicklung**
- [ ] Referral-Programm (Stripe Coupons API)
- [ ] Feature-Voting-Bereich (Upvote-System + Punkte/Badges)
- [ ] SEO-Aktien-Seiten (public, indexierbar, gecacht)
- [ ] Claude-API Social-Media-Draft + Freigabe-Workflow
- [ ] Trustpilot + Google Reviews (automatische Anfrage nach Pro-Upgrade)
- [ ] Backtesting-Interface (Pro-only)

**Marketing**
- [ ] Meta Ads starten: €200/Mo, 2 Creatives testen
- [ ] Google Search Ads (Long-Tail Keywords: "Aktiensignale kostenlos" etc.)
- [ ] Erster Micro-Influencer Deal (5–20k Follower, Finance-Nische)
- [ ] Black Friday Aktion (30% Rabatt, 72h)

**Ziele**
- [ ] 100 zahlende Nutzer → ~€1.900 MRR

---

### Phase 3 — Skalierung (Monat 7–18)

**Entwicklung**
- [ ] Paper-Trading-Wettbewerb (Anti-Fake-Design, klarer "kein Echtgeld"-Hinweis)
- [ ] Portfolio-Tracker (echte manuelle Einträge, nur forward-looking)
- [ ] KI-E-Mail-Support (technische Fragen, Claude-API-basiert)
- [ ] Weitere Indizes (EURO STOXX, MDAX, NASDAQ, Krypto)
- [ ] PostgreSQL Migration / Optimierung (bei >3.000 Nutzern)
- [ ] Mobile App (React Native)

**Marketing**
- [ ] Ads-Budget skalieren: €500 → €1.500 → €3.000/Mo
- [ ] EN-Markt aktivieren (UK, NL, Skandinavien)
- [ ] YouTube Pre-Roll Ads
- [ ] Affiliate-Programm (20% recurring Commission)
- [ ] Neujahrs-Aktion (20% auf Jahresabo, 1.–7. Januar)

**Ziele**
- [ ] 500 zahlende Nutzer → ~€9.500 MRR
- [ ] 1.200 zahlende Nutzer → ~€22.800 MRR (passiv skalierend)

---

### Phase 4 — Scaling / Exit-Vorbereitung (Jahr 2–4)

**Entwicklung**
- [ ] API-Zugang für Drittanbieter (Pro, rate-limited)
- [ ] Algo-Strategie-Marktplatz (User-eigene Strategien)
- [ ] White-Label-Option für Broker
- [ ] Institutionelle API-Pakete
- [ ] Internationale Expansion (EN vollständig, FR, ES)

**Ziele**
- [ ] UG → GmbH-Umwandlung (bei ausreichend Kapitalreserve)
- [ ] 2.000–10.000 zahlende Nutzer → €6,6M–€54M Unternehmenswert

---

## 7. Community & Engagement

### Feature-Voting-System

Jeder zahlende Nutzer kann Features vorschlagen und voten.

**Punkte & Belohnungen:**

| Meilenstein | Belohnung |
|---|---|
| Feature vorgeschlagen + umgesetzt (3 Features) | 1 Monat gratis |
| Feature vorgeschlagen + umgesetzt (10 Features) | 1 Jahr gratis |
| Jedes umgesetzte Feature | Permanentes Badge im Profil |

Badges sind dauerhaft sichtbar — auch wenn das Abo endet.

---

## 8. Marketing & Wachstum

### Bewertungen / Social Proof

- **Trustpilot:** Automatische Anfrage 7 Tage nach Pro-Upgrade
- **Google Reviews:** Automatische Anfrage 14 Tage nach Pro-Upgrade
- Keine Anfrage bei Free-Nutzern (zu früh)

### E-Mail-Marketing

- **Frequenz:** Max. 1x/Monat (FOMO/Retention-Emails), Opt-in pflicht
- **Pflicht-Disclaimer** in jeder E-Mail (siehe Abschnitt 2)
- **Transaktional:** Sofort (Signal-Alerts, Passwort-Reset, Rechnungen)
- **Sequences:** Onboarding (5 E-Mails, Tag 0/1/3/7/14), Win-Back (nach 30 Tagen Inaktivität)

### Social Media

- **Strategie:** Automatische Draft-Erstellung aus Signaldaten (kein Autopilot-Posting)
- **Manueller Post:** Alle Drafts werden vor Veröffentlichung manuell geprüft
- **Kanäle:** Twitter/X, LinkedIn, Instagram (Charts), YouTube (Erklärvideos)

### SEO

- Signalseiten als statische/gecachte Seiten (indexierbar)
- Keyword-Cluster: "Aktiensignale", "technische Analyse Software", "Trading Signale kostenlos"
- Blog: Wöchentliche Marktübersichten (SEO + Authority)

---

## 9. IT-Sicherheit

### Basis-Sicherheit
- HTTPS überall (TLS 1.3)
- Passwörter: bcrypt (min. cost factor 12)
- Rate Limiting auf allen Auth-Endpunkten
- Input Validation / SQL Injection Prevention (ORM-only, kein Raw SQL)
- XSS Prevention (CSP-Header, React escaping)

### Admin & Infrastruktur
- Kein Root-Zugang in Produktion
- Secrets nur via Environment Variables (niemals im Code)
- GitHub Secrets für CI/CD
- 2FA für alle Admin-Accounts

### Security Audits (automatisiert, quartalsweise)
- **GitHub Dependabot:** Dependency-Vulnerabilities automatisch
- **OWASP ZAP:** Automatisierter Web-App-Scan
- **Bandit:** Python-Code-Analyse auf Sicherheitslücken

### DSGVO-Compliance
- Datensparsamkeit: Nur notwendige Daten erheben
- Recht auf Löschung: Automatisierter Account-Deletion-Flow
- Datenexport: GDPR-Export-Funktion (JSON)
- Auftragsverarbeitungsvertrag (AVV) mit allen Sub-Processoren (Stripe, SendGrid, etc.)
- Cookiebanner mit Opt-in (keine Pre-Checked-Boxes)

---

## 10. Paper Trading (geplant Phase 3)

### Konzept
Simuliertes Trading auf Basis der Plattformsignale ohne Echtgeld-Risiko.

### Vorteile
- Nutzerbindung erhöht sich stark
- Feature differenziert gegenüber reinen Signaldiensten
- Zeigt Signalqualität transparent (Trust-Builder)
- Community-Events möglich (Wettbewerbe mit Preisen)

### Risiken / Nachteile
- Erhöhter Entwicklungsaufwand (Portfolio-Engine, P&L-Berechnung)
- Nutzer könnten echtes Trading-Ergebnis mit Paper-Ergebnis verwechseln
- Regulatorisch: Klarer Hinweis "kein Echtgeld" überall notwendig

**Entscheidung:** Implementierung ab Phase 3, nach solidem Track-Record der Live-Signale.

---

## 11. Plattformbewertung nach Ausbaustufen

Bewertungsbasis: SaaS ARR-Multiple. Annahme: Ø €45/Monat je zahlendem Nutzer.

### Stufe 1 — MVP / Launch (Monat 0–6)
- Zahlende Nutzer: 0–100
- ARR: €0 – €54k
- **Bewertung: €100k – €250k** (Substanzwert: Code + Konzept)

### Stufe 2 — Early Traction (Monat 6–18)
- Zahlende Nutzer: 100–500
- ARR: €54k – €270k
- Multiple: 3–5x
- **Bewertung: €200k – €1,3M**

### Stufe 3 — Product-Market Fit (Jahr 2–3)
- Zahlende Nutzer: 500–2.000
- ARR: €270k – €1,1M
- Multiple: 5–8x
- **Bewertung: €1,3M – €8,8M**
- UG → GmbH-Umwandlung in dieser Phase

### Stufe 4 — Scaling (Jahr 3–5)
- Zahlende Nutzer: 2.000–10.000
- ARR: €1,1M – €5,4M
- Multiple: 6–10x
- **Bewertung: €6,6M – €54M**
- Potenzielle Käufer: Trade Republic, eToro, Finanzen.net, Onvista, Bloomberg-ähnliche

### Stufe 5 — Strategischer Exit (Jahr 5+)
- Zahlende Nutzer: 10.000+
- ARR: €5,4M+
- Strategischer Aufschlag (Daten, Brand, Nutzerbasis): 2–3x Premium
- **Bewertung: €30M – €100M+**

### Wertreiber die den Multiple erhöhen
1. Monatliche Churn-Rate < 3%
2. Nachgewiesener Signal-Track-Record (12+ Monate Live-Daten)
3. Starke Community / Brand (Newsletter, Telegram, YouTube)
4. Datenschatz (historische Signale, Nutzerverhalten)
5. Internationale Expansion (EN-Version live)
6. Strategischer Fit mit möglichem Käufer

### Steuerersparnis Holding bei Exit (Erinnerung)

Bei einem Exit von €10M:
- Ohne Holding: ~€2,64M Steuer
- Mit Holding: ~€150k Steuer
- **Ersparnis: ~€2,49M**

---

## 12. Erfolgskennzahlen (KPIs)

| Kennzahl | Ziel Phase 1 | Ziel Phase 2 | Ziel Phase 3 |
|---|---|---|---|
| Zahlende Nutzer | 50 | 300 | 1.000 |
| MRR | €2k | €13k | €45k |
| Monatl. Churn | < 10% | < 6% | < 3% |
| Free-to-Paid Conversion | 5% | 8% | 12% |
| NPS | > 30 | > 45 | > 60 |
| Signal-Accuracy (Live) | Messung starten | > 55% | > 60% |

---

## 13. Instagram-Marketing (AI Alpha Selection)

Faceless-Account zur Bewerbung des wikifolios „AI Alpha Selection".
Technik & Ablauf: **`instagram/PROMPT.md`** (Generator unter `instagram/`).

- **Phase 1 (jetzt):** Wöchentliches **Carousel (4:5)** aus dem wikifolio-
  Wochenreport, automatisch generiert, manueller Upload nach Kontrolle.
  Reel-Frames (9:16) entstehen parallel aus derselben Pipeline.
- **Phase 2 (bei genügend Followern):** **Stories** für kurze Updates;
  Reel-Animation aus den 9:16-Frames (ffmpeg).
- **Phase 3 (optional):** Auto-Upload via Instagram Graph API (Business-Account),
  erst nach finalem Design + rechtlicher Freigabe.
- **Recht:** strikte Trennung Musterdepot/Zertifikat, keine ISIN, kein
  wikifolio-Logo ohne Freigabe, Pflicht-Disclaimer (in PROMPT.md verankert).

---

*Dieses Dokument ist ein lebendes Dokument und wird mit jeder Entwicklungsphase aktualisiert.*

#!/usr/bin/env python3
"""
KPI-/Umsatz-Rechner für das Faceless-Instagram-System (AI Alpha Selection).

Rechnet den Conversion-Funnel (Reichweite -> zahlende 39 €-Abos) für drei
Szenarien plus die Umsätze aller 5 Säulen. Reine Planwerte — Raten unten
zentral editieren oder Ist-Werte gegenrechnen.

    python3 controlling/kpi_model.py

Doku/Hintergrund: controlling/KPI_MODELL.md
"""

PRICE = 39.0          # €/Monat Telegram-Abo
FEE = 0.10            # Whop/Stripe/PayPal-Anteil (-> Netto = PRICE*(1-FEE))
NET = PRICE * (1 - FEE)

# ── Funnel-Szenarien (monatlich) ───────────────────────────────────────────────
# Pfad zu Paid: Reichweite × link_click → Klicks × tg_join → Free × free2paid → Paid
SCENARIOS = {
    "Konservativ": dict(reach=24_000, profile_visit=0.030, link_click=0.005,
                        tg_join=0.40, free2paid=0.04, churn=0.08),
    "Basis":       dict(reach=80_000, profile_visit=0.040, link_click=0.008,
                        tg_join=0.45, free2paid=0.05, churn=0.07),
    "Optimistisch":dict(reach=320_000, profile_visit=0.050, link_click=0.012,
                        tg_join=0.50, free2paid=0.06, churn=0.06),
}

# ── Weitere Säulen (Planwerte, editierbar) ─────────────────────────────────────
PILLARS = dict(
    # Säule 2: wikifolio Performance-Fee (Monats-Anteil) = AuM × Jahres-Perf × Fee% / 12
    wikifolio_aum=0.0, wikifolio_perf=0.20, wikifolio_fee=0.10,
    # Säule 3: Broker-Affiliate
    affiliate_signups=10, affiliate_eur=40.0,
    # Säule 4: Newsletter Paid
    newsletter_paid=50, newsletter_eur=15.0,
    # Säule 5: B2B-Sponsoring (ab ~25k Follower)
    sponsoring_eur=0.0,
)


def funnel(s):
    visits = s["reach"] * s["profile_visit"]
    clicks = s["reach"] * s["link_click"]
    tg_free = clicks * s["tg_join"]
    new_paid = tg_free * s["free2paid"]
    steady = new_paid / s["churn"] if s["churn"] else 0.0
    return dict(visits=visits, clicks=clicks, tg_free=tg_free,
                new_paid=new_paid, steady=steady, mrr=steady * NET)


def pillar_revenue(p, telegram_mrr):
    wf = p["wikifolio_aum"] * p["wikifolio_perf"] * p["wikifolio_fee"] / 12
    aff = p["affiliate_signups"] * p["affiliate_eur"]
    nl = p["newsletter_paid"] * p["newsletter_eur"]
    sp = p["sponsoring_eur"]
    return dict(telegram=telegram_mrr, wikifolio=wf, affiliate=aff,
                newsletter=nl, sponsoring=sp,
                total=telegram_mrr + wf + aff + nl + sp)


def eur(x):
    return f"{x:,.0f} €".replace(",", ".")


def main():
    print(f"\nKPI-Modell · Telegram {PRICE:.0f} €/Monat · Netto {NET:.2f} € "
          f"(nach {FEE:.0%} Gebühren)\n" + "=" * 64)
    print(f"{'Szenario':<14}{'Klicks':>9}{'TG free':>9}{'Neu-Abos':>10}"
          f"{'Steady':>9}{'MRR':>12}")
    print("-" * 64)
    base_mrr = 0.0
    for name, s in SCENARIOS.items():
        f = funnel(s)
        if name == "Basis":
            base_mrr = f["mrr"]
        print(f"{name:<14}{f['clicks']:>9.0f}{f['tg_free']:>9.0f}"
              f"{f['new_paid']:>10.1f}{f['steady']:>9.0f}{eur(f['mrr']):>12}")

    print("\nUmsatz aller Säulen (Basis-Szenario Telegram-MRR + Planwerte)\n"
          + "=" * 64)
    rev = pillar_revenue(PILLARS, base_mrr)
    labels = {"telegram": "1 Telegram-SaaS", "wikifolio": "2 wikifolio-Fee",
              "affiliate": "3 Broker-Affiliate", "newsletter": "4 Newsletter",
              "sponsoring": "5 B2B-Sponsoring"}
    for k, lab in labels.items():
        print(f"  {lab:<22}{eur(rev[k]):>14}")
    print("-" * 40)
    print(f"  {'GESAMT / Monat':<22}{eur(rev['total']):>14}")
    print(f"  {'GESAMT / Jahr':<22}{eur(rev['total'] * 12):>14}\n")
    print("Raten/Inputs oben im Skript editieren · Details: "
          "controlling/KPI_MODELL.md\n")


if __name__ == "__main__":
    main()

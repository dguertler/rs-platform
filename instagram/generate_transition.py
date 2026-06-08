"""
Erstellt einen einzelnen Erklär-Slide (Carousel 4:5) der den Wechsel von
manuellem Momentum-Trading zu AI Alpha Selection visualisiert.

Aufruf:
    python3 -m instagram.generate_transition
    python3 -m instagram.generate_transition --date 2026-04-04 --out out/instagram/transition
"""
import argparse
import os
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt

from . import render, theme as T
from .render import Canvas, MX, fmt_pct, short_date, header, footer, _style_chart

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Manuelle Phase – Wochenwerte aus Excel (G:I), Spalte I = EUR-Wert, Spalte G = Datum
MANUAL_DATA = [
    ("2026-02-09", 108.90),
    ("2026-02-16", 108.90),
    ("2026-02-23", 107.25),
    ("2026-03-02", 109.57),
    ("2026-03-09", 109.35),
    ("2026-03-16", 109.35),
    ("2026-03-23", 106.08),
]

# Transition-Datum (Restrukturierung des Depots)
TRANSITION_DATE = "2026-03-30"
TRANSITION_VALUE = 98.48

# AI Alpha Startdaten (aus wikifolio_history.json)
AI_DATA_RAW = [
    # date → wikifolio_history.json Einträge KW14-KW23
]


def _load_ai_data():
    """Lädt AI Alpha Werte aus wikifolio_history.json."""
    import json
    path = os.path.join(ROOT, "instagram", "data", "wikifolio_history.json")
    with open(path) as f:
        hist = json.load(f)
    weekly = sorted(hist["weekly"], key=lambda w: w["kw"])
    return [(w["date"], w["value"]) for w in weekly if "date" in w]


def slide_transition(c, date_iso, ai_data, nasdaq_ret=None):
    """Transition-Erklär-Slide im Stil der Wochenberichte."""
    header(c, date_iso)

    # ── Titel ────────────────────────────────────────────────────────────────
    c.text(MX, 196, "Strategiewechsel — 30. März 2026", render.TY_H1,
           weight="bold")
    c.text(MX, 248, "Manuelles Momentum-Trading → KI-gestützte Aktienauswahl",
           render.TY_SUB, color=T.MUTED)

    # ── Daten aufbereiten ────────────────────────────────────────────────────
    man_dates = [d for d, _ in MANUAL_DATA]
    man_vals = [v for _, v in MANUAL_DATA]

    # Verbindungspunkt: letzter manueller Wert → Transition-Dip
    bridge_dates = [man_dates[-1], TRANSITION_DATE]
    bridge_vals = [man_vals[-1], TRANSITION_VALUE]

    # AI Alpha Werte (Start = Transition-Value am 30.03.)
    ai_dates = [TRANSITION_DATE] + [d for d, _ in ai_data]
    ai_vals = [TRANSITION_VALUE] + [v for _, v in ai_data]

    def to_x(dates):
        return np.array([datetime.strptime(d, "%Y-%m-%d").toordinal()
                         for d in dates], float)

    mx = to_x(man_dates)
    bx = to_x(bridge_dates)
    ax_ = to_x(ai_dates)
    all_dates = man_dates + ai_dates[1:]
    all_x = to_x(all_dates)
    all_vals = man_vals + ai_vals[1:]

    # ── Chart ────────────────────────────────────────────────────────────────
    chart_h = 410
    chart_top = 290
    ax = c.chart_axes(MX, chart_top, c.W - 2 * MX, chart_h)
    _style_chart(ax)

    ymin = min(min(all_vals), TRANSITION_VALUE) - 5
    ymax = max(all_vals) + 6
    ax.set_ylim(ymin, ymax)

    # Manueller Bereich (grau gestrichelt) + Füllung
    ax.plot(mx, man_vals, color=T.MUTED, lw=3.5, linestyle="--",
            solid_capstyle="round", zorder=3, label="Manuelles Trading")
    ax.fill_between(mx, man_vals, ymin,
                    color=T.MUTED, alpha=0.07, zorder=1)

    # Brücke zur Restrukturierung (gepunktete Linie)
    ax.plot(bx, bridge_vals, color=T.MUTED, lw=1.5, linestyle=":",
            alpha=0.5, zorder=2)

    # AI Alpha Bereich (grün) + Füllung
    ax.plot(ax_, ai_vals, color=T.GREEN, lw=4,
            solid_capstyle="round", zorder=4, label="AI Alpha Selection")
    ax.fill_between(ax_, ai_vals, ymin,
                    color=T.GREEN, alpha=0.10, zorder=1)

    # Vertikale Trennlinie "KI übernimmt"
    trans_x = datetime.strptime(TRANSITION_DATE, "%Y-%m-%d").toordinal()
    ax.axvline(trans_x, color=T.BLUE, lw=2, linestyle="--", alpha=0.9, zorder=5)

    # Beschriftung der Trennlinie
    ax.text(trans_x + (ax_.max() - ax_.min()) * 0.01,
            ymin + (ymax - ymin) * 0.68,
            "30.03.2026\nKI übernimmt",
            color=T.BLUE, fontsize=9, va="center", ha="left",
            fontfamily=render._FONTS["sans"], fontweight="bold",
            bbox=dict(facecolor=T.BG, edgecolor="none", pad=2))

    # Restrukturierungs-Annotation
    ax.annotate(
        "Depot-Neuaufstellung\n(Einmaleffekt)",
        xy=(trans_x, TRANSITION_VALUE),
        xytext=(trans_x - (ax_.max() - ax_.min()) * 0.22,
                TRANSITION_VALUE + (ymax - ymin) * 0.12),
        color=T.MUTED, fontsize=8,
        fontfamily=render._FONTS["sans"],
        arrowprops=dict(arrowstyle="->", color=T.MUTED, lw=1.2),
        ha="right",
    )

    # Datums-Achsenbeschriftungen: Monate
    from matplotlib.ticker import FixedLocator
    month_labels = []
    seen = set()
    for d in all_dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        key = (dt.year, dt.month)
        if key not in seen:
            seen.add(key)
            month_labels.append((dt.toordinal(), dt.strftime("%b '%y")
                                 .replace("Feb", "Feb").replace("Mar", "Mär")
                                 .replace("Apr", "Apr").replace("May", "Mai")
                                 .replace("Jun", "Jun")))
    ax.set_xticks([x for x, _ in month_labels])
    ax.set_xticklabels([lbl for _, lbl in month_labels],
                       fontsize=8, color=T.MUTED,
                       fontfamily=render._FONTS["sans"])
    ax.tick_params(axis="x", bottom=True, labelbottom=True,
                   colors=T.MUTED, length=4, width=1)

    # Legende
    def _leg(ya, col, lbl, ls="solid"):
        ax.plot([0.02, 0.07], [ya, ya], transform=ax.transAxes,
                color=col, lw=3, linestyle=ls, solid_capstyle="round",
                clip_on=False)
        ax.text(0.09, ya, lbl, transform=ax.transAxes, color=col,
                fontsize=10, va="center", fontweight="bold",
                fontfamily=render._FONTS["sans"])

    _leg(0.95, T.GREEN, "AI Alpha Selection")
    _leg(0.86, T.MUTED, "Manuelles Trading", ls="dashed")

    # ── KPI-Streifen ─────────────────────────────────────────────────────────
    ky = chart_top + chart_h + 52
    gap = 24
    third = (c.W - 2 * MX - 2 * gap) // 3
    ch = 120

    # Manuell-Performance (Feb9 → März23, ohne Restrukturierungsdip)
    man_ret = MANUAL_DATA[-1][1] / MANUAL_DATA[0][1] - 1   # 106.08/108.9 - 1 = -2.6%
    # AI Alpha Performance (März30 → letzter KW-Wert)
    ai_ret = ai_vals[-1] / TRANSITION_VALUE - 1            # 149.86/98.48 - 1 = +52.2%
    ai_weeks = len(ai_data)

    nasdaq_str = fmt_pct(nasdaq_ret) if nasdaq_ret is not None else "—"
    kpis = [
        ("Manuell · 6 Wochen", fmt_pct(man_ret), T.MUTED),
        (f"AI Alpha · {ai_weeks} Wochen", fmt_pct(ai_ret), T.GREEN),
        (f"NASDAQ-100 · {ai_weeks} Wochen", nasdaq_str, T.BLUE),
    ]
    for i, (lbl, val, col) in enumerate(kpis):
        x = MX + i * (third + gap)
        c.tile(x, ky, third, ch, color=T.PANEL)
        c.text(x + 22, ky + 22, lbl, 15, color=T.MUTED)
        c.text(x + 22, ky + 50, val, 36, color=col, weight="bold", font="mono")

    # ── Erklärtext ───────────────────────────────────────────────────────────
    ty = ky + ch + 26
    lines = [
        "Bis März 2026: manuelles Momentum-Trading. Seit 30.03.2026:",
        "KI-gestützte Selektion (Relative Stärke + Fundamentals).",
    ]
    for i, ln in enumerate(lines):
        c.text(MX, ty + i * 32, ln, 21, color=T.MUTED)

    footer(c)


def _nasdaq_ret_over_period(start_iso, end_iso):
    """Berechnet NASDAQ-Rendite zwischen zwei Daten aus den Repo-Daten."""
    try:
        from . import data as _data
        _, benchmark = _data.load_universe()
        bench = list(benchmark)
        def qqq_on(d):
            v = None
            for date_str, c in bench:
                if date_str <= d:
                    v = c
                else:
                    break
            return v
        v0, v1 = qqq_on(start_iso), qqq_on(end_iso)
        return (v1 / v0 - 1) if v0 and v1 else None
    except Exception:
        return None


def build_transition(fmt="carousel", date_iso=None, outdir=None):
    ai_data = _load_ai_data()
    nasdaq_ret = _nasdaq_ret_over_period(TRANSITION_DATE,
                                         ai_data[-1][0] if ai_data else TRANSITION_DATE)
    if date_iso is None:
        from datetime import date
        date_iso = date.today().isoformat()
    if outdir is None:
        outdir = os.path.join(ROOT, "out", "instagram", f"{date_iso}_TRANSITION")
    os.makedirs(outdir, exist_ok=True)

    c = Canvas(fmt)
    slide_transition(c, date_iso, ai_data, nasdaq_ret=nasdaq_ret)
    path = os.path.join(outdir, "01_transition.png")
    c.save(path)
    print(f"✓ Transition-Slide gespeichert: {os.path.relpath(path, ROOT)}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None,
                    help="Slide-Datum (YYYY-MM-DD). Standard: heute.")
    ap.add_argument("--out", default=None,
                    help="Ausgabe-Verzeichnis. Standard: out/instagram/<DATUM>_TRANSITION/")
    ap.add_argument("--format", choices=["carousel", "reel"], default="carousel")
    args = ap.parse_args()
    build_transition(fmt=args.format, date_iso=args.date, outdir=args.out)


if __name__ == "__main__":
    main()

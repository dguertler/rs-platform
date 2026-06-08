"""
Erstellt einen einzelnen Erklär-Slide (Carousel 4:5) der den Wechsel von
manuellem Momentum-Trading zu AI Alpha Selection visualisiert.

Aufruf:
    python3 -m instagram.generate_transition
    python3 -m instagram.generate_transition --date 2026-04-04
"""
import argparse
import os
from datetime import datetime

import numpy as np

from . import render, theme as T
from .render import Canvas, MX, fmt_pct, header, footer, _style_chart

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Manuelle Phase – Wochenwerte aus Excel (G:I)
MANUAL_DATA = [
    ("2026-02-09", 108.90),
    ("2026-02-16", 108.90),
    ("2026-02-23", 107.25),
    ("2026-03-02", 109.57),
    ("2026-03-09", 109.35),
    ("2026-03-16", 109.35),
    ("2026-03-23", 106.08),
]

TRANSITION_DATE  = "2026-03-30"
TRANSITION_VALUE = 98.48   # Startwert AI Alpha (nach Restrukturierung)


def _load_ai_data():
    import json
    path = os.path.join(ROOT, "instagram", "data", "wikifolio_history.json")
    with open(path) as f:
        hist = json.load(f)
    weekly = sorted(hist["weekly"], key=lambda w: w["kw"])
    return [(w["date"], w["value"]) for w in weekly if "date" in w]


def _load_nasdaq_normalized(start_iso, end_iso, base_value):
    """NASDAQ-Kursdaten normalisiert auf base_value am start_iso."""
    try:
        from . import data as _data
        _, benchmark = _data.load_universe()
        bench = list(benchmark)
        base = None
        for d, c in bench:
            if d <= start_iso:
                base = c
        if not base:
            return [], []
        dates, vals = [], []
        for d, c in bench:
            if start_iso <= d <= end_iso:
                dates.append(d)
                vals.append(c / base * base_value)
        return dates, vals
    except Exception:
        return [], []


def _nasdaq_ret(start_iso, end_iso):
    try:
        from . import data as _data
        _, benchmark = _data.load_universe()
        bench = list(benchmark)
        v0 = v1 = None
        for d, c in bench:
            if d <= start_iso:
                v0 = c
            if d <= end_iso:
                v1 = c
        return (v1 / v0 - 1) if v0 and v1 else None
    except Exception:
        return None


def slide_transition(c, date_iso, ai_data, nasdaq_ret=None):
    """Transition-Erklär-Slide im Stil der Wochenberichte."""
    header(c, date_iso)

    # ── Titel ────────────────────────────────────────────────────────────────
    c.text(MX, 175, "Strategiewechsel — 30. März 2026",
           render.TY_H1, weight="bold")

    # Vor/Nach als zwei Boxen mit großem Pfeil dazwischen
    box_h = 58
    box_y = 228
    box_w = int((c.W - 2 * MX - 80) * 0.46)
    arrow_cx = MX + box_w + 40

    c.tile(MX, box_y, box_w, box_h, color=T.PANEL)
    c.text(MX + 22, box_y + 10, "VOR DEM 30.03.2026", 13, color=T.MUTED)
    c.text(MX + 22, box_y + 30, "Manuelles Momentum-Trading", 19, color=T.MUTED)

    # Großer Pfeil mittig
    c.text(arrow_cx, box_y + 2, "→", 50, color=T.BLUE, weight="bold", ha="center")

    right_x = MX + box_w + 80
    right_w = c.W - MX - right_x
    c.tile(right_x, box_y, right_w, box_h, color=T.PANEL_HI)
    c.text(right_x + 22, box_y + 10, "AB 30.03.2026", 13, color=T.GREEN)
    c.text(right_x + 22, box_y + 30, "KI-gestützte Aktienauswahl", 19,
           color=T.TEXT, weight="bold")

    # ── Chart-Vorbereitung ───────────────────────────────────────────────────
    man_dates = [d for d, _ in MANUAL_DATA]
    man_vals  = [v for _, v in MANUAL_DATA]

    ai_dates = [TRANSITION_DATE] + [d for d, _ in ai_data]
    ai_vals  = [TRANSITION_VALUE]  + [v for _, v in ai_data]

    end_iso = ai_dates[-1] if ai_dates else TRANSITION_DATE
    nas_dates, nas_vals = _load_nasdaq_normalized(TRANSITION_DATE, end_iso, TRANSITION_VALUE)

    def to_x(dates):
        return np.array([datetime.strptime(d, "%Y-%m-%d").toordinal()
                         for d in dates], float)

    mx   = to_x(man_dates)
    bx   = to_x([man_dates[-1], TRANSITION_DATE])   # Brücke Restrukturierung
    bv   = [man_vals[-1], TRANSITION_VALUE]
    ax_  = to_x(ai_dates)
    nas_x = to_x(nas_dates) if nas_dates else np.array([])

    ymin = min(min(man_vals), TRANSITION_VALUE, *(nas_vals or [99])) - 4
    ymax = max(max(man_vals), max(ai_vals), *(nas_vals or [100])) + 8

    # ── Chart ────────────────────────────────────────────────────────────────
    chart_h   = 400
    chart_top = 305
    ax = c.chart_axes(MX, chart_top, c.W - 2 * MX, chart_h)
    _style_chart(ax)
    ax.set_ylim(ymin, ymax)

    # Manueller Bereich (grau gestrichelt)
    ax.plot(mx, man_vals, color=T.MUTED, lw=3, linestyle="--",
            solid_capstyle="round", zorder=3)
    ax.fill_between(mx, man_vals, ymin, color=T.MUTED, alpha=0.07, zorder=1)

    # Brücke zur Restrukturierung (gepunktet)
    ax.plot(to_x([man_dates[-1], TRANSITION_DATE]), bv,
            color=T.MUTED, lw=1.5, linestyle=":", alpha=0.5, zorder=2)

    # NASDAQ (blau) ab Transition
    if nas_dates:
        ax.plot(nas_x, nas_vals, color=T.BLUE, lw=2.5,
                solid_capstyle="round", zorder=3, alpha=0.9)
        ax.fill_between(nas_x, nas_vals, ymin,
                        color=T.BLUE, alpha=0.06, zorder=1)

    # AI Alpha (grün) ab Transition
    ax.plot(ax_, ai_vals, color=T.GREEN, lw=4,
            solid_capstyle="round", zorder=4)
    ax.fill_between(ax_, ai_vals, ymin, color=T.GREEN, alpha=0.10, zorder=1)

    # Vertikale Trennlinie
    trans_x = datetime.strptime(TRANSITION_DATE, "%Y-%m-%d").toordinal()
    x_range = (ax_.max() - mx.min()) if (len(ax_) and len(mx)) else 1
    ax.axvline(trans_x, color=T.BLUE, lw=1.8, linestyle="--", alpha=0.85, zorder=5)

    # "KI übernimmt"-Label RECHTS vom Transition-Strich (im oberen Drittel)
    ax.text(trans_x + x_range * 0.013,
            ymin + (ymax - ymin) * 0.82,
            "30.03.\nKI übernimmt",
            color=T.BLUE, fontsize=8.5, va="top", ha="left",
            fontfamily=render._FONTS["sans"], fontweight="bold")

    # Legende
    def _leg(ya, col, lbl, ls="solid"):
        ax.plot([0.02, 0.065], [ya, ya], transform=ax.transAxes,
                color=col, lw=3, linestyle=ls, solid_capstyle="round", clip_on=False)
        ax.text(0.08, ya, lbl, transform=ax.transAxes, color=col,
                fontsize=9.5, va="center", fontweight="bold",
                fontfamily=render._FONTS["sans"])
    _leg(0.96, T.GREEN, "AI Alpha Selection")
    if nas_dates:
        _leg(0.88, T.BLUE, "NASDAQ-100")
    _leg(0.80, T.MUTED, "Manuelles Trading", ls="dashed")

    # X-Achsen-Beschriftungen (Monate)
    seen_months = set()
    xticks, xlabels = [], []
    all_dates = man_dates + ai_dates[1:]
    for d in all_dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        key = (dt.year, dt.month)
        if key not in seen_months:
            seen_months.add(key)
            xticks.append(dt.toordinal())
            lbl = dt.strftime("%b").replace("Feb","Feb").replace("Mar","Mär") \
                     .replace("Apr","Apr").replace("May","Mai").replace("Jun","Jun")
            xlabels.append(f"{lbl} '{str(dt.year)[2:]}")
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, fontsize=8.5, color=T.MUTED,
                       fontfamily=render._FONTS["sans"])
    ax.tick_params(axis="x", bottom=True, labelbottom=True,
                   colors=T.MUTED, length=4, width=1)

    # ── KPI-Streifen: Manuell / AI Alpha / NASDAQ ────────────────────────────
    ky  = chart_top + chart_h + 44
    gap = 22
    ch  = 118
    third = (c.W - 2 * MX - 2 * gap) // 3

    man_ret = MANUAL_DATA[-1][1] / MANUAL_DATA[0][1] - 1      # -2.6%
    ai_ret  = ai_vals[-1] / TRANSITION_VALUE - 1               # +52.2%
    ai_weeks = len(ai_data)
    nas_str = fmt_pct(nasdaq_ret) if nasdaq_ret is not None else "—"

    kpis = [
        ("Manuell · 6 Wochen",           fmt_pct(man_ret), T.MUTED),
        (f"AI Alpha · {ai_weeks} Wochen", fmt_pct(ai_ret),  T.GREEN),
        (f"NASDAQ-100 · {ai_weeks}W",     nas_str,           T.BLUE),
    ]
    for i, (lbl, val, col) in enumerate(kpis):
        x = MX + i * (third + gap)
        c.tile(x, ky, third, ch, color=T.PANEL)
        c.text(x + 20, ky + 20, lbl, 14, color=T.MUTED)
        c.text(x + 20, ky + 50, val, 38, color=col, weight="bold", font="mono")

    # ── Erklärtext (weiß, jeder Satz eigene Zeile, gut lesbar) ──────────────
    ty = ky + ch + 28
    lines = [
        "Bis März 2026: manuelles Momentum-Trading — flat, kein System.",
        "Seit 30.03.2026: KI selektiert nach Relativer Stärke und Fundamentals.",
        "Strategie: datengetrieben · systematisch · unabhängig",
    ]
    for i, ln in enumerate(lines):
        c.text(MX, ty + i * 36, ln, 22, color=T.TEXT if i < 2 else T.MUTED)

    footer(c)


def build_transition(fmt="carousel", date_iso=None, outdir=None):
    ai_data = _load_ai_data()
    end_iso = ai_data[-1][0] if ai_data else TRANSITION_DATE
    nasdaq_ret_val = _nasdaq_ret(TRANSITION_DATE, end_iso)
    if date_iso is None:
        from datetime import date
        date_iso = date.today().isoformat()
    if outdir is None:
        outdir = os.path.join(ROOT, "out", "instagram", f"{date_iso}_TRANSITION")
    os.makedirs(outdir, exist_ok=True)

    c = Canvas(fmt)
    slide_transition(c, date_iso, ai_data, nasdaq_ret=nasdaq_ret_val)
    path = os.path.join(outdir, "01_transition.png")
    c.save(path)
    print(f"✓ Transition-Slide: {os.path.relpath(path, ROOT)}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--format", choices=["carousel", "reel"], default="carousel")
    args = ap.parse_args()
    build_transition(fmt=args.format, date_iso=args.date, outdir=args.out)


if __name__ == "__main__":
    main()

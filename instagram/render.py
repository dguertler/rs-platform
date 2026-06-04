"""
Render-Engine: zeichnet einzelne Slides als PNG im AI-Alpha-Selections-Design.
Reines matplotlib, kein Browser nötig. Jede Slide funktioniert in beiden
Formaten (Carousel 4:5 / Reel 9:16) über pixelbasierte Layout-Koordinaten.
"""
import os
from datetime import datetime

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from . import theme as T

_FONTS = T.register_fonts()
HANDLE = "@aialphaselections"
BRAND = "AI ALPHA SELECTIONS"
MX = 90  # Seitenrand in px


# ── Formatierungs-Helfer ──────────────────────────────────────────────────────
def fmt_pct(x, decimals=1, signed=True):
    sign = ("+" if x >= 0 else "−") if signed else ""
    return f"{sign}{abs(x) * 100:.{decimals}f}".replace(".", ",") + "%"


def fmt_de_date(iso):
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except Exception:
        return iso


def short_date(iso):
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.")
    except Exception:
        return iso


# ── Canvas ─────────────────────────────────────────────────────────────────────
class Canvas:
    def __init__(self, fmt):
        self.W, self.H = T.FORMATS[fmt]
        self.fig = plt.figure(figsize=(self.W / T.DPI, self.H / T.DPI), dpi=T.DPI)
        self.fig.patch.set_facecolor(T.BG)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, self.W)
        self.ax.set_ylim(0, self.H)
        self.ax.axis("off")

    def y(self, top_px):
        """Pixel von oben -> matplotlib-y (von unten)."""
        return self.H - top_px

    def text(self, x, top, s, size, color=T.TEXT, weight="normal",
             ha="left", va="top", font="sans", spacing=None, alpha=1.0):
        # `size` ist in Pixel gedacht -> in Punkt umrechnen (Layout = px)
        pt = size * 72.0 / T.DPI
        self.ax.text(x, self.y(top), s, fontsize=pt, color=color,
                     fontweight=weight, ha=ha, va=va, alpha=alpha,
                     fontfamily=_FONTS[font])

    def tile(self, x, top, w, h, color=T.PANEL, radius=26):
        bottom = self.y(top + h)
        box = FancyBboxPatch(
            (x, bottom), w, h,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            linewidth=0, facecolor=color, mutation_aspect=1)
        self.ax.add_patch(box)

    def draw_logo(self, x, top, height):
        """Zeichnet instagram/assets/logo.png (falls vorhanden). Gibt die
        gezeichnete Breite zurück (0, wenn kein Logo da ist)."""
        path = T.logo_file()
        if not path:
            return 0
        try:
            from PIL import Image
            img = Image.open(path).convert("RGBA")
            w = int(img.width * height / img.height)
            img = img.resize((w, int(height)), Image.LANCZOS)
            arr = np.asarray(img)
            self.fig.figimage(arr, xo=int(x), yo=int(self.H - top - height), zorder=10)
            return w
        except Exception:
            return 0

    def chart_axes(self, x, top, w, h):
        bottom = self.y(top + h)
        ax = self.fig.add_axes([x / self.W, bottom / self.H, w / self.W, h / self.H])
        ax.set_facecolor("none")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        return ax

    def save(self, path):
        self.fig.savefig(path, facecolor=T.BG, dpi=T.DPI)
        plt.close(self.fig)


# ── Gemeinsame Bausteine ────────────────────────────────────────────────────────
def header(c, date_iso):
    lw = c.draw_logo(MX, 62, 60)          # Logo (falls vorhanden)
    if not lw:                            # Fallback: Wortmarke
        c.text(MX, 70, BRAND, 22, color=T.TEXT, weight="bold")
        c.text(MX, 102, "Datengetriebene Aktienauswahl", 15, color=T.MUTED)
    c.text(c.W - MX, 78, fmt_de_date(date_iso), 18, color=T.MUTED, ha="right")
    c.ax.plot([MX, c.W - MX], [c.y(150), c.y(150)], color=T.GRID, lw=1.5)


def footer(c):
    # Disclaimer mehrzeilig umbrechen
    import textwrap
    lines = textwrap.wrap(T.DISCLAIMER_SHORT, width=64)
    y0 = c.H - 130
    c.ax.plot([MX, c.W - MX], [c.y(c.H - 165), c.y(c.H - 165)], color=T.GRID, lw=1.5)
    c.text(MX, c.H - 150, HANDLE, 16, color=T.GREEN, weight="bold")
    for i, ln in enumerate(lines):
        c.text(MX, c.H - 122 + i * 26, ln, 13, color=T.MUTED)


def _style_chart(ax):
    ax.grid(axis="y", color=T.GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)


# ── Slides ───────────────────────────────────────────────────────────────────────
def slide_hook(c, date_iso, perf_ret, nasdaq_ret, period_label):
    header(c, date_iso)
    cy = int(c.H * 0.40)
    c.text(MX, cy - 70, "WIKIFOLIO-PERFORMANCE", 24, color=T.MUTED, weight="bold")
    c.text(MX, cy, fmt_pct(perf_ret), 130, color=T.GREEN, weight="bold", font="mono")
    c.text(MX, cy + 175, period_label, 22, color=T.MUTED)
    # Outperformance-Chip
    chip_top = cy + 240
    c.tile(MX, chip_top, c.W - 2 * MX, 120, color=T.PANEL)
    c.text(MX + 40, chip_top + 32, "Outperformance vs. NASDAQ-100", 20, color=T.MUTED)
    c.text(c.W - MX - 40, chip_top + 28, fmt_pct(nasdaq_ret), 44,
           color=T.BLUE, weight="bold", ha="right", font="mono")
    footer(c)


def slide_performance(c, date_iso, wf_dates, wf_vals, nas_dates, nas_vals,
                      wf_ret, nas_ret, is_sample):
    header(c, date_iso)
    c.text(MX, 200, "Wertentwicklung vs. NASDAQ-100", 40, weight="bold")
    c.text(MX, 252, "Indexiert auf 100 zum Startzeitpunkt", 18, color=T.MUTED)

    chart_h = int(c.H * 0.42)
    ax = c.chart_axes(MX, 320, c.W - 2 * MX, chart_h)
    _style_chart(ax)

    wf_x = np.array([datetime.strptime(d, "%Y-%m-%d").toordinal() for d in wf_dates], float)
    base = wf_vals[0]
    wf_y = np.array([v / base * 100 for v in wf_vals])
    ax.plot(wf_x, wf_y, color=T.GREEN, lw=4, solid_capstyle="round", zorder=3)

    if nas_dates:
        nas_x = np.array([datetime.strptime(d, "%Y-%m-%d").toordinal() for d in nas_dates], float)
        nas_y = np.array(nas_vals)
        ax.plot(nas_x, nas_y, color=T.BLUE, lw=3, solid_capstyle="round", zorder=2)
        nas_on_wf = np.interp(wf_x, nas_x, nas_y)
        ax.fill_between(wf_x, wf_y, nas_on_wf, where=(wf_y >= nas_on_wf),
                        color=T.GREEN, alpha=0.12, zorder=1)

    # Kompakte Legende oben links im Chart (immer im Bild)
    def _leg(y, col, label):
        ax.plot([0.02, 0.06], [y, y], transform=ax.transAxes,
                color=col, lw=4, solid_capstyle="round", clip_on=False)
        ax.text(0.08, y, label, transform=ax.transAxes, color=col,
                fontsize=11, va="center", fontweight="bold",
                fontfamily=_FONTS["sans"])
    _leg(0.95, T.GREEN, "AI Alpha Selections")
    if nas_dates:
        _leg(0.87, T.BLUE, "NASDAQ-100")

    # Datums-Endpunkte
    c.text(MX, 320 + chart_h + 20, short_date(wf_dates[0]), 14, color=T.MUTED)
    c.text(c.W - MX, 320 + chart_h + 20, short_date(wf_dates[-1]), 14,
           color=T.MUTED, ha="right")

    # KPI-Zeile unter dem Chart
    ky = 320 + chart_h + 70
    half = (c.W - 2 * MX - 30) // 2
    c.tile(MX, ky, half, 110, color=T.PANEL)
    c.text(MX + 30, ky + 26, "AI Alpha Selections", 17, color=T.MUTED)
    c.text(MX + 30, ky + 52, fmt_pct(wf_ret), 40, color=T.GREEN, weight="bold", font="mono")
    c.tile(MX + half + 30, ky, half, 110, color=T.PANEL)
    c.text(MX + half + 60, ky + 26, "NASDAQ-100", 17, color=T.MUTED)
    c.text(MX + half + 60, ky + 52, fmt_pct(nas_ret), 40, color=T.BLUE, weight="bold", font="mono")

    if is_sample:
        c.text(c.W - MX, 200, "BEISPIELDATEN", 18, color=T.RED, weight="bold", ha="right")
    footer(c)


def slide_kpis(c, date_iso, wf_ret, out_ret, n_signals, n_tickers, top_ticker):
    header(c, date_iso)
    c.text(MX, 200, "Die Zahlen im Überblick", 40, weight="bold")
    cells = [
        ("Rendite (Zeitraum)", fmt_pct(wf_ret), T.GREEN),
        ("Outperformance NASDAQ", fmt_pct(out_ret), T.BLUE),
        ("Trade-Signale", str(n_signals), T.TEXT),
        ("Beobachtete Titel", str(n_tickers), T.TEXT),
    ]
    gap = 30
    tw = (c.W - 2 * MX - gap) // 2
    th = int((c.H * 0.42) / 2 - gap / 2)
    top0 = 300
    for i, (label, val, col) in enumerate(cells):
        r, cc = divmod(i, 2)
        x = MX + cc * (tw + gap)
        y = top0 + r * (th + gap)
        c.tile(x, y, tw, th, color=T.PANEL)
        c.text(x + 36, y + 36, label, 19, color=T.MUTED)
        c.text(x + 36, y + th - 70, val, 64, color=col, weight="bold", font="mono")
    c.text(MX, top0 + 2 * (th + gap) + 10,
           f"Stärkster Titel aktuell: {top_ticker}", 20, color=T.MUTED)
    footer(c)


def slide_signal(c, date_iso, ticker, sig, ret, ohlcv, entry):
    header(c, date_iso)
    color = T.GREEN if (ret or 0) >= 0 else T.RED
    c.text(MX, 200, "TRADE-SIGNAL", 22, color=T.MUTED, weight="bold")
    c.text(MX, 232, ticker, 72, weight="bold")

    chart_h = int(c.H * 0.40)
    ax = c.chart_axes(MX, 340, c.W - 2 * MX, chart_h)
    _style_chart(ax)
    xs = np.array([datetime.strptime(p["d"], "%Y-%m-%d").toordinal() for p in ohlcv], float)
    ys = np.array([p["c"] for p in ohlcv])
    ax.plot(xs, ys, color=T.TEXT, lw=2.5, zorder=3)
    ax.fill_between(xs, ys, ys.min(), color=T.TEXT, alpha=0.05, zorder=1)
    # Signal-Marker
    ex = datetime.strptime(entry["d"], "%Y-%m-%d").toordinal()
    ax.axvline(ex, color=color, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([ex], [entry["c"]], s=120, color=color, zorder=4, edgecolor=T.BG, lw=2)
    # Beschriftung links vom Marker, falls dieser im rechten Drittel liegt
    xmin, xmax = xs.min(), xs.max()
    right = (ex - xmin) / (xmax - xmin + 1e-9) > 0.6
    ax.annotate(f"Signal {short_date(entry['d'])}", (ex, entry["c"]),
                xytext=(-12 if right else 12, 18), textcoords="offset points",
                color=color, fontsize=15, fontweight="bold",
                ha="right" if right else "left", fontfamily=_FONTS["sans"])

    ky = 340 + chart_h + 60
    half = (c.W - 2 * MX - 30) // 2
    c.tile(MX, ky, half, 110, color=T.PANEL)
    c.text(MX + 30, ky + 26, "Rendite seit Signal", 17, color=T.MUTED)
    c.text(MX + 30, ky + 52, fmt_pct(ret) if ret is not None else "—", 40,
           color=color, weight="bold", font="mono")
    c.tile(MX + half + 30, ky, half, 110, color=T.PANEL)
    c.text(MX + half + 60, ky + 26, "Trigger / Quelle", 17, color=T.MUTED)
    trig = {"weekly": "Weekly", "daily": "Daily", "4h": "4h"}.get(
        sig.get("trigger_tf", ""), sig.get("trigger_tf", "—"))
    c.text(MX + half + 60, ky + 56, f"{trig} · {sig.get('source', '')}", 30,
           color=T.TEXT, weight="bold")
    footer(c)


def slide_cta(c, date_iso):
    import textwrap
    header(c, date_iso)
    cy = int(c.H * 0.30)
    c.text(MX, cy, "Folge für wöchentliche", 50, weight="bold")
    c.text(MX, cy + 64, "Updates & Signale.", 50, weight="bold")
    c.text(MX, cy + 150, HANDLE, 30, color=T.GREEN, weight="bold")
    c.text(MX, cy + 200, "→ Das wikifolio „AI Alpha Selections\" auf wikifolio.com", 20, color=T.MUTED)

    # Disclaimer-Panel
    panel_top = int(c.H * 0.55)
    panel_h = int(c.H * 0.31)
    c.tile(MX, panel_top, c.W - 2 * MX, panel_h, color=T.PANEL)
    c.text(MX + 36, panel_top + 30, "RISIKOHINWEIS", 20, color=T.RED, weight="bold")
    body = textwrap.wrap(T.DISCLAIMER_LONG.split("\n", 1)[1], width=58)
    for i, ln in enumerate(body[:9]):
        c.text(MX + 36, panel_top + 74 + i * 30, ln, 15, color=T.MUTED)
    footer(c)


# ── Wochenreport-Slides (report-getrieben) ─────────────────────────────────────
def slide_hook_weekly(c, date_iso, kw, period, week_perf, total_perf):
    header(c, date_iso)
    cy = int(c.H * 0.34)
    c.text(MX, cy - 60, f"WOCHENREPORT KW {kw}", 26, color=T.MUTED, weight="bold")
    c.text(MX, cy - 18, period, 20, color=T.MUTED)
    col = T.GREEN if week_perf >= 0 else T.RED
    c.text(MX, cy + 30, fmt_pct(week_perf), 120, color=col, weight="bold", font="mono")
    c.text(MX, cy + 195, "Wochenperformance Musterdepot", 22, color=T.MUTED)
    # Gesamt-Chip
    chip_top = cy + 260
    c.tile(MX, chip_top, c.W - 2 * MX, 120, color=T.PANEL)
    c.text(MX + 40, chip_top + 32, "Gesamtrendite seit Start", 20, color=T.MUTED)
    c.text(c.W - MX - 40, chip_top + 28, fmt_pct(total_perf), 44,
           color=T.GREEN, weight="bold", ha="right", font="mono")
    footer(c)


def slide_kpis_weekly(c, date_iso, total_perf, alpha, beaten, of_weeks, avg_win, avg_loss):
    header(c, date_iso)
    c.text(MX, 200, "Die Zahlen im Überblick", 40, weight="bold")
    cells = [
        ("Gesamtrendite", fmt_pct(total_perf), T.GREEN),
        ("Alpha vs. NASDAQ-100", fmt_pct(alpha), T.BLUE),
        ("Wochen geschlagen", f"{beaten}/{of_weeks}", T.TEXT),
        ("Ø Gewinn / Verlustwoche",
         f"{fmt_pct(avg_win)} / {fmt_pct(avg_loss)}", T.TEXT),
    ]
    gap = 30
    tw = (c.W - 2 * MX - gap) // 2
    th = int((c.H * 0.42) / 2 - gap / 2)
    top0 = 300
    for i, (label, val, col) in enumerate(cells):
        r, cc = divmod(i, 2)
        x = MX + cc * (tw + gap)
        y = top0 + r * (th + gap)
        c.tile(x, y, tw, th, color=T.PANEL)
        c.text(x + 36, y + 36, label, 19, color=T.MUTED)
        size = 64 if len(val) <= 7 else 40
        c.text(x + 36, y + th - 70, val, size, color=col, weight="bold", font="mono")
    footer(c)


def slide_history(c, date_iso, history):
    """Balkendiagramm der Wochenperformance (grün/rot)."""
    header(c, date_iso)
    c.text(MX, 200, "Wochen-Historie", 40, weight="bold")
    won = sum(1 for h in history if h["perf"] >= 0)
    c.text(MX, 252, f"{won} von {len(history)} Wochen positiv", 18, color=T.MUTED)

    chart_h = int(c.H * 0.46)
    ax = c.chart_axes(MX, 320, c.W - 2 * MX, chart_h)
    ax.grid(axis="y", color=T.GRID, lw=1, alpha=0.5)
    ax.set_axisbelow(True)
    labels = [f"KW{h['kw']}" for h in history]
    vals = [h["perf"] * 100 for h in history]
    xs = np.arange(len(vals))
    colors = [T.GREEN if v >= 0 else T.RED for v in vals]
    ax.bar(xs, vals, color=colors, width=0.66, zorder=3)
    ax.axhline(0, color=T.MUTED, lw=1.2)
    pad = max(abs(min(vals)), abs(max(vals))) * 0.18 + 0.5
    for x, v in zip(xs, vals):
        ax.text(x, v + (pad if v >= 0 else -pad),
                f"{v:+.1f}".replace(".", ",") + "%",
                ha="center", va="bottom" if v >= 0 else "top",
                color=T.TEXT, fontsize=11, fontweight="bold",
                fontfamily=_FONTS["sans"])
        ax.text(x, min(vals) - pad * 2.6, labels[int(x)], ha="center", va="top",
                color=T.MUTED, fontsize=11, fontfamily=_FONTS["sans"])
    ax.set_ylim(min(vals) - pad * 3.6, max(vals) + pad * 2.4)
    footer(c)


def slide_list(c, date_iso, title, subtitle, rows):
    """Generische Listen-Slide für Käufe / Verkäufe / Top-Performer.
    rows: Liste von dict(main, sub, value, color)."""
    header(c, date_iso)
    c.text(MX, 200, title, 40, weight="bold")
    if subtitle:
        c.text(MX, 252, subtitle, 18, color=T.MUTED)
    rows = rows[:4]
    top0 = 310
    gap = 24
    rh = min(150, int((c.H * 0.52 - gap * (len(rows) - 1)) / max(1, len(rows))))
    for i, row in enumerate(rows):
        y = top0 + i * (rh + gap)
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        # farbiger Akzentbalken links
        c.tile(MX, y, 10, rh, color=row["color"], radius=5)
        c.text(MX + 42, y + rh / 2 - 28, row["main"], 30, weight="bold")
        if row.get("sub"):
            c.text(MX + 42, y + rh / 2 + 14, row["sub"], 16, color=T.MUTED)
        c.text(c.W - MX - 40, y + rh / 2 - 26, row["value"], 40,
               color=row["color"], weight="bold", ha="right", font="mono")
    footer(c)

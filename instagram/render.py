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
HANDLE = "@aialphaselection"
BRAND = "AI ALPHA SELECTION"
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
            bbox = img.getbbox()           # transparente Ränder wegschneiden
            if bbox:
                img = img.crop(bbox)
            w = int(img.width * height / img.height)
            img = img.resize((w, int(height)), Image.LANCZOS)
            arr = np.asarray(img)
            self.fig.figimage(arr, xo=int(x), yo=int(self.H - top - height), zorder=10)
            return w
        except Exception:
            return 0

    def draw_image_contain(self, path, x, top, w, h, zorder=10):
        """Zeichnet ein Bild größtmöglich INNERHALB der Box (x,top,w,h),
        Seitenverhältnis erhalten, zentriert. Gibt (nw, nh) zurück oder None."""
        try:
            from PIL import Image
            img = Image.open(path).convert("RGBA")
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            iw, ih = img.width, img.height
            scale = min(w / iw, h / ih)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            img = img.resize((nw, nh), Image.LANCZOS)
            arr = np.asarray(img)
            ox = int(x + (w - nw) / 2)
            oy_top = top + (h - nh) / 2
            self.fig.figimage(arr, xo=ox, yo=int(self.H - oy_top - nh), zorder=zorder)
            return (nw, nh)
        except Exception:
            return None

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
    # Disclaimer volle Breite (links nach rechts), ohne Handle
    import textwrap
    c.ax.plot([MX, c.W - MX], [c.y(c.H - 150), c.y(c.H - 150)], color=T.GRID, lw=1.5)
    lines = textwrap.wrap(T.DISCLAIMER_SHORT, width=150)
    for i, ln in enumerate(lines):
        c.text(MX, c.H - 128 + i * 25, ln, 12, color=T.MUTED)


def _style_chart(ax):
    ax.grid(axis="y", color=T.GRID, lw=1, alpha=0.6)
    ax.set_axisbelow(True)


def _justify_line(c, x, top, words, size, color, target_w, font="sans"):
    """Zeichnet eine Zeile im Blocksatz: Wörter werden auf target_w (px) verteilt."""
    try:
        r = c.fig.canvas.get_renderer()
    except Exception:
        c.fig.canvas.draw()
        r = c.fig.canvas.get_renderer()
    pt = size * 72.0 / T.DPI

    def wpx(s):
        t = c.ax.text(0, 0, s, fontsize=pt, fontfamily=_FONTS[font])
        bb = t.get_window_extent(renderer=r)
        t.remove()
        return bb.width

    if len(words) <= 1:
        c.text(x, top, words[0] if words else "", size, color=color, font=font)
        return
    widths = [wpx(w) for w in words]
    gap = max((target_w - sum(widths)) / (len(words) - 1), wpx(" "))
    cx = x
    for w, ww in zip(words, widths):
        c.text(cx, top, w, size, color=color, font=font)
        cx += ww + gap


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
                      wf_ret, nas_ret, is_sample, stats=None):
    header(c, date_iso)
    c.text(MX, 196, "Wertentwicklung vs. NASDAQ-100", 40, weight="bold")
    c.text(MX, 248, "Indexiert auf 100 zum Startzeitpunkt", 18, color=T.MUTED)

    chart_h = int(c.H * (0.30 if stats else 0.42))
    ax = c.chart_axes(MX, 306, c.W - 2 * MX, chart_h)
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

    def _leg(y, col, label):
        ax.plot([0.02, 0.06], [y, y], transform=ax.transAxes,
                color=col, lw=4, solid_capstyle="round", clip_on=False)
        ax.text(0.08, y, label, transform=ax.transAxes, color=col,
                fontsize=11, va="center", fontweight="bold", fontfamily=_FONTS["sans"])
    _leg(0.95, T.GREEN, "AI Alpha Selection")
    if nas_dates:
        _leg(0.87, T.BLUE, "NASDAQ-100")

    c.text(MX, 306 + chart_h + 16, short_date(wf_dates[0]), 14, color=T.MUTED)
    c.text(c.W - MX, 306 + chart_h + 16, short_date(wf_dates[-1]), 14,
           color=T.MUTED, ha="right")

    # Zwei große Renditen-Kacheln
    ky = 306 + chart_h + 48
    half = (c.W - 2 * MX - 30) // 2
    c.tile(MX, ky, half, 104, color=T.PANEL)
    c.text(MX + 30, ky + 24, "AI Alpha Selection", 17, color=T.MUTED)
    c.text(MX + 30, ky + 50, fmt_pct(wf_ret), 40, color=T.GREEN, weight="bold", font="mono")
    c.tile(MX + half + 30, ky, half, 104, color=T.PANEL)
    c.text(MX + half + 60, ky + 24, "NASDAQ-100", 17, color=T.MUTED)
    c.text(MX + half + 60, ky + 50, fmt_pct(nas_ret), 40, color=T.BLUE, weight="bold", font="mono")

    # Kennzahlen-Streifen
    if stats:
        pf = stats.get("profit_factor")
        pfs = "∞" if pf is None else f"{pf:.1f}".replace(".", ",")
        chips = [
            ("Alpha vs. NASDAQ", fmt_pct(stats["alpha"]), T.BLUE),
            ("Trades seit Start", f"{stats['trades']}*", T.TEXT),
            ("Trefferquote", f"{round(stats['win_rate'] * 100)} %*", T.GREEN),
            ("Profitfaktor", pfs + "*", T.GREEN),
            ("Ø Gewinn/Trade", fmt_pct(stats["avg_win"]) + "*", T.GREEN),
            ("Ø Verlust/Trade", fmt_pct(stats["avg_loss"]) + "*", T.RED),
        ]
        gap = 20
        cw = (c.W - 2 * MX - 2 * gap) // 3
        ch = 104
        sy = ky + 104 + 22
        for i, (lab, val, col) in enumerate(chips):
            r, cc = divmod(i, 3)
            x = MX + cc * (cw + gap)
            y = sy + r * (ch + gap)
            c.tile(x, y, cw, ch, color=T.PANEL)
            c.text(x + 22, y + 24, lab, 14, color=T.MUTED)
            c.text(x + 22, y + 50, val, 34, color=col, weight="bold", font="mono")
        c.text(MX, sy + 2 * (ch + gap) + 4, "* inkl. offener Positionen",
               13, color=T.MUTED)

    if is_sample:
        c.text(c.W - MX, 196, "BEISPIELDATEN", 18, color=T.RED, weight="bold", ha="right")
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
    ax.annotate(f"Signal {short_date(entry['d'])}", (ex, entry["c"]),
                xytext=(-12, 18), textcoords="offset points",
                color=color, fontsize=15, fontweight="bold",
                ha="right", fontfamily=_FONTS["sans"])

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
    c.text(MX, cy + 150, "AI Alpha Selection", 30, color=T.BLUE, weight="bold")
    c.text(MX, cy + 200, "→ Das wikifolio auf wikifolio.com", 20, color=T.MUTED)

    # Risikohinweis-Box: Text volle Breite, Box an Textgröße angepasst, unten ausgerichtet
    body = textwrap.wrap(T.DISCLAIMER_LONG.split("\n", 1)[1], width=104)
    line_h = 30
    panel_h = 74 + (len(body) - 1) * line_h + 42
    panel_bottom = c.H - 175
    panel_top = panel_bottom - panel_h
    c.tile(MX, panel_top, c.W - 2 * MX, panel_h, color=T.PANEL)
    c.text(MX + 36, panel_top + 30, "RISIKOHINWEIS", 20, color=T.RED, weight="bold")
    target_w = (c.W - 2 * MX) - 72        # Innenbreite der Box
    for i, ln in enumerate(body):
        ty = panel_top + 74 + i * line_h
        if i < len(body) - 1:             # alle Zeilen außer der letzten: Blocksatz
            _justify_line(c, MX + 36, ty, ln.split(), 15, T.MUTED, target_w)
        else:
            c.text(MX + 36, ty, ln, 15, color=T.MUTED)
    footer(c)


# ── Wochenreport-Slides (report-getrieben) ─────────────────────────────────────
def slide_hook_weekly(c, date_iso, kw, period, week_perf, total_perf):
    header(c, date_iso)
    cy = int(c.H * 0.34)
    c.text(MX, cy - 60, f"WOCHENREPORT KW {kw}", 26, color=T.MUTED, weight="bold")
    c.text(MX, cy - 18, period, 20, color=T.MUTED)
    col = T.GREEN if week_perf >= 0 else T.RED
    c.text(MX, cy + 30, fmt_pct(week_perf), 120, color=col, weight="bold", font="mono")
    c.text(MX, cy + 195, "Wochenperformance", 22, color=T.MUTED)
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
    """Balkendiagramm der wöchentlichen Mehrrendite ggü. NASDAQ (grün/rot)."""
    header(c, date_iso)
    c.text(MX, 200, "Mehrrendite ggü. NASDAQ-100", 40, weight="bold")
    vkey = "dev" if history and "dev" in history[0] else "perf"
    won = sum(1 for h in history if h[vkey] >= 0)
    c.text(MX, 252, f"{won} von {len(history)} Wochen den NASDAQ geschlagen",
           18, color=T.MUTED)

    chart_h = int(c.H * 0.46)
    ax = c.chart_axes(MX, 320, c.W - 2 * MX, chart_h)
    ax.grid(axis="y", color=T.GRID, lw=1, alpha=0.5)
    ax.set_axisbelow(True)
    labels = [f"KW{h['kw']}" for h in history]
    vals = [h[vkey] * 100 for h in history]
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
    rows = rows[:5]
    top0 = 310
    gap = 22
    rh = min(150, int((c.H * 0.56 - gap * (len(rows) - 1)) / max(1, len(rows))))
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


def slide_featured(c, date_iso, feat, label="AKTIE DER WOCHE"):
    """Kursverlauf mit Kauf-Signal (blau) + eingearbeiteten weiteren Signalen."""
    header(c, date_iso)
    ticker, ohlcv = feat["ticker"], feat["ohlcv"]
    entry, ret = feat["entry"], feat["ret"]
    rcol = T.GREEN if (ret or 0) >= 0 else T.RED   # Farbe für Renditewert
    mcol = T.BLUE                                   # Kauf = Signal -> blau
    c.text(MX, 200, label, 22, color=T.BLUE, weight="bold")
    c.text(MX, 232, ticker, 64, weight="bold")
    sub = feat.get("name", "")
    if feat.get("buy_date"):
        sub += f"  ·  Kauf {fmt_de_date(feat['buy_date'])}"
    if sub:
        c.text(MX + 12, 300, sub, 20, color=T.MUTED)

    # Fenster: ~25 Bars vor Kauf bis heute
    idx = next((i for i, p in enumerate(ohlcv) if p["d"] >= feat["buy_date"]), 0)
    sub = ohlcv[max(0, idx - 25):]
    chart_h = int(c.H * 0.40)
    ax = c.chart_axes(MX, 350, c.W - 2 * MX, chart_h)
    _style_chart(ax)
    xs = np.array([datetime.strptime(p["d"], "%Y-%m-%d").toordinal() for p in sub], float)
    ys = np.array([p["c"] for p in sub])
    ax.plot(xs, ys, color=T.TEXT, lw=2.5, zorder=3)
    ax.fill_between(xs, ys, ys.min(), color=T.TEXT, alpha=0.05, zorder=1)

    def _on(dt):
        p = next((q for q in sub if q["d"] >= dt), None)
        return (datetime.strptime(p["d"], "%Y-%m-%d").toordinal(), p["c"]) if p else None

    # weitere Signale (klein, blau)
    for s in feat.get("signals", []):
        if s.get("signal_date") == entry["d"]:
            continue
        pt = _on(s.get("signal_date", ""))
        if pt:
            ax.scatter([pt[0]], [pt[1]], s=42, color=T.BLUE, zorder=4,
                       edgecolor=T.BG, lw=1.5)

    # Kauf-Signal (groß, blau)
    ex = datetime.strptime(entry["d"], "%Y-%m-%d").toordinal()
    ax.axvline(ex, color=mcol, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([ex], [entry["c"]], s=140, color=mcol, zorder=5, edgecolor=T.BG, lw=2)
    ax.annotate(f"Kauf-Signal {short_date(entry['d'])}", (ex, entry["c"]),
                xytext=(-12, 18), textcoords="offset points",
                color=mcol, fontsize=15, fontweight="bold",
                ha="right", fontfamily=_FONTS["sans"])

    # Mini-Legende
    c.text(MX, 350 + chart_h + 22, "● Kauf-Signal", 14, color=mcol, weight="bold")
    if any(s.get("signal_date") != entry["d"] for s in feat.get("signals", [])):
        c.text(MX + 200, 350 + chart_h + 22, "● weitere Signale", 14, color=T.BLUE)

    # KPI-Kacheln
    ky = 350 + chart_h + 70
    half = (c.W - 2 * MX - 30) // 2
    c.tile(MX, ky, half, 110, color=T.PANEL)
    c.text(MX + 30, ky + 26, "Wertzuwachs seit Kauf", 17, color=T.MUTED)
    c.text(MX + 30, ky + 52, fmt_pct(ret) if ret is not None else "—", 40,
           color=rcol, weight="bold", font="mono")
    c.tile(MX + half + 30, ky, half, 110, color=T.PANEL)
    bp = feat.get("buy_price_eur")
    if bp:
        c.text(MX + half + 60, ky + 26, "Einstiegskurs", 17, color=T.MUTED)
        c.text(MX + half + 60, ky + 52,
               f"{bp:.2f}".replace(".", ",") + " €", 40, weight="bold", font="mono")
    else:
        c.text(MX + half + 60, ky + 26, "Kaufdatum", 17, color=T.MUTED)
        c.text(MX + half + 60, ky + 56, fmt_de_date(entry["d"]), 30, weight="bold")
    footer(c)


# ── Aktien-Analyse-Slides (analyses/TICKER.md -> Instagram) ─────────────────────
from . import analysis as A

VERDICT_LABEL = {"BUY": "KAUFEN", "HOLD": "HALTEN",
                 "WATCH": "BEOBACHTEN", "SELL": "VERKAUFEN"}
SCEN_LABEL = {"bull": "Bull", "base": "Base", "bear": "Bear"}
SCEN_COLOR = {"bull": T.GREEN, "base": T.BLUE, "bear": T.RED}


def verdict_color(v):
    return {"BUY": T.GREEN, "HOLD": T.AMBER,
            "WATCH": T.AMBER, "SELL": T.RED}.get((v or "").upper(), T.BLUE)


def _wrap_px(text, px_width, size, factor=0.52):
    import textwrap
    width = max(8, int(px_width / max(1.0, size * factor)))
    return textwrap.wrap(text, width=width)


def _draw_paragraph(c, x, top, text, size, px_width, color=T.TEXT,
                    weight="normal", line_h=None, max_lines=None):
    lines = _wrap_px(text, px_width, size)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;") + " …"
    lh = line_h or int(size * 1.34)
    for i, ln in enumerate(lines):
        c.text(x, top + i * lh, ln, size, color=color, weight=weight)
    return top + len(lines) * lh


def analysis_header(c, a, date_iso):
    """Kompakter Marken-Header für Innen-Slides + ANALYSE-Tag rechts."""
    lw = c.draw_logo(MX, 62, 52)
    if not lw:
        c.text(MX, 66, BRAND, 20, color=T.TEXT, weight="bold")
    # Tag rechts: ANALYSE · TICKER
    tag = f"ANALYSE · {a['ticker']}"
    c.tile(c.W - MX - 320, 60, 320, 52, color=T.PANEL_HI)
    c.text(c.W - MX - 320 + 24, 74, tag, 17, color=T.BLUE, weight="bold")
    c.ax.plot([MX, c.W - MX], [c.y(140), c.y(140)], color=T.GRID, lw=1.5)


def analysis_footer(c):
    import textwrap
    c.ax.plot([MX, c.W - MX], [c.y(c.H - 150), c.y(c.H - 150)], color=T.GRID, lw=1.5)
    lines = textwrap.wrap(T.DISCLAIMER_ANALYSE_SHORT, width=150)
    for i, ln in enumerate(lines):
        c.text(MX, c.H - 128 + i * 25, ln, 12, color=T.MUTED)


def _verdict_badge(c, x, top, verdict, score, w=None, h=120):
    col = verdict_color(verdict)
    w = w or (c.W - 2 * MX)
    c.tile(x, top, w, h, color=T.PANEL)
    c.tile(x, top, 12, h, color=col, radius=6)
    lab = VERDICT_LABEL.get((verdict or "").upper(), verdict or "—")
    c.text(x + 40, top + 24, "EINSCHÄTZUNG", 16, color=T.MUTED)
    c.text(x + 40, top + 52, f"{verdict} · {lab}", 40, color=col, weight="bold")
    if score is not None:
        c.text(x + w - 40, top + 30, f"{score}", 64, color=col,
               weight="bold", ha="right", font="mono")
        c.text(x + w - 40, top + 98, "/100", 20, color=T.MUTED, ha="right")


def _pips(c, x, top, value, total=5, size=22, gap=12, col=T.BLUE):
    for i in range(total):
        cx = x + i * (size + gap)
        c.tile(cx, top, size, size, color=col if i < (value or 0) else T.GRID,
               radius=size // 2)


def _stars(c, x, top, value, total=5, gap=50, s=520, col=T.BLUE):
    """5 Sterne als Bewertung; gefüllte = Wert (robust als Marker gezeichnet)."""
    for i in range(total):
        cx = x + i * gap
        filled = i < (value or 0)
        c.ax.scatter(cx, c.y(top), s=s, marker="*",
                     color=(col if filled else T.GRID),
                     edgecolor="none", zorder=11)


# 1) COVER — Firmenlogo + Verdict + Hook
def slide_analysis_cover(c, a, date_iso):
    col = verdict_color(a["verdict"])
    # Top-Leiste: Marke + Tag + Datum
    lw = c.draw_logo(MX, 70, 48)
    if not lw:
        c.text(MX, 74, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 80, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")
    c.tile(MX, 150, 220, 50, color=T.PANEL_HI)
    c.text(MX + 24, 163, "AKTIENANALYSE", 17, color=T.BLUE, weight="bold")

    # Logo-Panel (Firmenlogo oder Wortmarke)
    panel_top, panel_h = 250, 430
    c.tile(MX, panel_top, c.W - 2 * MX, panel_h, color=T.PANEL)
    logo = T.company_logo_file(a["ticker"])
    drew = c.draw_image_contain(logo, MX + 80, panel_top + 60,
                                c.W - 2 * MX - 160, panel_h - 200) if logo else None
    if drew:
        c.text(c.W / 2, panel_top + panel_h - 78, a["ticker"], 40,
               weight="bold", ha="center")
    else:
        # Wortmarke-Fallback: Ticker groß zentriert (Name steht unter dem Panel)
        c.text(c.W / 2, panel_top + panel_h / 2 - 95, a["ticker"], 150,
               weight="bold", ha="center", font="mono")

    # Name + Sektor unter dem Panel
    sub = a["name"]
    if a.get("sector"):
        sub += f"  ·  {a['sector']}"
    c.text(MX, panel_top + panel_h + 34, sub, 22, color=T.MUTED)

    # Verdict-Badge
    badge_top = panel_top + panel_h + 86
    _verdict_badge(c, MX, badge_top, a["verdict"], a["score"], h=130)

    # Hook
    if a.get("hook"):
        _draw_paragraph(c, MX, badge_top + 162, a["hook"], 24,
                        c.W - 2 * MX, color=T.TEXT, weight="bold", max_lines=3)
    analysis_footer(c)


# 2) GESAMTEINSCHÄTZUNG — Kernthese + Rating-Pips
def slide_analysis_verdict(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Gesamteinschätzung", 42, weight="bold")
    col = verdict_color(a["verdict"])
    lab = VERDICT_LABEL.get((a["verdict"] or "").upper(), "")
    c.text(MX, 248, f"{a['verdict']} · {lab}   ·   Score {a['score']}/100"
           if a["score"] is not None else f"{a['verdict']} · {lab}",
           22, color=col, weight="bold")

    # Kernthese: vollständiger Investment-Case (mehrzeilig, sauber gekürzt)
    core = " ".join(a["sections"].get(1, "").split()) or a.get("hook", "")
    y = _draw_paragraph(c, MX, 312, core, 25, c.W - 2 * MX,
                        color=T.TEXT, line_h=38, max_lines=10)

    # Rating-Karten 2x2 mit Pips
    rt = a["ratings"]
    items = [("Qualität", rt.get("Qualität")), ("Wachstum", rt.get("Wachstum")),
             ("Bewertung", rt.get("Bewertung")), ("Katalysator", rt.get("Katalysator"))]
    gap = 26
    cw = (c.W - 2 * MX - gap) // 2
    ch = 150
    top0 = max(y + 40, 760)
    for i, (label, val) in enumerate(items):
        r, cc = divmod(i, 2)
        x = MX + cc * (cw + gap)
        yy = top0 + r * (ch + gap)
        c.tile(x, yy, cw, ch, color=T.PANEL)
        c.text(x + 30, yy + 26, label.upper(), 16, color=T.MUTED, weight="bold")
        c.text(x + cw - 30, yy + 22, f"{val if val is not None else '–'}/5", 30,
               color=T.TEXT, weight="bold", ha="right", font="mono")
        _stars(c, x + 44, yy + 100, val, col=col)
    analysis_footer(c)


def _scenario_rows(c, a, top, horizon_key, title, subtitle):
    """Gemeinsamer Block: Bull/Base/Bear als Wahrscheinlichkeits-Balken +
    Kursziel-Spanne. horizon_key: 'scenarios' (12–18M) oder 'longterm' (3–5J)."""
    c.text(MX, top, title, 42, weight="bold")
    c.text(MX, top + 56, subtitle, 18, color=T.MUTED)
    data = a[horizon_key]
    rows_top = top + 110
    rh, gap = 168, 26
    maxprob = 0
    if horizon_key == "scenarios":
        maxprob = max([(data[k]["prob"] or 0) for k in ("bull", "base", "bear")] + [1])
    for i, key in enumerate(("bull", "base", "bear")):
        col = SCEN_COLOR[key]
        y = rows_top + i * (rh + gap)
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        c.tile(MX, y, 12, rh, color=col, radius=6)
        c.text(MX + 40, y + 22, SCEN_LABEL[key] + " Case", 28, color=col, weight="bold")
        if horizon_key == "scenarios":
            prob = data[key]["prob"]
            rng = A.fmt_range(data[key]["range"])
            # Wahrscheinlichkeits-Balken
            bar_x, bar_top = MX + 40, y + 78
            bar_w = c.W - 2 * MX - 80 - 260
            c.tile(bar_x, bar_top, bar_w, 30, color=T.PANEL_HI, radius=15)
            if prob:
                c.tile(bar_x, bar_top, int(bar_w * prob / maxprob), 30,
                       color=col, radius=15)
            c.text(bar_x, bar_top + 52, "Wahrscheinlichkeit", 15, color=T.MUTED)
            c.text(c.W - MX - 40, y + 26,
                   (f"{prob}%" if prob is not None else "–"), 40,
                   color=col, weight="bold", ha="right", font="mono")
            c.text(c.W - MX - 40, y + 86, "Kursziel " + (rng or "k. A."), 22,
                   color=T.TEXT, ha="right", weight="bold")
        else:
            rng = A.fmt_range(data[key])
            c.text(MX + 40, y + 78, "Kursziel-Spanne", 16, color=T.MUTED)
            c.text(c.W - MX - 40, y + 58, rng or "k. A.", 40,
                   color=col, weight="bold", ha="right", font="mono")
    return rows_top + 3 * (rh + gap)


# 3) SZENARIEN 12–18 MONATE — Wahrscheinlichkeiten + Kursziele
def slide_analysis_scenarios(c, a, date_iso):
    analysis_header(c, a, date_iso)
    _scenario_rows(c, a, 184, "scenarios",
                   "Szenarien · 12–18 Monate",
                   "Eintrittswahrscheinlichkeit & Kursziel-Spanne (Bull + Base + Bear = 100 %)")
    analysis_footer(c)


# 4) LANGFRIST 3–5 JAHRE — Kursziel-Spannen (Punkt 10)
def slide_analysis_longterm(c, a, date_iso):
    analysis_header(c, a, date_iso)
    _scenario_rows(c, a, 184, "longterm",
                   "Langfrist-Szenarien · 3–5 Jahre",
                   "Kursziel-Spannen je Szenario — ohne Eintrittswahrscheinlichkeit")
    analysis_footer(c)


# 5) WAS MACHT DAS UNTERNEHMEN — Highlights aus Investment-Case + Geschäftsmodell
def slide_analysis_business(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Was macht das Unternehmen?", 42, weight="bold")
    c.text(MX, 240, "Geschäftsmodell & Investment-Case in Kürze", 18, color=T.MUTED)
    bullets = a.get("business_bullets", [])[:5]
    top0, gap = 304, 22
    rh = min(150, int((c.H * 0.58 - gap * (len(bullets) - 1)) / max(1, len(bullets))))
    for i, b in enumerate(bullets):
        y = top0 + i * (rh + gap)
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        c.tile(MX, y, 10, rh, color=T.BLUE, radius=5)
        # Bullet kann " — " als Trenner Kopf/Detail haben
        head, _, rest = b.partition(" — ")
        if rest:
            c.text(MX + 40, y + 22, head.strip(), 22, color=T.BLUE, weight="bold")
            _draw_paragraph(c, MX + 40, y + 60, rest.strip(), 19,
                            c.W - 2 * MX - 80, color=T.TEXT, max_lines=2)
        else:
            _draw_paragraph(c, MX + 40, y + rh / 2 - 24, b, 21,
                            c.W - 2 * MX - 80, color=T.TEXT, max_lines=2)
    analysis_footer(c)


# 5b) CHANCEN & RISIKEN — für Posts ohne Szenario-Wahrscheinlichkeiten (Alt-Schema)
def slide_analysis_chances(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Chancen & Risiken", 42, weight="bold")
    c.text(MX, 240, "Das Wichtigste aus Bull- und Bear-Sicht", 18, color=T.MUTED)

    def block(title, bullets, col, top, h):
        c.tile(MX, top, c.W - 2 * MX, h, color=T.PANEL)
        c.tile(MX, top, 12, h, color=col, radius=6)
        c.text(MX + 40, top + 24, title, 26, color=col, weight="bold")
        y = top + 84
        for b in bullets[:4]:
            c.text(MX + 40, y, "›", 22, color=col, weight="bold")
            yy = _draw_paragraph(c, MX + 70, y, b, 20, c.W - 2 * MX - 110,
                                 color=T.TEXT, line_h=29, max_lines=2)
            y = yy + 14

    gap = 30
    h = int((c.H * 0.62 - gap) / 2)
    block("Chancen", a.get("pro_bullets", []), T.GREEN, 300, h)
    block("Risiken", a.get("con_bullets", []), T.RED, 300 + h + gap, h)
    analysis_footer(c)


# 6) BULL / BASE / BEAR ERKLÄRT — Treibersätze (konsistent zu Slide 3)
def slide_analysis_cases(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Die drei Szenarien erklärt", 42, weight="bold")
    c.text(MX, 240, "Was hinter Bull, Base und Bear steckt", 18, color=T.MUTED)
    top0, gap = 300, 26
    rh = 318
    sc = a["scenarios"]
    for i, key in enumerate(("bull", "base", "bear")):
        col = SCEN_COLOR[key]
        y = top0 + i * (rh + gap)
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        c.tile(MX, y, 12, rh, color=col, radius=6)
        rng = A.fmt_range(sc[key]["range"])
        prob = sc[key]["prob"]
        hdr = f"{SCEN_LABEL[key]} Case"
        c.text(MX + 40, y + 24, hdr, 26, color=col, weight="bold")
        meta = []
        if prob is not None:
            meta.append(f"{prob}%")
        if rng:
            meta.append(rng)
        if meta:
            c.text(c.W - MX - 40, y + 28, "  ·  ".join(meta), 24,
                   color=T.TEXT, weight="bold", ha="right", font="mono")
        _draw_paragraph(c, MX + 40, y + 84, sc[key]["summary"], 21,
                        c.W - 2 * MX - 80, color=T.TEXT, line_h=32, max_lines=6)
    analysis_footer(c)


# 7) PROFI-FAZIT — Kernaussage + Peers + Verweis auf Caption
def slide_analysis_fazit(c, a, date_iso):
    analysis_header(c, a, date_iso)
    col = verdict_color(a["verdict"])
    c.text(MX, 184, "Profi-Fazit", 42, weight="bold")
    _verdict_badge(c, MX, 244, a["verdict"], a["score"], h=120)

    core = a.get("fazit_core") or A._first_sentence(a["sections"].get(11, ""), 320)
    y = _draw_paragraph(c, MX, 396, core, 24, c.W - 2 * MX,
                        color=T.TEXT, line_h=36, max_lines=6)

    # Peers
    peers = a.get("peers", [])
    if peers:
        c.text(MX, y + 30, "VERGLEICHBARE TITEL", 16, color=T.MUTED, weight="bold")
        px = MX
        yy = y + 64
        for p in peers:
            w = min(360, 60 + int(len(p) * 12))
            if px + w > c.W - MX:
                px = MX
                yy += 70
            c.tile(px, yy, w, 56, color=T.PANEL_HI)
            c.text(px + 24, yy + 16, p, 20, color=T.TEXT, weight="bold")
            px += w + 18
        y = yy + 56

    # Verweis auf vollständige Analyse (Caption)
    cta_top = max(y + 40, c.H - 360)
    c.tile(MX, cta_top, c.W - 2 * MX, 120, color=T.PANEL)
    c.tile(MX, cta_top, 12, 120, color=T.BLUE, radius=6)
    c.text(MX + 40, cta_top + 26, "Ganze Analyse als Text unter diesem Post", 26,
           color=T.TEXT, weight="bold")
    c.text(MX + 40, cta_top + 70, "Tippe auf „mehr“  ·  folge für 1–2 Analysen/Woche",
           19, color=T.MUTED)
    # nach unten zeigende Dreiecke (robust gezeichnet statt Glyph)
    for i in range(3):
        c.ax.scatter(c.W - MX - 60 - i * 34, c.y(cta_top + 60), s=150,
                     marker="v", color=T.BLUE, edgecolor="none", zorder=12)
    analysis_footer(c)

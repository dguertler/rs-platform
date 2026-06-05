"""
Render-Engine: zeichnet einzelne Slides als PNG im AI-Alpha-Selections-Design.
Reines matplotlib, kein Browser nötig. Jede Slide funktioniert in beiden
Formaten (Carousel 4:5 / Reel 9:16) über pixelbasierte Layout-Koordinaten.

CHART-KONVENTIONEN (verbindlich):
  - Marker-Texte stehen IMMER LINKS der gepunkteten (vertikalen) Linie
    (ha="right", negativer x-Offset).
  - Kauf-Marker = GRÜN (T.GREEN), Verkauf-Marker = ROT (T.RED).
  - Renditewert (Kachel/Titel) bleibt vorzeichenabhängig grün/rot.
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


def _wrap_px(c, text, size, target_w, font="sans"):
    """Umbruch nach Pixelbreite: packt je Zeile so viele Wörter wie möglich, bis
    target_w (px) erreicht ist. Dadurch sind die Zeilen voll und der Blocksatz
    erzeugt nur minimale Lücken (statt großer Abstände bei zeichen-basiertem Wrap)."""
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

    lines, cur = [], []
    for w in text.split():
        if cur and wpx(" ".join(cur + [w])) > target_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _risk_box(c):
    """Pflicht-Risikohinweis als Box am unteren Rand (Blocksatz, pixelgefüllt)."""
    target_w = (c.W - 2 * MX) - 72
    body = _wrap_px(c, T.DISCLAIMER_LONG.split("\n", 1)[1], 15, target_w)
    line_h = 30
    panel_h = 74 + (len(body) - 1) * line_h + 42
    panel_bottom = c.H - 175
    panel_top = panel_bottom - panel_h
    c.tile(MX, panel_top, c.W - 2 * MX, panel_h, color=T.PANEL)
    c.text(MX + 36, panel_top + 30, "RISIKOHINWEIS", 20, color=T.RED, weight="bold")
    for i, ln in enumerate(body):
        ty = panel_top + 74 + i * line_h
        if i < len(body) - 1:
            _justify_line(c, MX + 36, ty, ln.split(), 15, T.MUTED, target_w)
        else:
            c.text(MX + 36, ty, ln, 15, color=T.MUTED)


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
    header(c, date_iso)
    cy = int(c.H * 0.30)
    c.text(MX, cy, "Folge für wöchentliche", 50, weight="bold")
    c.text(MX, cy + 64, "Updates & Signale.", 50, weight="bold")
    c.text(MX, cy + 150, "AI Alpha Selection", 30, color=T.BLUE, weight="bold")
    c.text(MX, cy + 200, "→ Das wikifolio auf wikifolio.com", 20, color=T.MUTED)
    _risk_box(c)
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
    mcol = T.GREEN                                  # Kauf-Marker = grün
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

    # Kauf-Signal (groß, blau) inkl. Kaufkurs am Marker
    ex = datetime.strptime(entry["d"], "%Y-%m-%d").toordinal()
    ax.axvline(ex, color=mcol, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([ex], [entry["c"]], s=140, color=mcol, zorder=5, edgecolor=T.BG, lw=2)
    bp = feat.get("buy_price_eur")
    klabel = f"Kauf {short_date(entry['d'])}"
    if bp:
        klabel += "\n" + f"{bp:.2f}".replace(".", ",") + " €"
    ax.annotate(klabel, (ex, entry["c"]),
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


def slide_trade(c, date_iso, t, label="GROSSER VERKAUF DER WOCHE"):
    """Realisierter Trade: Kursverlauf mit Kauf- (blau) UND Verkauf-Marker
    (grün/rot), beide mit Kurs, plus Rendite/Einstiegs-/Verkaufskurs-Kacheln."""
    header(c, date_iso)
    ticker, ohlcv = t["ticker"], t["ohlcv"]
    entry, exit_pt, ret = t["entry"], t["exit"], t["ret"]
    rcol = T.GREEN if (ret or 0) >= 0 else T.RED   # Renditewert (Vorzeichen)
    bcol = T.GREEN                                  # Kauf-Marker = grün
    scol = T.RED                                    # Verkauf-Marker = rot
    c.text(MX, 200, label, 22, color=rcol, weight="bold")
    c.text(MX, 232, ticker, 64, weight="bold")
    sub = t.get("name", "")
    sub += (f"  ·  Kauf {fmt_de_date(t['buy_date'])}"
            f"  →  Verkauf {fmt_de_date(t['sell_date'])}")
    c.text(MX + 12, 300, sub, 18, color=T.MUTED)

    # Fenster: ~15 Bars vor Kauf bis zum Verkauf
    idx_b = next((i for i, p in enumerate(ohlcv) if p["d"] >= t["buy_date"]), 0)
    idx_e = next((i for i in range(len(ohlcv) - 1, -1, -1)
                  if ohlcv[i]["d"] <= t["sell_date"]), len(ohlcv) - 1)
    win = ohlcv[max(0, idx_b - 15):idx_e + 1] or ohlcv
    chart_h = int(c.H * 0.40)
    ax = c.chart_axes(MX, 350, c.W - 2 * MX, chart_h)
    _style_chart(ax)
    xs = np.array([datetime.strptime(p["d"], "%Y-%m-%d").toordinal() for p in win], float)
    ys = np.array([p["c"] for p in win])
    ax.plot(xs, ys, color=T.TEXT, lw=2.5, zorder=3)
    ax.fill_between(xs, ys, ys.min(), color=T.TEXT, alpha=0.05, zorder=1)

    def _eur(v):
        return f"{v:.2f}".replace(".", ",") + " €" if v else ""

    # Kauf-Marker (grün) – Label IMMER links der gepunkteten Linie
    bx = datetime.strptime(entry["d"], "%Y-%m-%d").toordinal()
    ax.axvline(bx, color=bcol, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([bx], [entry["c"]], s=140, color=bcol, zorder=5, edgecolor=T.BG, lw=2)
    blab = f"Kauf {short_date(entry['d'])}"
    if t.get("buy_price_eur"):
        blab += "\n" + _eur(t["buy_price_eur"])
    ax.annotate(blab, (bx, entry["c"]), xytext=(-10, 16), textcoords="offset points",
                color=bcol, fontsize=14, fontweight="bold", ha="right",
                fontfamily=_FONTS["sans"])

    # Verkauf-Marker (rot) – Label IMMER links der gepunkteten Linie
    sx = datetime.strptime(exit_pt["d"], "%Y-%m-%d").toordinal()
    ax.axvline(sx, color=scol, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([sx], [exit_pt["c"]], s=140, color=scol, zorder=5, edgecolor=T.BG, lw=2)
    slab = f"Verkauf {short_date(t['sell_date'])}"
    if t.get("sell_price_eur"):
        slab += "\n" + _eur(t["sell_price_eur"])
    ax.annotate(slab, (sx, exit_pt["c"]), xytext=(-10, 16), textcoords="offset points",
                color=scol, fontsize=14, fontweight="bold", ha="right",
                fontfamily=_FONTS["sans"])

    # Mini-Legende
    c.text(MX, 350 + chart_h + 22, "● Kauf", 14, color=bcol, weight="bold")
    c.text(MX + 130, 350 + chart_h + 22, "● Verkauf", 14, color=scol, weight="bold")

    # Drei KPI-Kacheln: Rendite · Einstiegskurs · Verkaufskurs
    ky = 350 + chart_h + 70
    gap = 20
    tw = (c.W - 2 * MX - 2 * gap) // 3
    cells = [
        ("Realisierte Rendite", fmt_pct(ret) if ret is not None else "—", rcol),
        ("Einstiegskurs", _eur(t.get("buy_price_eur")) or "—", T.TEXT),
        ("Verkaufskurs", _eur(t.get("sell_price_eur")) or "—", T.TEXT),
    ]
    for i, (lab, val, col) in enumerate(cells):
        x = MX + i * (tw + gap)
        c.tile(x, ky, tw, 110, color=T.PANEL)
        c.text(x + 24, ky + 26, lab, 16, color=T.MUTED)
        c.text(x + 24, ky + 54, val, 32, color=col, weight="bold", font="mono")
    footer(c)


# ── Strategie-/Intro-Post (evergreen) ──────────────────────────────────────────
def slide_strategy_cover(c, kicker, title, subtitle):
    """Cover des Strategie-Posts: Kicker + großer (umbrechender) Titel + Untertitel."""
    header(c, "")
    target = c.W - 2 * MX
    cy = int(c.H * 0.30)
    c.text(MX, cy - 8, kicker, 22, color=T.BLUE, weight="bold")
    lines = _wrap_px(c, title, 60, target)
    for i, ln in enumerate(lines):
        c.text(MX, cy + 36 + i * 74, ln, 60, weight="bold")
    sy = cy + 36 + len(lines) * 74 + 18
    for i, ln in enumerate(_wrap_px(c, subtitle, 26, target)):
        c.text(MX, sy + i * 40, ln, 26, color=T.MUTED)
    _risk_box(c)
    footer(c)


def slide_strategy_phase(c, no, kicker, title, text):
    """Phasen-Slide: Nummern-Badge + Kicker/Titel, darunter Fließtext (umgebrochen)."""
    header(c, "")
    top = 210
    c.tile(MX, top, 88, 88, color=T.PANEL, radius=22)
    c.text(MX + 44, top + 20, str(no), 50, color=T.BLUE, weight="bold",
           font="mono", ha="center")
    c.text(MX + 116, top + 10, kicker, 20, color=T.MUTED, weight="bold")
    c.text(MX + 116, top + 40, title, 38, weight="bold")
    target = c.W - 2 * MX
    ty = top + 150
    for i, ln in enumerate(_wrap_px(c, text, 27, target)):
        c.text(MX, ty + i * 44, ln, 27, color=T.TEXT)
    _risk_box(c)
    footer(c)


def slide_strategy_cta(c, title, hl_label, hl_value, text):
    """CTA-Slide des Strategie-Posts: Titel + Performance-Chip + Fließtext + Risikobox."""
    header(c, "")
    cy = int(c.H * 0.22)
    c.text(MX, cy, title, 50, weight="bold")
    chip_top = cy + 86
    c.tile(MX, chip_top, c.W - 2 * MX, 132, color=T.PANEL)
    c.text(MX + 36, chip_top + 28, hl_label, 19, color=T.MUTED)
    c.text(MX + 36, chip_top + 60, hl_value, 50, color=T.GREEN, weight="bold", font="mono")
    target = c.W - 2 * MX
    ty = chip_top + 176
    for i, ln in enumerate(_wrap_px(c, text, 24, target)):
        c.text(MX, ty + i * 38, ln, 24, color=T.TEXT)
    _risk_box(c)
    footer(c)

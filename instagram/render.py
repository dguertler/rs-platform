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

# ── Typografie-Konstanten (einheitlich auf allen Slides) ──────────────────────
TY_H1      = 42   # Slide-Überschrift  (z. B. "Gesamteinschätzung")
TY_SUB     = 18   # Untertitel / Kontext-Zeile
TY_BODY    = 28   # Fließtext / Analysetext
TY_BODY_LH = 44   # Zeilenabstand für TY_BODY


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


def _justify_line(c, x, top, words, size, color, target_w, font="sans", weight="normal"):
    """Zeichnet eine Zeile im Blocksatz: Wörter werden auf target_w (px) verteilt."""
    try:
        r = c.fig.canvas.get_renderer()
    except Exception:
        c.fig.canvas.draw()
        r = c.fig.canvas.get_renderer()
    pt = size * 72.0 / T.DPI

    def wpx(s):
        t = c.ax.text(0, 0, s, fontsize=pt, fontfamily=_FONTS[font], fontweight=weight)
        bb = t.get_window_extent(renderer=r)
        t.remove()
        return bb.width

    if len(words) <= 1:
        c.text(x, top, words[0] if words else "", size, color=color, font=font, weight=weight)
        return
    widths = [wpx(w) for w in words]
    gap = max((target_w - sum(widths)) / (len(words) - 1), wpx(" "))
    cx = x
    for w, ww in zip(words, widths):
        c.text(cx, top, w, size, color=color, font=font, weight=weight)
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


def slide_cta(c, date_iso, question=None, account=None):
    """Abschluss-Slide: Bio-Link-Pfad + dynamische Interaktions-Frage
    (Engagement-Boost) + Pflicht-Risikohinweis.

    `question` = von Claude pro Woche aus den Trades getextete Frage; treibt die
    Kommentare. `account` = Handle für den Bio-Verweis (Default: Marke).
    """
    import textwrap
    header(c, date_iso)
    handle = account or HANDLE
    cy = int(c.H * 0.24)
    c.text(MX, cy, "Mehr Trades & Updates?", 50, weight="bold")
    # URLs sind in IG-Beiträgen nicht klickbar → strikt auf die Bio verweisen.
    c.text(MX, cy + 80, "Den Link zum Live-Depot findest du", 24, color=T.TEXT)
    c.text(MX, cy + 116, "aktuell in unserer Bio.", 24, color=T.TEXT)
    c.text(MX, cy + 168, handle, 30, color=T.BLUE, weight="bold")

    # Dynamische Interaktions-Frage (Engagement / Kommentare anfeuern)
    if question:
        qlines = textwrap.wrap(question, width=44)
        qy = cy + 236
        box_h = 60 + len(qlines) * 34
        c.tile(MX, qy, c.W - 2 * MX, box_h, color=T.PANEL)
        c.text(MX + 34, qy + 24, "DEINE MEINUNG?", 16, color=T.BLUE, weight="bold")
        for i, ln in enumerate(qlines):
            c.text(MX + 34, qy + 60 + i * 34, ln, 22, weight="bold")

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


def slide_hook_dynamic(c, date_iso, headline, metrics, kw=None):
    """Slide 1 — **Dynamic Hook** (visueller Stopper, KEIN Dashboard).

    `headline` = wöchentlich aus den Daten getextete Schlagzeile, die neugierig
    macht (hoher Alpha-Wert, Outperformance, Krisenfestigkeit, Sektor-Gewinne).
    `metrics` = Liste (label, value, color) — 1–2 prominente Kennzahlen als
    visueller Beweis direkt auf der Slide (z. B. Alpha, Gesamtrendite).
    """
    import textwrap
    header(c, date_iso)
    eyebrow = f"WOCHENUPDATE · KW {kw}" if kw else "WOCHENUPDATE"
    c.text(MX, 200, eyebrow, 24, color=T.BLUE, weight="bold")

    # Schlagzeile groß umbrechen (visueller Stopper)
    wrapped = textwrap.wrap(headline, width=20)[:4]
    size = 78 if len(wrapped) <= 3 else 62
    top = 272
    for i, ln in enumerate(wrapped):
        c.text(MX, top + i * (size + 12), ln, size, weight="bold")

    # Kennzahlen als Beweis (Chips unten)
    metrics = (metrics or [])[:2]
    n = len(metrics)
    if n:
        gap = 28
        chip_top = int(c.H * 0.64)
        tw = (c.W - 2 * MX - gap * (n - 1)) / n
        ch = 178
        for i, (label, val, col) in enumerate(metrics):
            x = MX + i * (tw + gap)
            c.tile(x, chip_top, tw, ch, color=T.PANEL)
            c.text(x + 34, chip_top + 32, label, 18, color=T.MUTED)
            c.text(x + 34, chip_top + ch - 92, val, 58, color=col,
                   weight="bold", font="mono")
    footer(c)


def slide_why(c, date_iso, text):
    """Strategisches „Warum" — minimalistische Text-Slide (KI-Kontext).

    Übergang von den Positionen zu den Einzelaktien-Deep-Dives. `text` =
    wöchentlich getextete Begründung der KI-Logik (Sektor-Rotation,
    Volatilitäts-Check, Trendbestätigung).
    """
    import textwrap
    header(c, date_iso)
    c.text(MX, 210, "HINTER DEN KULISSEN", 26, color=T.BLUE, weight="bold")
    c.text(MX, 250, "Warum die KI so entschieden hat", 18, color=T.MUTED)
    wrapped = textwrap.wrap(text, width=32)
    size = 46 if len(wrapped) <= 8 else 36
    cy = int(c.H * 0.36)
    for i, ln in enumerate(wrapped):
        c.text(MX, cy + i * (size + 16), ln, size, weight="bold")
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


def _wrap_px(text, px_width, size, factor=0.56):
    import textwrap
    width = max(8, int(px_width / max(1.0, size * factor)))
    return textwrap.wrap(text, width=width)


def _draw_paragraph(c, x, top, text, size, px_width, color=T.TEXT,
                    weight="normal", line_h=None, max_lines=None,
                    justify=True, font="sans"):
    lines = _wrap_px(text, px_width, size)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;") + " …"
    lh = line_h or int(size * 1.34)
    for i, ln in enumerate(lines):
        is_last = (i == len(lines) - 1)
        if justify and not is_last and len(ln.split()) > 1:
            _justify_line(c, x, top + i * lh, ln.split(), size, color,
                          px_width, font=font, weight=weight)
        else:
            c.text(x, top + i * lh, ln, size, color=color, weight=weight, font=font)
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
        c.text(x + w - 40, top + h // 2 - 24, f"{score}", 46, color=col,
               weight="bold", ha="right", font="mono")
        c.text(x + w - 40, top + h // 2 + 6, "/100", 24, color=T.MUTED, ha="right")


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


def _num(s):
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _draw_bookmark(c, x, top, w, h, col):
    """Lesezeichen-Icon (Save-Symbol) als Polygon."""
    from matplotlib.patches import Polygon
    notch = h * 0.28
    pts = [(x, c.y(top)), (x + w, c.y(top)), (x + w, c.y(top + h)),
           (x + w / 2, c.y(top + h - notch)), (x, c.y(top + h))]
    c.ax.add_patch(Polygon(pts, closed=True, facecolor=col, edgecolor="none",
                           zorder=11))


def _logo_card(c, x, top, w, h, ticker, radius=28):
    """Helle Karte mit Firmenlogo (contain). Fehlt das Logo: Ticker dunkel
    zentriert. So wirken auch schwarze Firmenlogos sauber auf dem dunklen Cover."""
    c.tile(x, top, w, h, color="#FFFFFF", radius=radius)
    logo = T.company_logo_file(ticker)
    pad_x, pad_y = int(w * 0.12), int(h * 0.18)
    drew = c.draw_image_contain(logo, x + pad_x, top + pad_y,
                                w - 2 * pad_x, h - 2 * pad_y) if logo else None
    if not drew:
        c.text(x + w / 2, top + h / 2 - h * 0.16, ticker,
               int(h * 0.42), weight="bold", ha="center", font="mono", color=T.BG)
    return bool(drew)


def analysis_headline(a):
    """Frage/These als Hook (erste 3 Sekunden). a['headline'] hat Vorrang
    (bespoke); sonst verdict-bewusst & pro Ticker variiert."""
    if a.get("headline"):
        return a["headline"]
    name = A.short_name(a.get("name", a["ticker"]))
    t, sc = a["ticker"], a.get("score")
    v = (a["verdict"] or "").upper()
    buy = [f"{name}: Kaufen — oder schon zu spät?",
           f"Ist {name} der nächste Verdoppler?",
           f"{t}: {sc}/100 — verdient diese Aktie den Hype?",
           f"{name}: Warum die Bullen jetzt am Drücker sind"]
    hold = [f"{name}: Kauf oder Falle?",
            f"{name} — abwarten oder zugreifen?",
            f"{t}: Top-Story, aber der richtige Preis?",
            f"{name}: Chance oder Überbewertung?"]
    watch = [f"{name}: Finger weg — oder Schnäppchen?",
             f"{t}: Mehr Risiko als Chance?",
             f"{name}: Lieber abwarten?"]
    pool = buy if v == "BUY" else (watch if v in ("WATCH", "SELL") else hold)
    return pool[sum(ord(ch) for ch in a["ticker"]) % len(pool)]


# 1) COVER — Frage-Hook + Firmenlogo (weiße Karte) + Verdict + Rating-Blöcke
def slide_analysis_cover(c, a, date_iso):
    # Top-Leiste: Marke + Tag + Datum
    lw = c.draw_logo(MX, 64, 46)
    if not lw:
        c.text(MX, 68, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 74, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")
    c.tile(MX, 140, 220, 50, color=T.PANEL_HI)
    c.text(MX + 24, 153, "AKTIENANALYSE", 17, color=T.BLUE, weight="bold")

    # HEADLINE (Frage/These) — die ersten 3 Sekunden
    hy = _draw_paragraph(c, MX, 226, analysis_headline(a), 50, c.W - 2 * MX,
                         color=T.TEXT, weight="bold", line_h=62, max_lines=3,
                         justify=False)

    # Weiße Logo-Karte (kompakter als früher, damit Rating-Blöcke Platz haben)
    card_top = max(hy + 40, 430)
    card_h = 260
    _logo_card(c, MX, card_top, c.W - 2 * MX, card_h, a["ticker"])

    # Name + Sektor
    sub = A.short_name(a["name"])
    if a.get("sector"):
        sub += f"  ·  {a['sector']}"
    c.text(MX, card_top + card_h + 22, sub, 20, color=T.MUTED)

    # Verdict-Badge (etwas kompakter)
    col = verdict_color(a["verdict"])
    verdict_top = card_top + card_h + 60
    _verdict_badge(c, MX, verdict_top, a["verdict"], a["score"], h=106)
    verdict_bottom = verdict_top + 106

    # Rating-Karten 2×2 (kompakt) unter dem Verdict-Badge
    rt = a["ratings"]
    rating_items = [
        ("Qualität",    rt.get("Qualität")),
        ("Wachstum",    rt.get("Wachstum")),
        ("Bewertung",   rt.get("Bewertung")),
        ("Katalysator", rt.get("Katalysator")),
    ]
    r_gap = 16
    r_cw = (c.W - 2 * MX - r_gap) // 2
    r_ch = 100
    vcol = verdict_color(a["verdict"])
    r_top = verdict_bottom + 14
    for i, (label, val) in enumerate(rating_items):
        row, col_i = divmod(i, 2)
        rx = MX + col_i * (r_cw + r_gap)
        ry = r_top + row * (r_ch + r_gap)
        c.tile(rx, ry, r_cw, r_ch, color=T.PANEL)
        c.text(rx + 18, ry + 10, label.upper(), 13, color=T.MUTED, weight="bold")
        c.text(rx + r_cw - 18, ry + 8,
               f"{val if val is not None else '–'}/5", 36,
               color=vcol, weight="bold", ha="right", font="mono")
        _stars(c, rx + 28, ry + 68, val, col=vcol, gap=34, s=220)
    analysis_footer(c)


# 2) GESAMTEINSCHÄTZUNG — vollständiger Investment-Case (Rating-Blöcke auf Cover)
def slide_analysis_verdict(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Gesamteinschätzung", 42, weight="bold")
    col = verdict_color(a["verdict"])
    lab = VERDICT_LABEL.get((a["verdict"] or "").upper(), "")
    c.text(MX, 248, f"{a['verdict']} · {lab}   ·   Score {a['score']}/100"
           if a["score"] is not None else f"{a['verdict']} · {lab}",
           22, color=col, weight="bold")

    # Vollständiger Investment-Case — kein Abschneiden (Rating-Blöcke sind auf Cover)
    core = " ".join(a["sections"].get(1, "").split()) or a.get("hook", "")
    _draw_paragraph(c, MX, 312, core, TY_BODY, c.W - 2 * MX,
                    color=T.TEXT, line_h=TY_BODY_LH, max_lines=20)
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
    bullets = a.get("business_bullets", [])[:8]
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


def _cases_item_data(a):
    """Bereitet Szenario-Texte + dynamische Tile-Höhen vor (kein Truncating).
    Filtert Summen-/Metazeilen (z. B. '**Summe: 30%+45%+25%=100%**') heraus."""
    import re
    sc = a["scenarios"]
    inner_w = 1080 - 2 * MX - 80   # 820 px
    body_size, body_lh = 21, 32
    head_h, pad_bot = 78, 24        # Platz für Label+Meta, Abstand unten
    sec_map = {"bull": 3, "base": 4, "bear": 5}
    items = []
    for key in ("bull", "base", "bear"):
        raw = a["sections"].get(sec_map[key], "") or sc[key]["summary"]
        raw = re.sub(r"\*?\*?\s*Summe[^.\n*]*\.?\s*\*?\*?", "", raw, flags=re.I)
        body_text = A.clean_for_slide(raw).strip()
        lines = _wrap_px(body_text, inner_w, body_size)
        rh = head_h + len(lines) * body_lh + pad_bot
        items.append({"key": key, "text": body_text, "lines": lines, "rh": rh})
    return items


def _draw_cases_blocks(c, a, items, top0=300):
    """Zeichnet Szenario-Blöcke mit dynamischer Höhe — kein Text wird abgeschnitten."""
    sc = a["scenarios"]
    inner_w = c.W - 2 * MX - 80
    body_size, body_lh, head_h = 21, 32, 78
    gap = 22
    y = top0
    for item in items:
        key = item["key"]
        col = SCEN_COLOR[key]
        rh = item["rh"]
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        c.tile(MX, y, 12, rh, color=col, radius=6)
        rng = A.fmt_range(sc[key]["range"])
        prob = sc[key]["prob"]
        c.text(MX + 40, y + 24, SCEN_LABEL[key] + " Case", 26, color=col, weight="bold")
        meta = []
        if prob is not None:
            meta.append(f"{prob}%")
        if rng:
            meta.append(rng)
        if meta:
            c.text(c.W - MX - 40, y + 28, "  ·  ".join(meta), 24,
                   color=T.TEXT, weight="bold", ha="right", font="mono")
        _draw_paragraph(c, MX + 40, y + head_h, item["text"], body_size,
                        inner_w, color=T.TEXT, line_h=body_lh)
        y += rh + gap


# 6) BULL / BASE / BEAR ERKLÄRT — dynamische Tile-Höhen, kein Überlappen/Abschneiden
def slide_analysis_cases(c, a, date_iso, items=None):
    """items: Teilliste aus _cases_item_data() für Overflow-Splits.
    Titel passt sich an (2 von 3 Szenarien → 'Bull & Base Case erklärt')."""
    if items is None:
        items = _cases_item_data(a)
    keys = [d["key"] for d in items]
    if len(keys) == 3:
        title = "Die drei Szenarien erklärt"
    else:
        title = " & ".join(SCEN_LABEL[k] + " Case" for k in keys) + " erklärt"
    analysis_header(c, a, date_iso)
    c.text(MX, 184, title, 42, weight="bold")
    c.text(MX, 240, "Was hinter Bull, Base und Bear steckt", 18, color=T.MUTED)
    _draw_cases_blocks(c, a, items)
    analysis_footer(c)


# 7) PROFI-FAZIT — Kernaussage + Peers + Verweis auf Caption
def slide_analysis_fazit(c, a, date_iso):
    analysis_header(c, a, date_iso)
    col = verdict_color(a["verdict"])
    c.text(MX, 184, "Profi-Fazit", 42, weight="bold")
    _verdict_badge(c, MX, 244, a["verdict"], a["score"], h=120)

    import re as _re
    raw11 = a["sections"].get(11, "")
    raw11 = _re.sub(r"\n-\s*(Qualität|Wachstum|Bewertung|Katalysator)[^\n]*", "", raw11)
    raw11 = _re.sub(r"\*\*([^*]+)\*\*", r"\1", raw11)
    core = A.clean_for_slide(raw11.strip()) or a.get("fazit_core", "")
    y = _draw_paragraph(c, MX, 396, core, TY_BODY, c.W - 2 * MX,
                        color=T.TEXT, line_h=TY_BODY_LH, max_lines=10)

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


# 6b) BEWERTUNG — „KGV-Illusion" (Abschnitt 7), ohne aktuellen Kurs
def slide_analysis_valuation(c, a, date_iso):
    analysis_header(c, a, date_iso)
    pe = A.pe_multiples(a["sections"].get(7, ""))
    illusion = (pe["trailing"] and pe["forward"]
                and _num(pe["trailing"]) > _num(pe["forward"]) * 1.8)
    title = "Bewertung: die KGV-Illusion" if illusion else "Bewertung"
    c.text(MX, 184, title, 42, weight="bold")
    c.text(MX, 240, "Warum das optische KGV in die Irre führt"
           if illusion else "Bewertung im Zykluskontext", 18, color=T.MUTED)

    y = 300
    if pe["trailing"] or pe["forward"]:
        gap = 26
        cw = (c.W - 2 * MX - gap) // 2
        ch = 150
        if pe["trailing"]:
            c.tile(MX, y, cw, ch, color=T.PANEL)
            c.tile(MX, y, 10, ch, color=T.RED, radius=5)
            c.text(MX + 34, y + 26, "TRAILING-KGV", 16, color=T.MUTED, weight="bold")
            c.text(MX + 34, y + 56, pe["trailing"] + "x", 50, color=T.RED,
                   weight="bold", font="mono")
            c.text(MX + 34, y + 118, "optisch teuer · Artefakt", 16, color=T.MUTED)
        if pe["forward"]:
            x2 = MX + cw + gap
            c.tile(x2, y, cw, ch, color=T.PANEL)
            c.tile(x2, y, 10, ch, color=T.GREEN, radius=5)
            c.text(x2 + 34, y + 26, "FORWARD-KGV", 16, color=T.MUTED, weight="bold")
            c.text(x2 + 34, y + 56, pe["forward"] + "x", 50, color=T.GREEN,
                   weight="bold", font="mono")
            c.text(x2 + 34, y + 118, "die relevante Kennzahl", 16, color=T.MUTED)
        y += ch + 40

    txt = A.clean_for_slide(a["sections"].get(7, ""))
    _draw_paragraph(c, MX, y, txt, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=15)
    analysis_footer(c)


# 7b) RISIKO & REALITÄTSCHECK — Positionierung/Psychologie (Abschnitt 8), ohne GWS
def slide_analysis_risk(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Risiko & Realitätscheck", 42, weight="bold")
    c.text(MX, 240, "Positionierung, Erwartungen, Volatilität", 18, color=T.MUTED)

    # Positionsgrößen-Hinweis als Warnchip (falls im Fazit genannt)
    y = 300
    psz = A.position_size(a.get("fazit", ""))
    if psz:
        c.tile(MX, y, c.W - 2 * MX, 96, color=T.PANEL)
        c.tile(MX, y, 10, 96, color=T.AMBER, radius=5)
        c.text(MX + 34, y + 24, "POSITIONSGRÖSSE BEGRENZEN", 16,
               color=T.AMBER, weight="bold")
        c.text(c.W - MX - 34, y + 26, psz, 40, color=T.AMBER, weight="bold",
               ha="right", font="mono")
        y += 96 + 36

    body = A.clean_for_slide(a["sections"].get(8, "")) or \
        A.clean_for_slide(a["scenarios"]["bear"]["summary"])
    _draw_paragraph(c, MX, y, body, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=16)
    analysis_footer(c)


# 9b) SPEICHERN & MITREDEN — Engagement-CTA (Save + Community-Frage)
def slide_analysis_cta(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 200, "Speichern & mitreden", 46, weight="bold")

    # Save-Box
    c.tile(MX, 300, c.W - 2 * MX, 150, color=T.PANEL)
    c.tile(MX, 300, 12, 150, color=T.BLUE, radius=6)
    _draw_bookmark(c, MX + 46, 336, 44, 78, T.BLUE)
    c.text(MX + 130, 326, "Speichere diesen Beitrag", 30, weight="bold")
    c.text(MX + 130, 372, "für deine Watchlist — die ganze Analyse auf einen Blick.",
           19, color=T.MUTED)

    # Community-Frage
    name = A.short_name(a["name"])
    c.tile(MX, 500, c.W - 2 * MX, 240, color=T.PANEL_HI)
    c.text(MX + 40, 532, "DEINE MEINUNG?", 16, color=T.BLUE, weight="bold")
    _draw_paragraph(c, MX + 40, 576,
                    f"{name}: berechtigter Hype oder überhitzt? "
                    f"Schreib deine These in die Kommentare.", 28,
                    c.W - 2 * MX - 80, color=T.TEXT, weight="bold", line_h=42,
                    max_lines=4)

    # Folgen-CTA
    c.text(MX, 800, "Folge für mehr Profi-Analysen", 30, color=T.TEXT, weight="bold")
    c.text(MX, 846, HANDLE, 34, color=T.BLUE, weight="bold")
    c.text(MX, 904, "1–2 Aktienanalysen pro Woche · faceless · datengetrieben",
           19, color=T.MUTED)
    analysis_footer(c)


# 6b) FUNDAMENTALE QUALITÄT — Abschnitt 6 (Bilanz, Margen, Kapitalrendite)
def slide_analysis_fundamentals(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Fundamentale Qualität", 42, weight="bold")
    c.text(MX, 240, "Bilanz, Margen, Kapitalrendite", 18, color=T.MUTED)
    txt = A.clean_for_slide(a["sections"].get(6, ""))
    _draw_paragraph(c, MX, 304, txt, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=20)
    analysis_footer(c)


# 9b) TECHNISCHES BILD & MOMENTUM — Abschnitt 9 (Kurs & GWS herausgefiltert)
def slide_analysis_technical(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Technisches Bild & Momentum", 42, weight="bold")
    c.text(MX, 240, "Trend, Volatilität, Warnsignale", 18, color=T.MUTED)
    txt = A.clean_for_slide(a["sections"].get(9, ""))
    _draw_paragraph(c, MX, 304, txt, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=20)
    analysis_footer(c)


# ── Reel-Teaser (9:16): kurz & knackig, leitet aufs Karussell um ───────────────
def reel_header(c, date_iso):
    lw = c.draw_logo(MX, 80, 50)
    if not lw:
        c.text(MX, 84, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 92, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")
    c.tile(MX, 168, 240, 54, color=T.PANEL_HI)
    c.text(MX + 24, 182, "AKTIENANALYSE", 18, color=T.BLUE, weight="bold")


def slide_reel_hook(c, a, date_iso):
    reel_header(c, date_iso)
    # Frage/These groß (erste 3 Sekunden)
    hy = _draw_paragraph(c, MX, 300, analysis_headline(a), 58, c.W - 2 * MX,
                         color=T.TEXT, weight="bold", line_h=72, max_lines=3,
                         justify=False)
    card_top = max(hy + 60, 600)
    _logo_card(c, MX, card_top, c.W - 2 * MX, 470, a["ticker"])
    sub = A.short_name(a["name"])
    if a.get("sector"):
        sub += f"  ·  {a['sector']}"
    c.text(MX, card_top + 470 + 34, sub, 24, color=T.MUTED)
    _verdict_badge(c, MX, card_top + 470 + 86, a["verdict"], a["score"], h=150)
    analysis_footer(c)


def slide_reel_scenarios(c, a, date_iso):
    reel_header(c, date_iso)
    _scenario_rows(c, a, 320, "scenarios",
                   "Szenarien · 12–18 Monate",
                   "Wahrscheinlichkeit & Kursziel — Bull + Base + Bear = 100 %")
    analysis_footer(c)


def slide_reel_takeaway(c, a, date_iso):
    reel_header(c, date_iso)
    col = verdict_color(a["verdict"])
    c.text(MX, 320, "Das Wichtigste", 48, weight="bold")
    _verdict_badge(c, MX, 410, a["verdict"], a["score"], h=150)
    core = a.get("fazit_core") or A._first_sentence(a["sections"].get(11, ""), 280)
    y = _draw_paragraph(c, MX, 620, core, 28, c.W - 2 * MX,
                        color=T.TEXT, line_h=42, max_lines=6)
    rt = a["ratings"]
    items = [("Qualität", rt.get("Qualität")), ("Wachstum", rt.get("Wachstum")),
             ("Bewertung", rt.get("Bewertung")), ("Katalysator", rt.get("Katalysator"))]
    top0 = max(y + 60, 1080)
    for i, (label, val) in enumerate(items):
        yy = top0 + i * 120
        c.text(MX, yy, label.upper(), 22, color=T.MUTED, weight="bold")
        _stars(c, MX + 360, yy + 14, val, col=col, gap=58, s=620)
        c.text(c.W - MX, yy, f"{val if val is not None else '–'}/5", 30,
               color=T.TEXT, weight="bold", ha="right", font="mono")
    analysis_footer(c)


def slide_reel_cta(c, a, date_iso):
    """Hybrid-Trick: das Reel leitet auf den vollständigen Karussell-Post um."""
    reel_header(c, date_iso)
    col = verdict_color(a["verdict"])
    c.text(MX, 460, "Willst du die", 56, weight="bold")
    c.text(MX, 532, "ganze Analyse?", 56, color=col, weight="bold")
    box_top = 700
    c.tile(MX, box_top, c.W - 2 * MX, 470, color=T.PANEL)
    c.tile(MX, box_top, 12, 470, color=T.BLUE, radius=6)
    _draw_paragraph(c, MX + 50, box_top + 50,
                    f"Die komplette {a['ticker']}-Analyse mit allen Zahlen, "
                    f"Szenarien und Kurszielen findest du als Karussell-Post "
                    f"auf meinem Profil.", 30, c.W - 2 * MX - 100,
                    color=T.TEXT, line_h=46, max_lines=6)
    c.text(MX + 50, box_top + 330, "Profil öffnen", 26, color=T.MUTED)
    c.text(MX + 50, box_top + 372, HANDLE, 40, color=T.BLUE, weight="bold")
    # nach oben zeigende Dreiecke (zum Profil/Feed)
    for i in range(3):
        c.ax.scatter(c.W - MX - 60 - i * 36, c.y(box_top + 360), s=170,
                     marker="^", color=T.BLUE, edgecolor="none", zorder=12)
    c.text(MX, 1230, f"Folge {HANDLE} für 1–2 Analysen pro Woche", 24,
           color=T.MUTED)
    analysis_footer(c)

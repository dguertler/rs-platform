"""
Render-Engine: zeichnet einzelne Slides als PNG im AI-Alpha-Selection-Design.
Reines matplotlib, kein Browser nötig. Jede Slide funktioniert in beiden
Formaten (Carousel 4:5 / Reel 9:16) über pixelbasierte Layout-Koordinaten.
"""
import os
from datetime import datetime

import numpy as np
import matplotlib

matplotlib.use("Agg")
# Dollar-Zeichen ($3,37) NICHT als LaTeX-Mathmodus interpretieren — sonst werden
# Zeichen zwischen zwei $ kursiv gesetzt und Leerzeichen verschluckt.
try:
    matplotlib.rcParams["text.parse_math"] = False
except (KeyError, ValueError):
    pass
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from . import theme as T

_FONTS = T.register_fonts()
# Kein @-Handle auf Slides/Reels (für den IG-Algorithmus unnötig) —
# es erscheint nur der Markenname.
BRAND_NAME = "AI Alpha Selection"
BRAND = "AI ALPHA SELECTION"
MX = 90        # Seitenrand für alle Innen-Slides (ab Slide 2)
COVER_MX = 195  # Seitenrand nur für Slide 1 (Cover/Hook) — schützt gegen seitlichen
               # Beschnitt im Instagram-Profil-Raster (≈ 18 % der Breite)

# ── Typografie-Konstanten (einheitlich auf allen Slides) ──────────────────────
TY_H1      = 42   # Slide-Überschrift  (z. B. "Gesamteinschätzung")
TY_SUB     = 22   # Untertitel / Kontext-Zeile
TY_BODY    = 28   # Fließtext / Analysetext
TY_BODY_LH = 44   # Zeilenabstand für TY_BODY


# ── Formatierungs-Helfer ──────────────────────────────────────────────────────
def fmt_pct(x, decimals=1, signed=True):
    sign = ("+" if x >= 0 else "−") if signed else ""
    return f"{sign}{abs(x) * 100:.{decimals}f}".replace(".", ",") + "%"


def fmt_eur(v):
    """Deutschen Preis mit Tausenderpunkt: 1.224,20 €"""
    if v is None:
        return "—"
    s = f"{v:,.2f}"                              # "1,224.20"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


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
    lines = textwrap.wrap(T.DISCLAIMER_SHORT, width=130)
    for i, ln in enumerate(lines):
        c.text(MX, c.H - 128 + i * 28, ln, 14, color=T.MUTED)


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
    MX = COVER_MX
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
    c.text(MX, 248, "Indexiert auf 100 zum Startzeitpunkt", 22, color=T.MUTED)

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
    c.text(MX + 30, ky + 24, "AI Alpha Selection", 20, color=T.MUTED)
    c.text(MX + 30, ky + 50, fmt_pct(wf_ret), 40, color=T.GREEN, weight="bold", font="mono")
    c.tile(MX + half + 30, ky, half, 104, color=T.PANEL)
    c.text(MX + half + 60, ky + 24, "NASDAQ-100", 20, color=T.MUTED)
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
            c.text(x + 22, y + 24, lab, 17, color=T.MUTED)
            c.text(x + 22, y + 50, val, 36, color=col, weight="bold", font="mono")
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
                xytext=(-12, 28), textcoords="offset points",
                color=color, fontsize=15, fontweight="bold",
                ha="right", fontfamily=_FONTS["sans"],
                bbox=dict(boxstyle="square,pad=0.3", fc=T.BG, ec="none", alpha=0.9))

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
    Kommentare. Kein @-Handle auf der Slide (folgt aus IG-Bio-Konvention).

    Risikohinweis: 16 px (2 Stufen über 12 px) + _draw_paragraph/_wrap_px
    wie Aktienanalysen — Text füllt volle Breite links → rechts ohne halbe Zeilen.
    """
    header(c, date_iso)
    cy = int(c.H * 0.20)
    c.text(MX, cy, "Mehr Trades & Updates?", 54, weight="bold")
    # Bio-Text als Paragraph: füllt volle Breite links → rechts (kein hardcodierter Umbruch)
    bio = ("Den Link zum wikifolio AI Alpha Selection "
           "findest du in unserer Bio.")
    bio_bottom = _draw_paragraph(c, MX, cy + 92, bio, 26, c.W - 2 * MX,
                                 color=T.TEXT, line_h=40)

    # Interaktions-Frage — zentriert zwischen Bio-Text und Risikohinweis-Trennlinie
    sep_y = c.H - 260
    if question:
        inner_w = c.W - 2 * MX - 44   # 8 px Balken + 36 px Inset
        qlines = _wrap_px(question, inner_w, 32)
        # Box-Höhe: 28px oben + 24px Label + 40px Abstand + Zeilentext + 28px unten
        box_h = 28 + 24 + 40 + len(qlines) * 54 + 28
        # Mitte zwischen Ende Bio-Text und Beginn Separator
        qy = int((bio_bottom + (sep_y - box_h)) / 2)
        c.tile(MX, qy, c.W - 2 * MX, box_h, color=T.PANEL)
        c.tile(MX, qy, 8, box_h, color=T.BLUE, radius=5)
        c.text(MX + 36, qy + 28, "DEINE MEINUNG?", 24, color=T.BLUE, weight="bold")
        for i, ln in enumerate(qlines):
            c.text(MX + 36, qy + 92 + i * 54, ln, 32, weight="bold")

    # Risikohinweis — plain text wie Analyse-Footer, kein Kasten
    disc = T.DISCLAIMER_LONG.split("\n", 1)[1] if "\n" in T.DISCLAIMER_LONG else T.DISCLAIMER_LONG
    c.ax.plot([MX, c.W - MX], [c.y(sep_y), c.y(sep_y)], color=T.GRID, lw=1.5)
    c.text(MX, sep_y + 22, "Risikohinweis & Disclaimer", 20, color=T.MUTED, weight="bold")
    _draw_paragraph(c, MX, sep_y + 56, disc, 18, c.W - 2 * MX,
                    color=T.MUTED, line_h=30)


def slide_hook_dynamic(c, date_iso, headline, metrics, kw=None):
    """Slide 1 — **Dynamic Hook** (visueller Stopper, KEIN Dashboard).

    `headline` = wöchentlich aus den Daten getextete Schlagzeile, die neugierig
    macht (hoher Alpha-Wert, Outperformance, Krisenfestigkeit, Sektor-Gewinne).
    `metrics` = Liste (label, value, color) — 1–2 prominente Kennzahlen als
    visueller Beweis direkt auf der Slide (z. B. Alpha, Gesamtrendite).
    """
    MX = COVER_MX
    import textwrap
    header(c, date_iso)
    eyebrow = f"WOCHENUPDATE · KW {kw}" if kw else "WOCHENUPDATE"
    c.text(MX, 200, eyebrow, 28, color=T.BLUE, weight="bold")

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
            c.text(x + 34, chip_top + 32, label, 22, color=T.MUTED)
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
    c.text(MX, 210, "HINTER DEN KULISSEN", 30, color=T.BLUE, weight="bold")
    c.text(MX, 254, "Warum die KI so entschieden hat", 22, color=T.MUTED)
    wrapped = textwrap.wrap(text, width=32)
    size = 46 if len(wrapped) <= 8 else 36
    cy = int(c.H * 0.36)
    for i, ln in enumerate(wrapped):
        c.text(MX, cy + i * (size + 16), ln, size, weight="bold")
    footer(c)


# ── Wochenreport-Slides (report-getrieben) ─────────────────────────────────────
def slide_hook_weekly(c, date_iso, kw, period, week_perf, total_perf):
    MX = COVER_MX
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
           22, color=T.MUTED)

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
        c.text(MX, 252, subtitle, 22, color=T.MUTED)
    rows = rows[:5]
    top0 = 310
    gap = 22
    rh = min(150, int((c.H * 0.56 - gap * (len(rows) - 1)) / max(1, len(rows))))
    for i, row in enumerate(rows):
        y = top0 + i * (rh + gap)
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        # farbiger Akzentbalken links
        c.tile(MX, y, 10, rh, color=row["color"], radius=5)
        c.text(MX + 42, y + rh / 2 - 32, row["main"], 34, weight="bold")
        if row.get("sub"):
            c.text(MX + 42, y + rh / 2 + 10, row["sub"], 26, color=T.SUBTLE)
        c.text(c.W - MX - 40, y + rh / 2 - 26, row["value"], 44,
               color=row["color"], weight="bold", ha="right",
               font=row.get("value_font", "mono"))
    footer(c)


def slide_featured(c, date_iso, feat, label="AKTIE DER WOCHE"):
    """Kursverlauf mit Kauf-Signal (blau) + eingearbeiteten weiteren Signalen."""
    header(c, date_iso)
    ticker, ohlcv = feat["ticker"], feat["ohlcv"]
    entry, ret = feat["entry"], feat["ret"]
    rcol = T.GREEN if (ret or 0) >= 0 else T.RED   # Farbe für Renditewert
    buy_col, sell_col = T.GREEN, T.RED             # Konvention: Kauf grün, Verkauf rot
    c.text(MX, 200, label, 22, color=T.BLUE, weight="bold")
    c.text(MX, 232, ticker, 64, weight="bold")
    sub = feat.get("name", "")
    if feat.get("buy_date"):
        sub += f"  ·  Kauf {fmt_de_date(feat['buy_date'])}"
    if sub:
        c.text(MX + 12, 300, sub, 20, color=T.MUTED)

    # Fenster: ~25 Bars vor Kauf bis heute (bei abgeschlossenem Trade bis kurz nach Verkauf)
    idx = next((i for i, p in enumerate(ohlcv) if p["d"] >= feat["buy_date"]), 0)
    n_before = idx - max(0, idx - 25)   # Anzahl Bars links vom Kaufpunkt im Fenster
    end_i = len(ohlcv)
    if feat.get("closed") and feat.get("sells"):
        last_sell = max((s.get("date") or s.get("sell_date") or "") for s in feat["sells"])
        if last_sell:
            j = next((i for i, p in enumerate(ohlcv) if p["d"] > last_sell), len(ohlcv))
            end_i = min(len(ohlcv), j + 4)
    sub = ohlcv[max(0, idx - 25):end_i]
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

    # weitere Kauf-Signale (klein, grün)
    has_extra = False
    for s in feat.get("signals", []):
        sd = s.get("signal_date", "")
        if sd >= entry["d"]:   # Kaufdatum oder danach → kein "weiteres Signal"
            continue
        pt = _on(sd)
        if pt:
            has_extra = True
            ax.scatter([pt[0]], [pt[1]], s=42, color=buy_col, zorder=4,
                       edgecolor=T.BG, lw=1.5, alpha=0.6)

    # Verkaufs-Signale (groß, rot) — falls die Position (teil-)verkauft wurde
    drawn_sell = False
    for sl in feat.get("sells", []) or []:
        sd = sl.get("date") or sl.get("sell_date")
        pt = _on(sd) if sd else None
        if not pt:
            continue
        sx, sy = pt
        ax.axvline(sx, color=sell_col, lw=2, ls=(0, (4, 4)), zorder=2)
        ax.scatter([sx], [sy], s=140, color=sell_col, zorder=5, edgecolor=T.BG, lw=2)
        # Beschriftung nach links setzen (Verkäufe liegen meist nahe am rechten Rand)
        ax.annotate(f"Verkauf {short_date(sd)}", (sx, sy),
                    xytext=(-12, -32), textcoords="offset points",
                    color=sell_col, fontsize=15, fontweight="bold",
                    ha="right", fontfamily=_FONTS["sans"],
                    bbox=dict(boxstyle="square,pad=0.3", fc=T.BG, ec="none", alpha=0.9))
        drawn_sell = True

    # Kauf-Signal (groß, grün)
    # Nahe linkem Rand (n_before < 3): Label nach rechts, sonst nach links
    ex = datetime.strptime(entry["d"], "%Y-%m-%d").toordinal()
    ax.axvline(ex, color=buy_col, lw=2, ls=(0, (4, 4)), zorder=2)
    ax.scatter([ex], [entry["c"]], s=140, color=buy_col, zorder=5, edgecolor=T.BG, lw=2)
    _ha_buy = "left" if n_before < 3 else "right"
    _ox_buy = 14 if n_before < 3 else -12
    ax.annotate(f"Kauf {short_date(entry['d'])}", (ex, entry["c"]),
                xytext=(_ox_buy, 28), textcoords="offset points",
                color=buy_col, fontsize=15, fontweight="bold",
                ha=_ha_buy, fontfamily=_FONTS["sans"],
                bbox=dict(boxstyle="square,pad=0.3", fc=T.BG, ec="none", alpha=0.9))

    # Mini-Legende (Kauf grün · Verkauf rot · weitere Kauf-Signale)
    # Schriftgröße = 20px (identisch zu KPI-Chip-Labels darunter)
    ly = 350 + chart_h + 22
    c.text(MX, ly, "● Kauf", 20, color=buy_col, weight="bold")
    lx = MX + 160
    if drawn_sell:
        c.text(lx, ly, "● Verkauf", 20, color=sell_col, weight="bold")
        lx += 215
    if has_extra:
        c.text(lx, ly, "● weitere Kauf-Signale", 20, color=buy_col, alpha=0.7)

    # KPI-Kacheln
    ky = 350 + chart_h + 76
    half = (c.W - 2 * MX - 30) // 2
    sp = feat.get("sell_price_eur")
    bp = feat.get("buy_price_eur")
    lbl1 = "Realisierter Gewinn" if feat.get("closed") else "Wertzuwachs seit Kauf"

    if feat.get("closed") and (sp or bp):
        # Abgeschlossener Trade: links Rendite, rechts ZWEI Kacheln (Eintritt + Austritt)
        tile_h = 95
        tile_gap = 12
        total_h = tile_h * 2 + tile_gap
        # Linke Kachel (volle Höhe, vertikal zentriert)
        c.tile(MX, ky, half, total_h, color=T.PANEL)
        c.text(MX + 30, ky + total_h // 2 - 36, lbl1, 20, color=T.MUTED)
        c.text(MX + 30, ky + total_h // 2 + 4, fmt_pct(ret) if ret is not None else "—",
               40, color=rcol, weight="bold", font="mono")
        # Rechte Kachel oben: Eintrittskurs
        c.tile(MX + half + 30, ky, half, tile_h, color=T.PANEL)
        c.text(MX + half + 60, ky + 20, "Eintrittskurs", 20, color=T.MUTED)
        c.text(MX + half + 60, ky + 50, fmt_eur(bp), 34, weight="bold", font="mono")
        # Rechte Kachel unten: Austrittskurs
        c.tile(MX + half + 30, ky + tile_h + tile_gap, half, tile_h, color=T.PANEL)
        c.text(MX + half + 60, ky + tile_h + tile_gap + 20, "Austrittskurs", 20, color=T.MUTED)
        c.text(MX + half + 60, ky + tile_h + tile_gap + 50, fmt_eur(sp), 34,
               weight="bold", font="mono")
    else:
        # Offene Position: zwei Kacheln nebeneinander (unverändert)
        c.tile(MX, ky, half, 110, color=T.PANEL)
        c.text(MX + 30, ky + 26, lbl1, 20, color=T.MUTED)
        c.text(MX + 30, ky + 56, fmt_pct(ret) if ret is not None else "—", 40,
               color=rcol, weight="bold", font="mono")
        c.tile(MX + half + 30, ky, half, 110, color=T.PANEL)
        if bp:
            c.text(MX + half + 60, ky + 26, "Einstiegskurs", 20, color=T.MUTED)
            c.text(MX + half + 60, ky + 56, fmt_eur(bp), 40, weight="bold", font="mono")
        else:
            c.text(MX + half + 60, ky + 26, "Kaufdatum", 20, color=T.MUTED)
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


def _wrap_px(text, px_width, size, factor=0.50, lang="de"):
    """Bricht deutschen Text pixelbreitenbasiert um.

    factor: durchschnittliche Zeichenbreite / Schriftgröße (Liberation Sans ≈ 0.50).
    lang='de': Silbentrennung via pyphen (de_DE) — verhindert halbvolle Zeilen durch
               lange deutsche Komposita; zeigt Trennstrich nur am echten Zeilenende.
    lang=None: kein pyphen (für englische Texte oder wenn pyphen nicht installiert).

    Entspricht CSS: text-align:left; hyphens:auto; word-break:break-word; lang='de'.
    """
    import textwrap
    target = max(8, int(px_width / max(1.0, size * factor)))

    dic = None
    if lang == "de":
        try:
            import pyphen
            dic = pyphen.Pyphen(lang="de_DE")
        except ImportError:
            pass

    if dic is None:
        return textwrap.wrap(text, width=target, break_long_words=True)

    # Zeilenweise aufbauen mit Silbentrennung am rechtesten Silbenpunkt
    words = text.split()
    lines = []
    current: list[str] = []
    cur_len = 0  # Zeichenanzahl der laufenden Zeile

    for word in words:
        wlen = len(word)
        needed = wlen + (1 if current else 0)

        if cur_len + needed <= target:
            current.append(word)
            cur_len += needed
        else:
            space_left = target - cur_len - (1 if current else 0)
            broke = False

            # Silbentrennung nur für lange Wörter ohne echten Bindestrich
            if wlen >= 10 and "-" not in word and space_left >= 3:
                hyph = dic.inserted(word)          # z. B. "Ein-tritts-wahr-schein-..."
                parts = hyph.split("-")
                best_pos = 0
                pos = 0
                for part in parts[:-1]:            # letzten Part nie trennen
                    pos += len(part)
                    if pos + 1 <= space_left:      # Präfix + Trennstrich passt
                        best_pos = pos

                if best_pos > 0:
                    current.append(word[:best_pos] + "-")   # z. B. "Eintritts-"
                    lines.append(" ".join(current))
                    current = [word[best_pos:]]              # Rest auf neue Zeile
                    cur_len = len(word[best_pos:])
                    broke = True

            if not broke:
                if current:
                    lines.append(" ".join(current))
                current = [word]
                cur_len = wlen

    if current:
        lines.append(" ".join(current))

    return lines


def _draw_paragraph(c, x, top, text, size, px_width, color=T.TEXT,
                    weight="normal", line_h=None, max_lines=None,
                    justify=False, font="sans"):
    """Fließtext-Block, linksbündig (justify=False Standard).

    Nutzt _wrap_px mit German-Silbentrennung: lange Komposita werden am
    rechtesten Silbenpunkt getrennt, Trennstrich nur am echten Zeilenende.
    justify=True nur für abgegrenzte Boxen (z. B. CTA-Disclaimer).
    """
    lines = _wrap_px(text, px_width, size)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;-") + " …"
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
    """Kompakter Marken-Header für Innen-Slides: Brand-Logo links, Firmen-Logo
    rechts auf weißer Karte (damit dunkle/transparente Logos sichtbar sind)."""
    lw = c.draw_logo(MX, 62, 52)
    if not lw:
        c.text(MX, 66, BRAND, 20, color=T.TEXT, weight="bold")
    _company_logo_chip(c, a["ticker"], top=50)
    c.ax.plot([MX, c.W - MX], [c.y(140), c.y(140)], color=T.GRID, lw=1.5)


def analysis_footer(c):
    import textwrap
    c.ax.plot([MX, c.W - MX], [c.y(c.H - 150), c.y(c.H - 150)], color=T.GRID, lw=1.5)
    lines = textwrap.wrap(T.DISCLAIMER_ANALYSE_SHORT, width=120)
    for i, ln in enumerate(lines):
        c.text(MX, c.H - 128 + i * 28, ln, 16, color=T.MUTED)


def _company_logo_chip(c, ticker, top=52, card_w=156, card_h=66):
    """Firmenlogo oben rechts auf weißer Karte (für Innen-Slides ab Slide 2).
    Größe am AMD-Logo der Analyse-Seiten orientiert; weißer Hintergrund, damit
    dunkle/transparente Logos sauber sichtbar sind."""
    logo = T.company_logo_file(ticker)
    img = _trim_logo(logo) if logo else None
    if img is None:
        return False
    cx = c.W - MX - card_w
    c.tile(cx, top, card_w, card_h, color="#FFFFFF", radius=14)
    _draw_logo_contain(c, img, cx + 14, top + 10, card_w - 28, card_h - 20)
    return True


def _verdict_badge(c, x, top, verdict, score, w=None, h=120):
    col = verdict_color(verdict)
    w = w or (c.W - 2 * MX)
    c.tile(x, top, w, h, color=T.PANEL)
    c.tile(x, top, 12, h, color=col, radius=6)
    lab = VERDICT_LABEL.get((verdict or "").upper(), verdict or "—")
    c.text(x + 40, top + 24, "EINSCHÄTZUNG", TY_BODY, color=T.TEXT, weight="bold")
    c.text(x + 40, top + 24 + TY_BODY_LH, f"{verdict} · {lab}", 40, color=col, weight="bold")
    if score is not None:
        # Zahl groß, darunter "von 100 Punkten" — gestapelt rechts im Badge
        c.text(x + w - 40, top + 16, str(score), 46,
               color=col, weight="bold", ha="right", font="mono")
        c.text(x + w - 40, top + 66, "von 100 Punkten", 20,
               color=col, ha="right")


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


def _trim_logo(path):
    """Lädt ein Logo und schneidet transparente UND weiße Ränder weg, damit der
    sichtbare Schriftzug sauber zentriert werden kann (unabhängig davon, wie viel
    Leerraum das PNG eingebacken hat). Gibt ein PIL-RGBA-Bild oder None."""
    try:
        from PIL import Image, ImageChops
        img = Image.open(path).convert("RGBA")
        bbox = img.getbbox()                      # transparente Ränder
        if bbox:
            img = img.crop(bbox)
        # weiße Ränder: transparent auf Weiß komponieren, dann Differenz zu Weiß
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        comp = Image.alpha_composite(bg, img).convert("RGB")
        diff = ImageChops.difference(comp, Image.new("RGB", img.size, (255, 255, 255)))
        wbbox = diff.getbbox()
        if wbbox:
            img = img.crop(wbbox)
        return img
    except Exception:
        return None


def _draw_logo_contain(c, img, x, top, w, h, zorder=10):
    """Zeichnet ein (bereits getrimmtes) PIL-Logo größtmöglich INNERHALB der Box,
    Seitenverhältnis erhalten, horizontal + vertikal zentriert."""
    from PIL import Image
    iw, ih = img.size
    scale = min(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    arr = np.asarray(img.resize((nw, nh), Image.LANCZOS))
    ox = int(x + (w - nw) / 2)
    oy_top = top + (h - nh) / 2
    c.fig.figimage(arr, xo=ox, yo=int(c.H - oy_top - nh), zorder=zorder)
    return nw, nh


def _logo_card(c, x, top, w, h, ticker, radius=28):
    """Helle Karte mit Firmenlogo — getrimmt und mittig (horizontal + vertikal).
    Fehlt das Logo: Ticker dunkel zentriert."""
    c.tile(x, top, w, h, color="#FFFFFF", radius=radius)
    logo = T.company_logo_file(ticker)
    img = _trim_logo(logo) if logo else None
    if img is not None:
        # Logo füllt ~80 % Breite / ~62 % Höhe der Karte, exakt zentriert
        _draw_logo_contain(c, img, x + w * 0.10, top + h * 0.19,
                           w * 0.80, h * 0.62)
        return True
    c.text(x + w / 2, top + h / 2 - h * 0.16, ticker,
           int(h * 0.42), weight="bold", ha="center", font="mono", color=T.BG)
    return False


def analysis_headline(a):
    """Frage/These als Hook (erste 3 Sekunden). a['headline'] hat Vorrang
    (bespoke); sonst verdict-bewusst & pro Ticker variiert."""
    if a.get("headline"):
        return a["headline"]
    name = A.short_name(a.get("name", a["ticker"]))
    t, sc = a["ticker"], a.get("score")
    v = (a["verdict"] or "").upper()
    buy = ["Kaufen — oder schon zu spät?",
           f"Ist {name} der nächste Verdoppler?",
           f"Score {sc}/100 — verdient diese Aktie den Hype?",
           f"Warum die Bullen bei {name} jetzt am Drücker sind"]
    hold = [f"{name}: Kauf oder Falle?",
            f"{name} — abwarten oder zugreifen?",
            f"{t}: Top-Story, aber der richtige Preis?",
            f"{name}: Chance oder Überbewertung?"]
    watch = [f"{name}: Finger weg — oder Schnäppchen?",
             f"{t}: Mehr Risiko als Chance?",
             f"{name}: Lieber abwarten?"]
    if v == "BUY":
        return buy[0]  # immer "Kaufen — oder schon zu spät?" für BUY-Verdicts
    pool = watch if v in ("WATCH", "SELL") else hold
    return pool[sum(ord(ch) for ch in a["ticker"]) % len(pool)]


# 1) COVER — Frage-Hook + Firmenlogo (weiße Karte) + Verdict + Rating-Blöcke
def slide_analysis_cover(c, a, date_iso):
    MX = COVER_MX
    footer_line = c.H - 150

    # Top-Leiste: Marke + Datum
    lw = c.draw_logo(MX, 64, 46)
    if not lw:
        c.text(MX, 68, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 74, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")

    # HEADLINE — 60 px, eine Zeile tiefer (y=170)
    hook_size, hook_lh = 60, 74
    hy = _draw_paragraph(c, MX, 170, analysis_headline(a), hook_size, c.W - 2 * MX,
                         color=T.TEXT, weight="bold", line_h=hook_lh, max_lines=3)

    # Gesamthöhe der Kette: Karte + Name + Verdict + Ratings
    r_gap = 16
    r_cw = (c.W - 2 * MX - r_gap) // 2
    r_ch = 90
    ratings_h = 2 * r_ch + r_gap
    verdict_h = 106
    sub_h = 44        # Name/Sektor direkt unter der Karte
    logo_name_gap = 70  # visueller Abstand zwischen Name und Verdict-Badge
    card_h = 230
    chain_h = card_h + 16 + sub_h + logo_name_gap + verdict_h + 14 + ratings_h + 10

    # Logo-Karte: zentriert zwischen Hook-Ende und Footer
    available = footer_line - hy
    card_top = hy + max(16, (available - chain_h) // 2)

    _logo_card(c, MX, card_top, c.W - 2 * MX, card_h, a["ticker"])

    # Name + Sektor direkt unter der Logo-Karte
    sub = A.short_name(a["name"])
    if a.get("sector"):
        sub += f"  ·  {a['sector']}"
    sub_y = card_top + card_h + 16
    c.text(MX, sub_y, sub, TY_BODY, color=T.TEXT)

    # Verdict-Badge — mit Abstand zum Namen
    verdict_top = sub_y + sub_h + logo_name_gap
    _verdict_badge(c, MX, verdict_top, a["verdict"], a["score"], h=verdict_h,
                   w=c.W - 2 * MX)
    verdict_bottom = verdict_top + verdict_h

    # Rating-Blöcke 2×2 — direkt unter Verdict, zentriert bis Footer
    r_top = verdict_bottom + 14

    rt = a["ratings"]
    rating_items = [
        ("Qualität",    rt.get("Qualität")),
        ("Wachstum",    rt.get("Wachstum")),
        ("Bewertung",   rt.get("Bewertung")),
        ("Katalysator", rt.get("Katalysator")),
    ]
    vcol = verdict_color(a["verdict"])
    for i, (label, val) in enumerate(rating_items):
        row, col_i = divmod(i, 2)
        rx = MX + col_i * (r_cw + r_gap)
        ry = r_top + row * (r_ch + r_gap)
        c.tile(rx, ry, r_cw, r_ch, color=T.PANEL)
        c.text(rx + 18, ry + 10, label.upper(), 24, color=T.TEXT, weight="bold")
        c.text(rx + r_cw - 18, ry + 8,
               f"{val if val is not None else '–'}/5", 32,
               color=vcol, weight="bold", ha="right", font="mono")
        _stars(c, rx + 28, ry + r_ch - 32, val, col=vcol, gap=30, s=180)
    analysis_footer(c)


# 2) GESAMTEINSCHÄTZUNG — vollständiger Investment-Case (Rating-Blöcke auf Cover)
def slide_analysis_verdict(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Gesamteinschätzung", 42, weight="bold")
    col = verdict_color(a["verdict"])
    lab = VERDICT_LABEL.get((a["verdict"] or "").upper(), "")
    c.text(MX, 248, f"{a['verdict']} · {lab}   ·   {a['score']} von 100 Punkten"
           if a["score"] is not None else f"{a['verdict']} · {lab}",
           TY_SUB, color=col, weight="bold")

    # Vollständiger Investment-Case — kein Abschneiden (Rating-Blöcke sind auf Cover)
    core = " ".join(a["sections"].get(1, "").split()) or a.get("hook", "")
    _draw_paragraph(c, MX, 312, core, TY_BODY, c.W - 2 * MX,
                    color=T.TEXT, line_h=TY_BODY_LH, max_lines=20)
    analysis_footer(c)


def _scenario_rows(c, a, top, horizon_key, title, subtitle):
    """Gemeinsamer Block: Bull/Base/Bear als Wahrscheinlichkeits-Balken +
    Kursziel-Spanne. horizon_key: 'scenarios' (12–18M) oder 'longterm' (3–5J)."""
    c.text(MX, top, title, 42, weight="bold")
    c.text(MX, top + 56, subtitle, TY_SUB, color=T.MUTED)
    data = a[horizon_key]
    rows_top = top + 110
    rh, gap = 180, 22
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
            # Wahrscheinlichkeit + Kursziel rechts (vertikal gestapelt, aber kompakt)
            prob_str = f"{prob}%" if prob is not None else "–"
            c.text(c.W - MX - 40, y + 36, "Wahrscheinlichkeit:", TY_SUB,
                   color=T.MUTED, ha="right")
            c.text(c.W - MX - 40, y + 58, prob_str, 38,
                   color=col, weight="bold", ha="right", font="mono")
            c.text(c.W - MX - 40, y + 114, "Kursziel:", TY_SUB,
                   color=T.MUTED, ha="right")
            c.text(c.W - MX - 40, y + 136, rng or "k. A.", TY_BODY,
                   color=T.TEXT, ha="right", weight="bold")
        else:
            rng = A.fmt_range(data[key])
            c.text(MX + 40, y + 78, "Kursziel-Spanne", TY_SUB, color=T.MUTED)
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


# ── Business-Bullet-Vereinfachung (Fachjargon → klares Deutsch) ──────────────
_JARGON_MAP = [
    # Muster  →  Ersatz
    ("TSMC-Leading-Edge-Allokation und CoWoS-Packaging-Kapazität",
     "TSMC-Fertigungskapazität für die neusten Chips"),
    ("Datacenter-GPU-Mix-Verschiebung hebt Gruppen-Marge strukturell",
     "Mehr GPU-Umsatz verbessert die Gesamtmarge dauerhaft"),
    ("Operativer Hebel:", ""),
    ("Fabless-Modell:", ""),
    ("Semi-Custom", "Konsolen-Chips"),
    ("Leading-Edge-Allokation", "Fertigungskapazität"),
    ("CoWoS-Packaging-Kapazität", "Chip-Packaging-Kapazität"),
    ("niedrigmargigere", "margenschwächere"),
    ("Cash-Sockel", "stabile Cashflow-Basis"),
]


def _simplify_bullet(text: str) -> str:
    for pattern, replacement in _JARGON_MAP:
        text = text.replace(pattern, replacement)
    # Doppelleerzeichen nach Ersetzung bereinigen
    import re as _re
    text = _re.sub(r"  +", " ", text).strip()
    text = _re.sub(r"^[:\s]+", "", text).strip()
    return text


# 5) WAS MACHT DAS UNTERNEHMEN — Highlights aus Investment-Case + Geschäftsmodell
def slide_analysis_business(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Was macht das Unternehmen?", 42, weight="bold")
    c.text(MX, 240, "Geschäftsmodell & Investment-Case in Kürze", TY_SUB, color=T.MUTED)
    bullets = [_simplify_bullet(b) for b in a.get("business_bullets", [])[:8]]
    inner_w = c.W - 2 * MX - 80
    pad_top, pad_bot, b_gap = 22, 20, 16
    footer_y = c.H - 160

    # Berechne dynamische Höhe pro Box anhand der tatsächlich umgebrochenen Zeilen
    def _bullet_split(b):
        head, _, rest = b.partition(" — ")
        if not rest:
            words = b.split()
            split = min(5, max(2, len(words) - 2))
            head, rest = " ".join(words[:split]), " ".join(words[split:])
        return head.strip(), rest.strip()

    y = 304
    for b in bullets:
        head, rest = _bullet_split(b)
        n_head = len(_wrap_px(head, inner_w, TY_BODY))
        n_body = len(_wrap_px(rest, inner_w, TY_BODY)) if rest else 0
        rh = pad_top + n_head * TY_BODY_LH + n_body * TY_BODY_LH + pad_bot
        if y + rh > footer_y:
            break                          # Box würde Footer überschreiten
        c.tile(MX, y, c.W - 2 * MX, rh, color=T.PANEL)
        c.tile(MX, y, 10, rh, color=T.BLUE, radius=5)
        head_bottom = _draw_paragraph(c, MX + 40, y + pad_top, head, TY_BODY,
                                      inner_w, color=T.BLUE, weight="bold",
                                      line_h=TY_BODY_LH)
        if rest:
            _draw_paragraph(c, MX + 40, head_bottom, rest, TY_BODY,
                            inner_w, color=T.TEXT, line_h=TY_BODY_LH)
        y += rh + b_gap
    analysis_footer(c)


# 5b) CHANCEN & RISIKEN — für Posts ohne Szenario-Wahrscheinlichkeiten (Alt-Schema)
def slide_analysis_chances(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Chancen & Risiken", 42, weight="bold")
    c.text(MX, 240, "Das Wichtigste aus Bull- und Bear-Sicht", TY_SUB, color=T.MUTED)

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
    body_size, body_lh = TY_BODY, TY_BODY_LH
    head_h, pad_bot = 72, 24         # Platz für Label+Meta (eine Zeile), Abstand unten
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
    body_size, body_lh, head_h = TY_BODY, TY_BODY_LH, 72
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
        c.text(MX + 40, y + 20, SCEN_LABEL[key] + " Case", 26, color=col, weight="bold")
        # Wahrscheinlichkeit · Kursziel in EINER Zeile rechts — etwas tiefer als Label
        meta_parts = []
        if prob is not None:
            meta_parts.append(f"{prob}%")
        if rng:
            meta_parts.append(rng)
        if meta_parts:
            c.text(c.W - MX - 40, y + 36, "  ·  ".join(meta_parts), TY_BODY,
                   color=col, weight="bold", ha="right", font="mono")
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
    c.text(MX, 240, "Was hinter Bull, Base und Bear steckt", TY_SUB, color=T.MUTED)
    _draw_cases_blocks(c, a, items)
    analysis_footer(c)


def _fazit_clean_text(a):
    """Bereinigt Abschnitt 11 für Slide-Darstellung (ohne Ratings, Disclaimer etc.)."""
    import re as _re
    raw11 = a["sections"].get(11, "")
    raw11 = _re.sub(r"\n-\s*(Qualität|Wachstum|Bewertung|Katalysator)[^\n]*", "", raw11)
    raw11 = _re.sub(r"\*\*([^*]+)\*\*", r"\1", raw11)
    raw11 = _re.sub(r"\s*-{3,}\s*\|.*", "", raw11, flags=_re.DOTALL)
    raw11 = _re.sub(r"\|[^\n]*", "", raw11)
    raw11 = _re.sub(r"\*?Keine Anlageberatung[^*\n]*\*?", "", raw11)
    raw11 = _re.sub(r"Verdict:\s*\w+\s*\(\d+/\d+\)[^\n]*", "", raw11)
    return A.clean_for_slide(raw11.strip()) or a.get("fazit_core", "")


def _fazit_max_lines(canvas_h, has_peers):
    """Maximale Zeilenanzahl für Fazit-Fließtext (ohne Overflow-Folie)."""
    peers_reserve = 100 if has_peers else 0
    avail = (canvas_h - 160) - 256 - 120 - 40 - peers_reserve
    return max(4, int(avail / TY_BODY_LH))


def _rejoin_wrapped_lines(lines):
    """Rekonstruiert Fließtext aus _wrap_px-Zeilen (entfernt Trenn-Bindestriche)."""
    result = ""
    for line in lines:
        if result.endswith("-"):
            result = result[:-1] + line   # getrenntes Wort zusammenführen
        else:
            result = (result + " " + line).strip()
    return result


def fazit_split(a, canvas_h=1350):
    """Gibt (page1_text, page2_text_or_None) zurück — für Overflow-Erkennung in generate.py."""
    core = _fazit_clean_text(a)
    max_l = _fazit_max_lines(canvas_h, bool(a.get("peers")))
    all_lines = _wrap_px(core, 1080 - 2 * MX, TY_BODY)
    if len(all_lines) <= max_l:
        return core, None
    return _rejoin_wrapped_lines(all_lines[:max_l]), _rejoin_wrapped_lines(all_lines[max_l:])


# 7) PROFI-FAZIT — Kernaussage + Peers + Folgen-CTA
def slide_analysis_fazit(c, a, date_iso, text_override=None, show_peers_cta=True):
    analysis_header(c, a, date_iso)
    col = verdict_color(a["verdict"])
    c.text(MX, 184, "Profi-Fazit", 42, weight="bold")

    core = text_override if text_override is not None else _fazit_clean_text(a)
    peers_reserve = 100 if (show_peers_cta and a.get("peers")) else 0
    _avail_text = (c.H - 160) - 256 - 120 - 40 - peers_reserve
    max_lines_fazit = _fazit_max_lines(c.H, show_peers_cta and bool(a.get("peers")))
    # Bei text_override (Fortsetzungsfolie) keinen Truncate-Marker setzen
    use_max = None if text_override is not None else max_lines_fazit
    y = _draw_paragraph(c, MX, 256, core, TY_BODY, c.W - 2 * MX,
                        color=T.TEXT, line_h=TY_BODY_LH, max_lines=use_max)

    # Peers nur auf der letzten Fazit-Folie
    if show_peers_cta:
        peers = a.get("peers", [])
        if peers:
            c.text(MX, y + 30, "VERGLEICHBARE TITEL", TY_SUB, color=T.MUTED, weight="bold")
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

        # Folgen-CTA
        cta_top = max(y + 40, c.H - 360)
        c.tile(MX, cta_top, c.W - 2 * MX, 120, color=T.PANEL)
        c.tile(MX, cta_top, 12, 120, color=T.BLUE, radius=6)
        c.text(MX + 40, cta_top + 28, "Folge für wöchentliche Profi-Analysen", 28,
               color=T.TEXT, weight="bold")
        c.text(MX + 40, cta_top + 74, "datengetrieben · unabhängig · systematisiert",
               TY_SUB, color=T.MUTED)
    analysis_footer(c)


# 6b) BEWERTUNG — „KGV-Illusion" (Abschnitt 7), ohne aktuellen Kurs
def slide_analysis_valuation(c, a, date_iso):
    import re as _re
    analysis_header(c, a, date_iso)
    sec7_raw = a["sections"].get(7, "")
    pe = A.pe_multiples(sec7_raw)
    illusion = (pe["trailing"] and pe["forward"]
                and _num(pe["trailing"]) > _num(pe["forward"]) * 1.8)
    title = "Bewertung: die KGV-Illusion" if illusion else "Bewertung"
    c.text(MX, 184, title, 42, weight="bold")
    c.text(MX, 240, "Warum das optische KGV in die Irre führt"
           if illusion else "Bewertung im Zykluskontext", TY_SUB, color=T.MUTED)

    y = 300
    # Bewertungs-Chips immer linksbündig auffüllen — fehlt das Trailing-KGV,
    # rückt das Forward-KGV in die linke Spalte (nicht in die Mitte).
    chip_defs = []
    if pe["trailing"]:
        chip_defs.append(("TRAILING-KGV", pe["trailing"] + "x", T.RED,
                          "optisch teuer · Basiseffekt"))
    if pe["forward"]:
        chip_defs.append(("FORWARD-KGV", pe["forward"] + "x", T.GREEN,
                          "die relevante Kennzahl"))
    if pe.get("pb"):
        chip_defs.append(("KURS-BUCHWERT", pe["pb"] + "x", T.BLUE,
                          "Substanzbewertung"))
    chip_defs = chip_defs[:2]
    if chip_defs:
        gap = 26
        cw = (c.W - 2 * MX - gap) // 2
        ch = 150
        for i, (lab, val, ccol, note) in enumerate(chip_defs):
            cx = MX + i * (cw + gap)
            c.tile(cx, y, cw, ch, color=T.PANEL)
            c.tile(cx, y, 10, ch, color=ccol, radius=5)
            c.text(cx + 34, y + 26, lab, 26, color=ccol, weight="bold")
            c.text(cx + 34, y + 56, val, 50, color=ccol, weight="bold", font="mono")
            c.text(cx + 34, y + 118, note, TY_SUB, color=T.MUTED)
        y += ch + 26

    # Analyst-Konsensus-Tile (wenn vorhanden)
    m_ac = _re.search(
        r'Analyst-?Konsens(?:us|ziel)\s*\$\s*([0-9]+(?:[,.][0-9]+)?)', sec7_raw)
    if m_ac:
        ac_h = 120
        c.tile(MX, y, c.W - 2 * MX, ac_h, color=T.PANEL)
        c.tile(MX, y, 10, ac_h, color=T.AMBER, radius=5)
        c.text(MX + 34, y + 22, "ANALYSTEN-KONSENSUS", 24, color=T.AMBER, weight="bold")
        c.text(MX + 34, y + 60, "Ø Kursziel: " + m_ac.group(1) + " $", 38,
               color=T.AMBER, weight="bold", font="mono")
        c.text(c.W - MX - 34, y + 60, "Coverage hinkt der Rally hinterher",
               TY_SUB, color=T.MUTED, ha="right")
        y += ac_h + 26

    txt = A.clean_for_slide(sec7_raw)
    _draw_paragraph(c, MX, y, txt, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=11)
    analysis_footer(c)


# 7b) RISIKO & REALITÄTSCHECK — Positionierung/Psychologie (Abschnitt 8), ohne GWS
def slide_analysis_risk(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Risiko & Realitätscheck", 42, weight="bold")
    c.text(MX, 240, "Positionierung, Erwartungen, Volatilität", TY_SUB, color=T.MUTED)

    # Positionsgrößen-Hinweis als Warnchip (falls im Fazit genannt)
    y = 300
    psz = A.position_size(a.get("fazit", ""))
    if psz:
        box_h = 24 + TY_BODY + 24
        c.tile(MX, y, c.W - 2 * MX, box_h, color=T.PANEL)
        c.tile(MX, y, 10, box_h, color=T.AMBER, radius=5)
        c.text(MX + 34, y + 24, "POSITIONSGRÖSSE BEGRENZEN", TY_BODY,
               color=T.AMBER, weight="bold")
        c.text(c.W - MX - 34, y + 24, psz, TY_BODY, color=T.AMBER, weight="bold",
               ha="right", font="mono")
        y += box_h + 36

    # HBM-Lieferkettenrisiko (aus Geschäftsmodell-Section, falls vorhanden)
    if "HBM" in a["sections"].get(2, ""):
        hbm_h = 24 + TY_BODY + 24
        c.tile(MX, y, c.W - 2 * MX, hbm_h, color=T.PANEL)
        c.tile(MX, y, 10, hbm_h, color=T.AMBER, radius=5)
        c.text(MX + 34, y + 24, "HBM-LIEFERKETTENRISIKO", TY_BODY,
               color=T.AMBER, weight="bold")
        c.text(c.W - MX - 34, y + 24, "SK Hynix / Samsung", TY_BODY,
               color=T.MUTED, weight="bold", ha="right", font="mono")
        y += hbm_h + 20

    body = A.clean_for_slide(a["sections"].get(8, "")) or \
        A.clean_for_slide(a["scenarios"]["bear"]["summary"])
    _draw_paragraph(c, MX, y, body, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=14)
    analysis_footer(c)


# 9b) SPEICHERN & MITREDEN — Engagement-CTA (Save + Community-Frage)
def slide_analysis_cta(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Speichern & mitreden", TY_H1, weight="bold")

    # Save-Box
    c.tile(MX, 272, c.W - 2 * MX, 150, color=T.PANEL)
    c.tile(MX, 272, 12, 150, color=T.BLUE, radius=6)
    _draw_bookmark(c, MX + 46, 308, 44, 78, T.BLUE)
    c.text(MX + 130, 298, "Speichere diesen Beitrag", TY_BODY, weight="bold")
    c.text(MX + 130, 298 + TY_BODY_LH,
           "für deine Watchlist — die ganze Analyse auf einen Blick.",
           TY_SUB, color=T.MUTED)

    # Community-Frage — dynamische Box-Höhe an Text angepasst
    name = A.short_name(a["name"])
    q_text = (f"{name}: berechtigter Hype oder überhitzt? "
              f"Schreib deine These in die Kommentare.")
    q_lines = _wrap_px(q_text, c.W - 2 * MX - 80, TY_BODY)
    q_box_h = 16 + TY_BODY_LH + len(q_lines) * TY_BODY_LH + 24  # label + lines + padding
    save_box_bottom = 272 + 150                                    # Ende der Save-Box
    cta_y = c.H - 330                                             # Anfang CTA-Text
    q_top = save_box_bottom + (cta_y - save_box_bottom - q_box_h) // 2  # zentriert
    c.tile(MX, q_top, c.W - 2 * MX, q_box_h, color=T.PANEL_HI)
    c.text(MX + 40, q_top + 16, "DEINE MEINUNG?", TY_SUB, color=T.BLUE, weight="bold")
    _draw_paragraph(c, MX + 40, q_top + 16 + TY_BODY_LH,
                    q_text, TY_BODY, c.W - 2 * MX - 80,
                    color=T.TEXT, weight="bold", line_h=TY_BODY_LH)

    # Folgen-CTA (unten, zentriert)
    cta_y = c.H - 330
    c.text(c.W // 2, cta_y, "Folge für wöchentliche Profi-Analysen",
           TY_BODY, color=T.TEXT, weight="bold", ha="center")
    c.text(c.W // 2, cta_y + TY_BODY_LH, "datengetrieben · unabhängig · systematisiert",
           TY_SUB, color=T.MUTED, ha="center")
    analysis_footer(c)


# 6b) FUNDAMENTALE QUALITÄT — Abschnitt 6 (Bilanz, Margen, Kapitalrendite)
def slide_analysis_fundamentals(c, a, date_iso):
    import re as _re
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Fundamentale Qualität", 42, weight="bold")
    c.text(MX, 240, "Bilanz, Margen, Kapitalrendite", TY_SUB, color=T.MUTED)

    sec6_raw = a["sections"].get(6, "")
    m_de  = _re.search(r'D/E[^0-9]*([0-9]+(?:[,.][0-9]+)?)', sec6_raw)
    m_fcf = _re.search(r'FCF\s*\$\s*([0-9]+[,.][0-9]+)\s*(Mrd|Mio)', sec6_raw)

    y = 304
    if m_de or m_fcf:
        gap, cw, ch = 26, (c.W - 2 * MX - 26) // 2, 140
        if m_de:
            c.tile(MX, y, cw, ch, color=T.PANEL)
            c.tile(MX, y, 10, ch, color=T.GREEN, radius=5)
            c.text(MX + 34, y + 22, "D/E-VERHÄLTNIS", 24, color=T.GREEN, weight="bold")
            c.text(MX + 34, y + 56, m_de.group(1), 50, color=T.GREEN,
                   weight="bold", font="mono")
            c.text(MX + 34, y + 116, "konservative Verschuldung", TY_SUB, color=T.MUTED)
        if m_fcf:
            x2 = MX + cw + gap
            c.tile(x2, y, cw, ch, color=T.PANEL)
            c.tile(x2, y, 10, ch, color=T.BLUE, radius=5)
            c.text(x2 + 34, y + 22, "FREE CASHFLOW", 24, color=T.BLUE, weight="bold")
            c.text(x2 + 34, y + 56,
                   m_fcf.group(1) + " " + m_fcf.group(2) + ". $",
                   42, color=T.BLUE, weight="bold", font="mono")
            c.text(x2 + 34, y + 116, "starke Mittelgenerierung", TY_SUB, color=T.MUTED)
        y += ch + 32

    txt = A.clean_for_slide(sec6_raw)
    _draw_paragraph(c, MX, y, txt, TY_BODY, c.W - 2 * MX, color=T.TEXT,
                    line_h=TY_BODY_LH, max_lines=14)
    analysis_footer(c)


# 9b) TECHNISCHES BILD & MOMENTUM — Abschnitt 9 (Kurs & GWS herausgefiltert)
def slide_analysis_technical(c, a, date_iso):
    analysis_header(c, a, date_iso)
    c.text(MX, 184, "Technisches Bild & Momentum", 42, weight="bold")
    c.text(MX, 240, "Trend, Volatilität, Warnsignale", TY_SUB, color=T.MUTED)
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
    c.text(MX + 50, box_top + 372, BRAND_NAME, 40, color=T.BLUE, weight="bold")
    # nach oben zeigende Dreiecke (zum Profil/Feed)
    for i in range(3):
        c.ax.scatter(c.W - MX - 60 - i * 36, c.y(box_top + 360), s=170,
                     marker="^", color=T.BLUE, edgecolor="none", zorder=12)
    c.text(MX, 1230, f"Folge {BRAND_NAME} für 1–2 Analysen pro Woche", 24,
           color=T.MUTED)
    analysis_footer(c)


# ══════════════════════════════════════════════════════════════════════════════
# EARNINGS-ANALYSE-SLIDES (Dritter Post-Typ)
# Datenquelle: instagram/earnings.load_earnings(ticker) -> e
#   e enthält die Earnings-Zahlen (aus dem Web), den Kurssprung (aus RS-JSON)
#   und die geparste Basis-Analyse unter e["analysis"].
# Designsystem identisch zu den Analyse-Slides (analysis_header/-footer, Farben).
# Akzentfarbe = Grün (Beat) bzw. Rot (Miss) — signalisiert sofort „Earnings".
# ══════════════════════════════════════════════════════════════════════════════
from . import earnings as E


def earn_color(e):
    return T.GREEN if (e.get("eps_surprise_pct") or 0) >= 0 else T.RED


def _e_name(e):
    a = e.get("analysis")
    return A.short_name(a["name"]) if a and a.get("name") else e["ticker"]


def _e_sector(e):
    a = e.get("analysis")
    return a.get("sector", "") if a else ""


def earnings_headline(e):
    """Hook für Slide 1 — kurze, zugespitzte Beat-These. Regel: KEIN Firmenname und
    KEIN Tickerkürzel im Hook (z. B. weder „Centene" noch „(CNC)") — um welchen Wert
    es geht, zeigen die Logo-Karte und die Zeile darunter. e['headline'] (via
    --headline) hat Vorrang und wird unverändert übernommen."""
    if e.get("headline"):
        return e["headline"]
    surp = e.get("eps_surprise_pct")
    if (surp or 0) >= 0:
        s = E.fmt_pct_pts(surp, 0, signed=False) if surp is not None else ""
        return (f"Turnaround bestätigt — der Quartalsgewinn schlägt die Erwartung "
                f"um {s}") if s else "Die Quartalszahlen schlagen die Erwartungen"
    return "Quartalszahlen verfehlen die Erwartungen"


def _eyebrow_pill(c, x, top, text, col=T.GREEN, h=52):
    """Kleine Akzent-Pille (z. B. 'EARNINGS · Q1 2026 · BEAT')."""
    w = 56 + int(len(text) * 13.5)
    c.tile(x, top, w, h, color=T.PANEL_HI, radius=h // 2)
    c.tile(x + 18, top + h // 2 - 7, 14, 14, color=col, radius=7)
    c.text(x + 46, top + h // 2 - 13, text, 22, color=col, weight="bold")
    return w


def _stat_tile(c, x, top, w, h, label, value, sub, col, value_size=48):
    """Kennzahl-Kachel: Label oben, große Zahl, Untertitel. h ≥ 168 empfohlen."""
    c.tile(x, top, w, h, color=T.PANEL)
    c.tile(x, top, 10, h, color=col, radius=5)
    c.text(x + 34, top + 20, label, 22, color=col, weight="bold")
    c.text(x + 34, top + 54, value, value_size, color=T.TEXT, weight="bold",
           font="mono")
    if sub:
        for i, ln in enumerate(_wrap_px(sub, w - 60, 20)[:2]):
            c.text(x + 34, top + 120 + i * 26, ln, 20, color=T.MUTED)


# 1) COVER — Earnings-Hook, Logo, Beat-Badge, die zwei Hero-Zahlen
def slide_earnings_cover(c, e, date_iso):
    MX = COVER_MX
    col = earn_color(e)
    footer_line = c.H - 150

    lw = c.draw_logo(MX, 64, 46)
    if not lw:
        c.text(MX, 68, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 74, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")

    beat_word = "BEAT" if (e.get("eps_surprise_pct") or 0) >= 0 else "MISS"
    _eyebrow_pill(c, MX, 150, f"EARNINGS · {e['quarter']} · {beat_word}", col=col)

    hy = _draw_paragraph(c, MX, 232, earnings_headline(e), 56, c.W - 2 * MX,
                         color=T.TEXT, weight="bold", line_h=70, max_lines=4)

    # Kette: Logo-Karte + Name + zwei Hero-Kacheln, zwischen Hook & Footer zentriert
    card_h, sub_h, stat_h = 210, 44, 172
    gap_card_sub, gap_sub_stat = 16, 40
    chain_h = card_h + gap_card_sub + sub_h + gap_sub_stat + stat_h
    card_top = hy + max(20, (footer_line - hy - chain_h) // 2)

    _logo_card(c, MX, card_top, c.W - 2 * MX, card_h, e["ticker"])

    sub = _e_name(e) + (f"  ·  {_e_sector(e)}" if _e_sector(e) else "")
    sub_y = card_top + card_h + gap_card_sub
    c.text(MX, sub_y, sub, TY_BODY, color=T.TEXT)

    # Zwei Hero-Kacheln: EPS-Surprise + Kurssprung
    stat_top = sub_y + sub_h + gap_sub_stat
    gap = 24
    tw = (c.W - 2 * MX - gap) // 2
    surp = e.get("eps_surprise_pct")
    cur = e.get("currency", "")
    eps_sub = (f"Ist {cur}{E.fmt_num(e.get('eps_actual'))} · "
               f"Erw. {cur}{E.fmt_num(e.get('eps_estimate'))}")
    _stat_tile(c, MX, stat_top, tw, stat_h, "EPS-SURPRISE",
               E.fmt_pct_pts(surp, 0), eps_sub, col)
    jump = e.get("jump_pct")
    _stat_tile(c, MX + tw + gap, stat_top, tw, stat_h, "KURSSPRUNG",
               E.fmt_pct(jump, 1), f"am Tag der Zahlen ({short_date(e['report_date'])})",
               col if (jump or 0) >= 0 else T.RED)
    analysis_footer(c)


# 2) DER BEAT IN ZAHLEN — EPS & Umsatz Ist vs. Erwartung
def slide_earnings_numbers(c, e, date_iso):
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    # auf hohem (Reel-)Canvas den Inhalt vertikal zentrieren, auf 4:5 unverändert
    dy = max(0, (c.H - 1350) // 2)
    c.text(MX, 184 + dy, "Der Beat in Zahlen", 42, weight="bold")
    c.text(MX, 240 + dy, f"{e['quarter']} · Ist gegen Analysten-Erwartung", TY_SUB,
           color=T.MUTED)
    cur = e.get("currency", "")

    def compare_tile(top, label, actual, estimate, unit, surprise, surp_dec=0):
        h = 250
        c.tile(MX, top, c.W - 2 * MX, h, color=T.PANEL)
        c.tile(MX, top, 12, h, color=col, radius=6)
        c.text(MX + 40, top + 26, label, 26, color=col, weight="bold")
        # Surprise-Chip rechts
        chip = E.fmt_pct_pts(surprise, surp_dec) if surprise is not None else ""
        if chip:
            cw = 60 + int(len(chip) * 22)
            c.tile(c.W - MX - cw - 24, top + 22, cw, 60, color=T.PANEL_HI, radius=30)
            c.text(c.W - MX - cw / 2 - 24, top + 32, chip, 34, color=col,
                   weight="bold", ha="center", font="mono")
        # Ist (groß, grün) vs. Erwartet (gedämpft)
        col_w = (c.W - 2 * MX - 80) // 2
        iy = top + 110
        c.text(MX + 40, iy, "IST", 22, color=T.MUTED, weight="bold")
        c.text(MX + 40, iy + 34, f"{cur}{E.fmt_num(actual)}", 64,
               color=T.TEXT, weight="bold", font="mono")
        c.text(MX + 40, iy + 116, unit, TY_SUB, color=T.MUTED)
        ex = MX + 40 + col_w
        c.text(ex, iy, "ERWARTET", 22, color=T.MUTED, weight="bold")
        c.text(ex, iy + 34, f"{cur}{E.fmt_num(estimate)}", 64,
               color=T.MUTED, weight="bold", font="mono")
        c.text(ex, iy + 116, unit, TY_SUB, color=T.MUTED)
        return top + h

    y = compare_tile(300 + dy, "GEWINN JE AKTIE (ADJ.)", e.get("eps_actual"),
                     e.get("eps_estimate"), "je Aktie", e.get("eps_surprise_pct"))
    y = compare_tile(y + 28, "UMSATZ", e.get("revenue_actual"),
                     e.get("revenue_estimate"), e.get("revenue_unit", ""),
                     e.get("revenue_surprise_pct"), surp_dec=1)

    # Kurze Zusammenfassung als Text (statt technischer Chips)
    summary = e.get("beat_summary") or _auto_beat_summary(e)
    if summary:
        c.tile(MX, y + 30, c.W - 2 * MX, 4, color=T.GRID, radius=2)  # feine Trennlinie
        _draw_paragraph(c, MX, y + 56, summary, TY_BODY, c.W - 2 * MX,
                        color=T.SUBTLE, line_h=TY_BODY_LH, max_lines=4)
    analysis_footer(c)


def _auto_beat_summary(e):
    """Fallback-Zusammenfassung für Slide 2, falls keine 'beat_summary' gesetzt ist."""
    cur = e.get("currency", "")
    parts = []
    if e.get("eps_actual") is not None and e.get("eps_surprise_pct") is not None:
        parts.append(f"Bereinigt verdiente das Unternehmen {cur}{E.fmt_num(e['eps_actual'])} "
                     f"je Aktie — rund {E.fmt_pct_pts(e['eps_surprise_pct'], 0)} mehr als erwartet.")
    if e.get("revenue_actual") is not None:
        parts.append("Auch der Umsatz lag über den Schätzungen — ein Beat auf ganzer Linie.")
    return " ".join(parts)


# 3) KURSREAKTION — Candle-Chart um den Meldetag, Sprungtag markiert
def slide_earnings_reaction(c, e, date_iso):
    from matplotlib.patches import Rectangle
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    # auf hohem (Reel-)Canvas den Inhalt vertikal zentrieren, auf 4:5 unverändert
    dy = max(0, (c.H - 1350) // 2)
    c.text(MX, 184 + dy, "Die Kursreaktion", 42, weight="bold")
    c.text(MX, 240 + dy, "Tageskerzen — die letzten 50 Handelstage bis zum Meldetag",
           TY_SUB, color=T.MUTED)

    candles = e.get("reaction_ohlcv") or []
    idx = e.get("reaction_idx")
    chart_top, chart_h = 310 + dy, int(1350 * 0.42)
    if candles:
        ax = c.chart_axes(MX, chart_top, c.W - 2 * MX, chart_h)
        n = len(candles)
        for i, cd in enumerate(candles):
            o, h, l, cl = cd["o"], cd["h"], cd["l"], cd["c"]
            up = cl >= o
            ccol = T.GREEN if up else T.RED
            is_evt = (i == idx)
            lw = 2.4 if is_evt else 1.0
            ax.plot([i, i], [l, h], color=ccol, lw=lw, zorder=3 if is_evt else 1)
            body_h = max(abs(cl - o), (h - l) * 0.02)
            ax.add_patch(Rectangle((i - 0.34, min(o, cl)), 0.68, body_h,
                                   facecolor=ccol, edgecolor=ccol,
                                   lw=lw, zorder=3 if is_evt else 2))
            if is_evt:
                # Highlight-Säule hinter dem Meldetag
                ax.axvspan(i - 0.5, i + 0.5, color=col, alpha=0.10, zorder=0)

        all_h = [cd["h"] for cd in candles]
        all_l = [cd["l"] for cd in candles]
        pad = (max(all_h) - min(all_l)) * 0.10
        ax.set_xlim(-1, n)
        # mehr Luft unten für die Datums-Achse
        ax.set_ylim(min(all_l) - pad * 2.4, max(all_h) + pad)

        # Prev-Close-Referenzlinie + Sprung-Annotation
        if idx is not None and e.get("jump_prev_close"):
            ax.axhline(e["jump_prev_close"], color=T.MUTED, lw=1.2,
                       ls=(0, (5, 5)), zorder=2)
            jlabel = E.fmt_pct(e.get("jump_pct"), 1)
            # Annotation nach oben-links, damit sie nicht über die Folgekerzen läuft
            ax.annotate(jlabel, (idx - 0.4, candles[idx]["h"]),
                        xytext=(-4, 18), textcoords="offset points",
                        color=col, fontsize=16, fontweight="bold",
                        ha="right", fontfamily=_FONTS["mono"])

        # ── Datums-Achse unten: macht die Tagesspanne sichtbar ────────────────
        ylabel_y = min(all_l) - pad * 1.5
        step = max(1, (n - 1) // 5)
        xticks = list(range(0, n, step))
        # letzte (Meldetag-)Kerze immer beschriften; reguläre Ticks, die zu nah
        # daran liegen, entfernen, damit sich die Labels nicht überlappen
        xticks = [t for t in xticks if (n - 1) - t >= step * 0.7]
        xticks.append(n - 1)
        for xi in xticks:
            is_evt = (idx is not None and xi == idx)
            ax.text(xi, ylabel_y, short_date(candles[xi]["d"]),
                    color=col if is_evt else T.MUTED,
                    fontsize=13 if is_evt else 12,
                    fontweight="bold" if is_evt else "normal",
                    va="top", ha="center", fontfamily=_FONTS["sans"])
        # kleine Tick-Striche an den Datumslabels
        for xi in xticks:
            ax.plot([xi, xi], [min(all_l) - pad * 1.15, min(all_l) - pad * 0.85],
                    color=T.GRID, lw=1.2, zorder=1)

        # Preis-Labels links (damit sie nicht mit der letzten Kerze kollidieren)
        for yv in (min(all_l), (min(all_l) + max(all_h)) / 2, max(all_h)):
            ax.text(-0.6, yv, f"{yv:.0f}", color=T.MUTED, fontsize=12,
                    va="center", ha="right", fontfamily=_FONTS["mono"])
    else:
        c.text(MX, chart_top + 40, "Keine Kursdaten verfügbar.", TY_BODY,
               color=T.MUTED)

    # Kacheln: Kurssprung + Schlusskurs am Meldetag
    ky = chart_top + chart_h + 70
    gap = 24
    tw = (c.W - 2 * MX - gap) // 2
    jump = e.get("jump_pct")
    _stat_tile(c, MX, ky, tw, 172, "KURSSPRUNG",
               E.fmt_pct(jump, 1),
               f"Vortag {E.fmt_num(e.get('jump_prev_close'))} → "
               f"{E.fmt_num(e.get('jump_close'))}",
               col if (jump or 0) >= 0 else T.RED)
    _stat_tile(c, MX + tw + gap, ky, tw, 172, "SCHLUSSKURS",
               f"{e.get('currency','')}{E.fmt_num(e.get('jump_close'))}",
               f"am {fmt_de_date(e['report_date'])}", T.BLUE)
    analysis_footer(c)


# 4) GUIDANCE & TURNAROUND-TREIBER
def slide_earnings_guidance(c, e, date_iso):
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    c.text(MX, 184, "Ausblick & Treiber", 42, weight="bold")
    c.text(MX, 240, "Was hinter dem Beat steckt", TY_SUB, color=T.MUTED)

    y = 300
    # Guidance-Kachel (volle Breite)
    if e.get("guidance"):
        glines = _wrap_px(e["guidance"], c.W - 2 * MX - 80, TY_BODY)
        gh = 70 + len(glines) * TY_BODY_LH + 20
        c.tile(MX, y, c.W - 2 * MX, gh, color=T.PANEL)
        c.tile(MX, y, 12, gh, color=col, radius=6)
        c.text(MX + 40, y + 22, "ANGEHOBENE PROGNOSE", 22, color=col, weight="bold")
        _draw_paragraph(c, MX + 40, y + 62, e["guidance"], TY_BODY,
                        c.W - 2 * MX - 80, color=T.TEXT, line_h=TY_BODY_LH)
        y += gh + 26

    # Turnaround-Kennzahl: blaue Überschrift OBEN (volle Breite), darunter die
    # große Zahl links + Erklärungstext rechts daneben (tiefer, damit die
    # Überschrift nicht in den Text ragt). Boxhöhe passt sich dem Text an.
    if e.get("key_metric_value"):
        note = e.get("key_metric_note", "")
        klines = _wrap_px(note, c.W - 2 * MX - 380, TY_SUB) if note else []
        kh = max(150, 76 + max(len(klines), 2) * 30 + 14)
        c.tile(MX, y, c.W - 2 * MX, kh, color=T.PANEL_HI)
        c.text(MX + 34, y + 22, e["key_metric_label"].upper(), 22,
               color=T.BLUE, weight="bold")
        c.text(MX + 34, y + 62, e["key_metric_value"], 56, color=T.TEXT,
               weight="bold", font="mono")
        for i, ln in enumerate(klines[:4]):
            c.text(MX + 360, y + 66 + i * 30, ln, TY_SUB, color=T.MUTED)
        y += kh + 26

    # Treiber-Bullets
    drivers = e.get("drivers") or []
    if drivers:
        c.text(MX, y + 6, "DIE TREIBER", 22, color=T.MUTED, weight="bold")
        y += 48
        for d in drivers[:4]:
            dl = _wrap_px(d, c.W - 2 * MX - 56, TY_BODY)
            c.ax.scatter(MX + 12, c.y(y + 16), s=120, marker="o",
                         color=col, edgecolor="none", zorder=11)
            for i, ln in enumerate(dl[:2]):
                c.text(MX + 50, y + i * TY_BODY_LH, ln, TY_BODY, color=T.TEXT)
            y += max(TY_BODY_LH, len(dl[:2]) * TY_BODY_LH) + 14
    analysis_footer(c)


def _verdict_note(e):
    """Erklärt das KI-Verdict im Earnings-Kontext (warum z. B. HALTEN trotz Beat
    und Kursziel über dem aktuellen Kurs). e['verdict_note'] hat Vorrang."""
    if e.get("verdict_note"):
        return e["verdict_note"]
    a = e.get("analysis")
    if not a:
        return ""
    v = (a.get("verdict") or "").upper()
    ps = A.position_size(a["sections"].get(11, "")) or ""
    if v == "BUY":
        return "Die Quartalszahlen stützen das positive KI-Verdict zusätzlich."
    if v in ("HOLD", "WATCH", "SELL"):
        tail = f" Empfohlene Positionsgröße daher {ps}." if ps else ""
        return ("Trotz starker Zahlen bleibt das KI-Verdict bewusst vorsichtig: "
                "Das Aufwärtspotenzial ist real, aber an erhöhte (u. a. regulatorische) "
                "Risiken gekoppelt — daher kein klares Kaufsignal, sondern eine "
                f"kleinere Position.{tail}")
    return ""


# 5) EINORDNUNG — Brücke vom Beat zur Investment-These (Verdict-Badge + Begründung)
def slide_earnings_context(c, e, date_iso):
    analysis_header(c, e, date_iso)
    a = e.get("analysis")
    c.text(MX, 184, "Einordnung", 42, weight="bold")
    c.text(MX, 240, "Was die Zahlen für die These bedeuten", TY_SUB, color=T.MUTED)

    y = 306
    if e.get("context"):
        y = _draw_paragraph(c, MX, y, e["context"], TY_BODY, c.W - 2 * MX,
                            color=T.TEXT, line_h=TY_BODY_LH, max_lines=8) + 36

    if a:
        _verdict_badge(c, MX, y, a["verdict"], a["score"], h=120)
        y += 120 + 22
        note = _verdict_note(e)
        if note:
            c.tile(MX, y, c.W - 2 * MX, 6, color=verdict_color(a["verdict"]), radius=3)
            c.text(MX, y + 24, "WARUM DIESES VERDICT?", TY_SUB,
                   color=verdict_color(a["verdict"]), weight="bold")
            _draw_paragraph(c, MX, y + 24 + TY_BODY_LH, note, TY_BODY,
                            c.W - 2 * MX, color=T.SUBTLE, line_h=TY_BODY_LH,
                            max_lines=7)
    analysis_footer(c)


# 6) GEWINN JE QUARTAL — bereinigtes EPS als Mini-Balkenchart (Turnaround-Trend)
def slide_earnings_quarterly(c, e, date_iso):
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    dy = max(0, (c.H - 1350) // 2)
    c.text(MX, 184 + dy, "Gewinn je Quartal", 42, weight="bold")
    c.text(MX, 240 + dy, e.get("quarterly_label", "Bereinigtes EPS je Quartal ($)"),
           TY_SUB, color=T.MUTED)

    q = e.get("quarterly") or []
    chart_top, chart_h = 320 + dy, 470
    if q:
        ax = c.chart_axes(MX, chart_top, c.W - 2 * MX, chart_h)
        vals = [d["eps"] for d in q]
        labels = [d["q"] for d in q]
        n = len(q)
        ymax = max(vals + [0])
        ymin = min(vals + [0])
        span = (ymax - ymin) or 1
        for i, v in enumerate(vals):
            is_last = (i == n - 1)
            bcol = T.GREEN if v >= 0 else T.RED
            ax.bar(i, v, width=0.62, color=bcol, zorder=3,
                   alpha=1.0 if is_last else 0.8)
            ax.text(i, v + (0.03 * span if v >= 0 else -0.03 * span),
                    f"{v:.2f}".replace(".", ","),
                    ha="center", va="bottom" if v >= 0 else "top",
                    color=bcol, fontsize=15, fontweight="bold",
                    fontfamily=_FONTS["mono"])
        ax.axhline(0, color=T.MUTED, lw=1.4, zorder=2)
        ax.set_xlim(-0.7, n - 0.3)
        ax.set_ylim(ymin - 0.32 * span, ymax + 0.18 * span)
        for i, lab in enumerate(labels):
            is_last = (i == n - 1)
            ax.text(i, ymin - 0.20 * span, lab, ha="center", va="top",
                    color=col if is_last else T.MUTED, fontsize=14,
                    fontweight="bold" if is_last else "normal",
                    fontfamily=_FONTS["sans"])
    note = e.get("quarterly_note")
    if note:
        _draw_paragraph(c, MX, chart_top + chart_h + 80, note, TY_BODY,
                        c.W - 2 * MX, color=T.SUBTLE, line_h=TY_BODY_LH, max_lines=3)
    analysis_footer(c)


# 7) WAS DEN BEAT GETRAGEN HAT — Segmente im Detail
def slide_earnings_segments(c, e, date_iso):
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    c.text(MX, 184, "Was den Beat getragen hat", 42, weight="bold")
    c.text(MX, 240, "Die Segmente im Detail", TY_SUB, color=T.MUTED)

    segs = e.get("segments") or []
    y = 312
    for s in segs[:4]:
        note = s.get("note", "")
        nlines = _wrap_px(note, c.W - 2 * MX - 340, TY_SUB) if note else []
        h = max(124, 56 + len(nlines) * 30 + 24)
        c.tile(MX, y, c.W - 2 * MX, h, color=T.PANEL)
        c.tile(MX, y, 10, h, color=col, radius=5)
        c.text(MX + 34, y + 22, s["name"].upper(), 24, color=col, weight="bold")
        if s.get("metric"):
            c.text(MX + 34, y + 56, s["metric"], 34, color=T.TEXT,
                   weight="bold", font="mono")
        for i, ln in enumerate(nlines[:4]):
            c.text(MX + 330, y + 28 + i * 30, ln, TY_SUB, color=T.MUTED)
        y += h + 20
    if e.get("segments_note"):
        _draw_paragraph(c, MX, y + 8, e["segments_note"], TY_SUB, c.W - 2 * MX,
                        color=T.MUTED, line_h=32, max_lines=3)
    analysis_footer(c)


# 10) QUALITÄT AUF EINEN BLICK — Sterne-Ratings aus der Basis-Analyse
def slide_earnings_ratings(c, e, date_iso):
    analysis_header(c, e, date_iso)
    a = e.get("analysis")
    c.text(MX, 184, "Qualität auf einen Blick", 42, weight="bold")
    c.text(MX, 240, "KI-Bewertung in vier Dimensionen", TY_SUB, color=T.MUTED)
    if not a:
        analysis_footer(c)
        return
    rt = a["ratings"]
    vcol = verdict_color(a["verdict"])
    items = [("Qualität", rt.get("Qualität"), "Bilanz, Margen, Kapitalrendite"),
             ("Wachstum", rt.get("Wachstum"), "Umsatz- & Gewinndynamik"),
             ("Bewertung", rt.get("Bewertung"), "Preis vs. fairer Wert"),
             ("Katalysator", rt.get("Katalysator"), "Auslöser für Neubewertung")]
    gap, top0 = 24, 320
    cw = (c.W - 2 * MX - gap) // 2
    ch = 230
    for i, (label, val, desc) in enumerate(items):
        row, coli = divmod(i, 2)
        rx = MX + coli * (cw + gap)
        ry = top0 + row * (ch + gap)
        c.tile(rx, ry, cw, ch, color=T.PANEL)
        c.text(rx + 28, ry + 24, label.upper(), 24, color=vcol, weight="bold")
        c.text(rx + cw - 28, ry + 20, f"{val if val is not None else '–'}/5", 34,
               color=vcol, weight="bold", ha="right", font="mono")
        _stars(c, rx + 34, ry + 118, val, col=vcol, gap=46, s=430)
        for j, ln in enumerate(_wrap_px(desc, cw - 56, TY_SUB)[:2]):
            c.text(rx + 28, ry + 150 + j * 28, ln, TY_SUB, color=T.MUTED)
    analysis_footer(c)


# 9) EARNINGS-FAZIT / CTA — Speichern, Frage, Quellen-Hinweis
def slide_earnings_cta(c, e, date_iso):
    analysis_header(c, e, date_iso)
    col = earn_color(e)
    name = _e_name(e)
    c.text(MX, 184, "Speichern & mitreden", TY_H1, weight="bold")

    # Save-Box
    c.tile(MX, 272, c.W - 2 * MX, 150, color=T.PANEL)
    c.tile(MX, 272, 12, 150, color=col, radius=6)
    _draw_bookmark(c, MX + 46, 308, 44, 78, col)
    c.text(MX + 130, 298, "Speichere die Earnings-Analyse", TY_BODY, weight="bold")
    c.text(MX + 130, 298 + TY_BODY_LH,
           f"und behalte {name} zur nächsten Zahlen-Saison im Blick.",
           TY_SUB, color=T.MUTED)

    # Community-Frage
    q_text = (f"{name} nach den Zahlen: echter Turnaround oder Strohfeuer? "
              f"Schreib deine These in die Kommentare.")
    q_lines = _wrap_px(q_text, c.W - 2 * MX - 80, TY_BODY)
    q_box_h = 16 + TY_BODY_LH + len(q_lines) * TY_BODY_LH + 24
    save_box_bottom = 272 + 150
    cta_y = c.H - 330
    q_top = save_box_bottom + (cta_y - save_box_bottom - q_box_h) // 2
    c.tile(MX, q_top, c.W - 2 * MX, q_box_h, color=T.PANEL_HI)
    c.text(MX + 40, q_top + 16, "DEINE MEINUNG?", TY_SUB, color=col, weight="bold")
    _draw_paragraph(c, MX + 40, q_top + 16 + TY_BODY_LH, q_text, TY_BODY,
                    c.W - 2 * MX - 80, color=T.TEXT, weight="bold", line_h=TY_BODY_LH)

    c.text(c.W // 2, cta_y, "Folge für Earnings & Profi-Analysen", TY_BODY,
           color=T.TEXT, weight="bold", ha="center")
    c.text(c.W // 2, cta_y + TY_BODY_LH, "datengetrieben · unabhängig · systematisiert",
           TY_SUB, color=T.MUTED, ha="center")
    analysis_footer(c)


# ── Earnings-Reel (9:16): kurzer Teaser ───────────────────────────────────────
def earnings_reel_header(c, date_iso, e):
    lw = c.draw_logo(MX, 80, 50)
    if not lw:
        c.text(MX, 84, BRAND, 20, color=T.TEXT, weight="bold")
    c.text(c.W - MX, 92, fmt_de_date(date_iso), 16, color=T.MUTED, ha="right")
    col = earn_color(e)
    beat_word = "BEAT" if (e.get("eps_surprise_pct") or 0) >= 0 else "MISS"
    label = f"EARNINGS · {e['quarter']} · {beat_word}"
    w = 56 + int(len(label) * 12)
    c.tile(MX, 168, w, 54, color=T.PANEL_HI, radius=27)
    c.tile(MX + 20, 168 + 20, 14, 14, color=col, radius=7)
    c.text(MX + 46, 182, label, 18, color=col, weight="bold")


def slide_earnings_reel_cta(c, e, date_iso):
    """Hybrid-Trick: das Reel leitet auf den vollständigen Karussell-Post um.
    Reel-Slide 4 — ohne Verdict (Wunsch: Verdict nur im Karussell)."""
    earnings_reel_header(c, date_iso, e)
    col = earn_color(e)
    c.text(MX, 470, "Die ganze", 56, weight="bold")
    c.text(MX, 542, "Earnings-Analyse?", 56, color=col, weight="bold")
    box_top = 720
    box_h = 360
    c.tile(MX, box_top, c.W - 2 * MX, box_h, color=T.PANEL)
    c.tile(MX, box_top, 12, box_h, color=col, radius=6)
    _draw_paragraph(c, MX + 50, box_top + 50,
                    f"Alle Zahlen, der Turnaround-Check und die Kursziel-Szenarien "
                    f"zu {e['ticker']} findest du im Karussell-Post.", 30,
                    c.W - 2 * MX - 100, color=T.TEXT, line_h=46, max_lines=6)
    c.text(MX + 50, box_top + box_h - 86, BRAND_NAME, 40, color=col, weight="bold")
    for i in range(3):
        c.ax.scatter(c.W - MX - 60 - i * 36, c.y(box_top + box_h - 70), s=170,
                     marker="^", color=col, edgecolor="none", zorder=12)
    c.text(MX, 1230, f"Folge {BRAND_NAME} für Earnings & Analysen", 24, color=T.MUTED)
    analysis_footer(c)

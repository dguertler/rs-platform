"""
Erstellt den Strategie-Einführungs-Carousel (5 Slides, 4:5) für den ersten Post.

Erläutert die 3 Phasen des Systems und endet mit einem CTA-Slide der die
aktuelle Performance des wikifolio AI Alpha Selection zeigt.

Aufruf:
    python3 -m instagram.generate_strategy
    python3 -m instagram.generate_strategy --date 2026-06-10
"""
import argparse
import os
import textwrap
import zipfile

from . import render, theme as T
from .render import Canvas, MX, header, footer, fmt_pct, BRAND_NAME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PHASES = [
    {
        "n": 1,
        "label": "KI-gestütztes Screening",
        "body": (
            "Unser System scannt den Markt emotionslos über 6 Zeitfenster "
            "(5 Tage bis 12 Monate) und misst die relative Stärke jeder Aktie. "
            "Nur Titel, die den Gesamtmarkt konsistent outperformen, landen auf "
            "der Watchlist – datenbasiert statt nach Bauchgefühl."
        ),
    },
    {
        "n": 2,
        "label": "Trendbestätigung",
        "body": (
            "Kein blindes Kaufen. Der Einstieg erfolgt erst, wenn der Tageschart "
            "eine nachhaltige Trendwende bestätigt und wichtige Widerstände bricht. "
            "So werden Fehlsignale konsequent aussortiert."
        ),
    },
    {
        "n": 3,
        "label": "Präzisionseinstieg & Risiko",
        "body": (
            "Feintuning in der Beschleunigungsphase – kombiniert mit striktem "
            "Risikomanagement (rund 1 % Risiko pro Trade). Das Ergebnis: ein "
            "fokussiertes Depot aus 15–20 quantitativ bestätigten Outperformern."
        ),
    },
]


def _wrap(c, x, top, text, size, color, line_h, weight="normal"):
    """Fließtext zeilenweise zeichnen. Gibt y nach letzter Zeile zurück."""
    chars = max(20, int((c.W - 2 * MX) / (size * 0.56)))
    y = top
    for line in textwrap.wrap(text, width=chars):
        c.text(x, y, line, size, color=color, weight=weight)
        y += line_h
    return y


def slide_intro(c, date_iso):
    """Slide 1 — DIE STRATEGIE: Hook-Frage + Subtitle."""
    header(c, date_iso)

    c.text(MX, 285, "DIE STRATEGIE", 18, color=T.BLUE, weight="bold")

    h1_lines = textwrap.wrap("Wie schlägt man den NASDAQ-100?", width=20)
    y = 335
    for line in h1_lines:
        c.text(MX, y, line, 72, color=T.TEXT, weight="bold")
        y += 94

    c.text(MX, y + 30, "Das datengetriebene System hinter AI Alpha Selection.",
           28, color=T.SUBTLE)

    footer(c)


def slide_phase(c, date_iso, phase):
    """Slides 2–4 — PHASE 1/2/3."""
    header(c, date_iso)

    box_size = 112
    box_top  = 190

    # Nummern-Box
    c.tile(MX, box_top, box_size, box_size, color=T.PANEL_HI, radius=22)
    c.text(MX + box_size // 2, box_top + 8, str(phase["n"]), 80,
           color=T.TEXT, weight="bold", ha="center")

    # Phase-Label + Titel
    lx = MX + box_size + 30
    c.text(lx, box_top + 8,  f"PHASE {phase['n']}", 18, color=T.BLUE, weight="bold")
    title_lines = textwrap.wrap(phase["label"], width=28)
    ty = box_top + 46
    for line in title_lines:
        c.text(lx, ty, line, 36, color=T.TEXT, weight="bold")
        ty += 48

    # Body-Text
    _wrap(c, MX, box_top + box_size + 54, phase["body"], 28, T.SUBTLE, line_h=46)

    footer(c)


def slide_cta(c, date_iso, total_perf, nas_total, weeks):
    """Slide 5 — Folge dem wikifolio: Performance-Box + Disclaimer-Box."""
    header(c, date_iso)

    c.text(MX, 190, "Folge dem wikifolio", 52, color=T.TEXT, weight="bold")

    # Performance-Box
    pb_top = 272
    pb_h   = 140
    c.tile(MX, pb_top, c.W - 2 * MX, pb_h, color=T.PANEL)
    nas_str = fmt_pct(nas_total)
    c.text(MX + 30, pb_top + 22,
           f"wikifolio AI Alpha Selection · erste {weeks} Wochen · NASDAQ-100 {nas_str}",
           17, color=T.MUTED)
    c.text(MX + 30, pb_top + 50, fmt_pct(total_perf), 58,
           color=T.GREEN, weight="bold", font="mono")

    # Body-Text
    body = (
        "Jeder Trade ist öffentlich und zu 100 % transparent nachvollziehbar. "
        f"Folge dem wikifolio „AI Alpha Selection“ – Link in der Bio."
    )
    body_top = pb_top + pb_h + 44
    body_end = _wrap(c, MX, body_top, body, 28, T.SUBTLE, line_h=46)

    # Risikohinweis-Box
    risk_top = max(body_end + 36, 800)
    risk_h   = 240
    c.tile(MX, risk_top, c.W - 2 * MX, risk_h, color=T.PANEL, radius=20)
    c.text(MX + 30, risk_top + 24, "RISIKOHINWEIS", 17, color=T.BLUE, weight="bold")
    risk_body = (
        "Dieser Beitrag bezieht sich auf das wikifolio „AI Alpha Selection“ "
        "und dient der Information/Eigenwerbung. Keine Anlageberatung, keine "
        "Kauf-/Verkaufsempfehlung, insbesondere kein Erwerb eines Zertifikats. "
        "Vergangene Wertentwicklung ist kein verlässlicher Indikator für die "
        "Zukunft. Kapitalanlagen bergen Verlustrisiken bis zum Totalverlust."
    )
    ry = risk_top + 58
    chars = max(20, int((c.W - 2 * MX - 60) / (16 * 0.56)))
    for line in textwrap.wrap(risk_body, width=chars):
        c.text(MX + 30, ry, line, 16, color=T.MUTED)
        ry += 28

    footer(c)


def _load_perf():
    """Aktuelle Gesamtrendite + NASDAQ + Anzahl Wochen aus wikifolio_history."""
    try:
        import json
        from . import data as _data

        hist_path = os.path.join(ROOT, "instagram", "data", "wikifolio_history.json")
        hist = json.load(open(hist_path))
        weekly = sorted(hist["weekly"], key=lambda w: w["kw"])
        if not weekly:
            return 0.52, 0.27, 10

        start_val = json.load(open(
            os.path.join(ROOT, "instagram", "data", "config.json")
        )).get("start_value", 98.48)
        last_val  = weekly[-1]["value"]
        total_perf = last_val / start_val - 1

        weeks = len(weekly)

        start_date = weekly[0]["date"]
        end_date   = weekly[-1]["date"]
        try:
            _, benchmark = _data.load_universe()
            bench = list(benchmark)
            v0 = v1 = None
            for d, c_val in bench:
                if d <= start_date:
                    v0 = c_val
                if d <= end_date:
                    v1 = c_val
            nas_total = (v1 / v0 - 1) if v0 and v1 else 0.27
        except Exception:
            nas_total = 0.27

        return total_perf, nas_total, weeks
    except Exception:
        return 0.52, 0.27, 10


def build_strategy(date_iso=None, outdir=None):
    from datetime import date as _d
    if date_iso is None:
        date_iso = _d.today().isoformat()
    if outdir is None:
        outdir = os.path.join(ROOT, "out", "instagram", f"{date_iso}_STRATEGIE")
    carousel_dir = os.path.join(outdir, "carousel")
    os.makedirs(carousel_dir, exist_ok=True)

    total_perf, nas_total, weeks = _load_perf()

    slides = []

    c = Canvas("carousel")
    slide_intro(c, date_iso)
    p = os.path.join(carousel_dir, "01_intro.png")
    c.save(p); slides.append(p)

    for phase in PHASES:
        c = Canvas("carousel")
        slide_phase(c, date_iso, phase)
        p = os.path.join(carousel_dir, f"0{phase['n'] + 1}_phase{phase['n']}.png")
        c.save(p); slides.append(p)

    c = Canvas("carousel")
    slide_cta(c, date_iso, total_perf, nas_total, weeks)
    p = os.path.join(carousel_dir, "05_cta.png")
    c.save(p); slides.append(p)

    # Caption
    caption = _build_caption(total_perf, nas_total, weeks)
    cap_path = os.path.join(outdir, "caption.txt")
    with open(cap_path, "w") as f:
        f.write(caption)

    # ALT-Texte
    alt_lines = [
        "Slide 1: AI Alpha Selection Strategie — Wie schlägt man den NASDAQ-100?",
        "Slide 2: Phase 1 KI-gestütztes Screening — relative Stärke über 6 Zeitfenster",
        "Slide 3: Phase 2 Trendbestätigung — Einstieg nach Breakout, keine Fehlsignale",
        "Slide 4: Phase 3 Präzisionseinstieg und Risikomanagement — 1% Risiko pro Trade",
        f"Slide 5: wikifolio AI Alpha Selection Performance {fmt_pct(total_perf)} in {weeks} Wochen vs. NASDAQ-100 {fmt_pct(nas_total)}",
    ]
    with open(os.path.join(outdir, "alt_texts.txt"), "w") as f:
        f.write("# ALT-Texte für Instagram-Upload\n"
                "# Beim manuellen Hochladen pro Slide eintragen\n\n")
        f.write("\n".join(alt_lines) + "\n")

    # ZIP
    zip_path = os.path.join(outdir, "carousel_STRATEGIE.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in slides:
            zf.write(s, os.path.basename(s))
    slides.append(zip_path)

    print(f"✓ {len(slides)} Dateien (Strategie-Post) in {outdir}")
    print(f"  Performance: {fmt_pct(total_perf)} · NASDAQ: {fmt_pct(nas_total)} · {weeks} Wochen")
    for s in slides:
        print("  ", os.path.relpath(s, ROOT))
    return slides, outdir


def _build_caption(total_perf, nas_total, weeks):
    disc = T.DISCLAIMER_LONG
    return (
        f"NASDAQ-100 schlagen mit Algorithmus: die 3-Phasen-Strategie hinter AI Alpha Selection 📊\n\n"
        f"{fmt_pct(total_perf)} in {weeks} Wochen · NASDAQ-100 im selben Zeitraum: {fmt_pct(nas_total)}\n\n"
        f"Wie das System funktioniert, zeigen die Slides:\n"
        f"KI-Screening → Trendbestätigung → Präzisionseinstieg mit ~1 % Risiko pro Trade.\n\n"
        f"Jeder Trade öffentlich und 100 % transparent nachvollziehbar.\n"
        f"👉 Link zum wikifolio AI Alpha Selection in der Bio.\n\n"
        f"💬 Welche Phase interessiert dich am meisten — Screening, Trendbestätigung oder Risikomanagement?\n\n"
        f"❗ {disc}\n\n"
        f"#wikifolio #algotrading #nasdaq100 #relativestärke #aialphaselection"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--out",  default=None)
    args = ap.parse_args()
    build_strategy(date_iso=args.date, outdir=args.out)


if __name__ == "__main__":
    main()

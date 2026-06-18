"""
AI Alpha Selection — Instagram-Generator

Erzeugt ein komplettes Slide-Set (Carousel 4:5 + Reel-Frames 9:16) plus
Caption-Text in einen Review-Ordner. NICHTS wird hochgeladen – du prüfst
alles und lädst manuell hoch.

Aufruf:
    python3 -m instagram.generate                 # beide Formate, heutiges Datum
    python3 -m instagram.generate --format carousel
    python3 -m instagram.generate --signals 3

Output:  out/instagram/<YYYY-MM-DD>/<format>/NN_*.png  +  caption.txt
"""
import argparse
import os
import re
from datetime import datetime, timezone

from . import data, render, report, store
from . import analysis as ana
from . import earnings as earn
from . import hook_generator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pos_sub(t):
    s = t.get("name", "")
    if t.get("buy_date"):
        s += f" · Kauf {render.fmt_de_date(t['buy_date'])}"
    if t.get("buy_price_eur"):
        s += f" · {render.fmt_eur(t['buy_price_eur'])}"
    return s


def _hook_metrics(ctx):
    """1–2 prominente Kennzahlen als visueller Beweis für den Dynamic Hook."""
    return [
        ("Gesamtrendite seit Start", render.fmt_pct(ctx["total_perf"]),
         render.T.GREEN if ctx["total_perf"] >= 0 else render.T.RED),
        ("NASDAQ-100 seit Start", render.fmt_pct(ctx["nasdaq_total"]), render.T.BLUE),
    ]


def auto_hook(ctx):
    """Fallback-Schlagzeile aus den Daten, falls Claude keine `--hook` setzt.
    Claude sollte pro Woche eine eigene, ereignisbezogene Headline übergeben."""
    alpha = render.fmt_pct(ctx["alpha"])
    if ctx["alpha"] >= 0:
        return f"{alpha} Alpha: Während der NASDAQ schlief, hat die KI agiert."
    return "Sturm an der Börse — wie die KI das Depot stabil hält."


def auto_why(ctx):
    """Fallback-Begründung der KI-Logik, falls Claude kein `--why` setzt."""
    f = ctx["featured"]["ticker"]
    return (f"Unser KI-Modell hat diese Woche den Fokus auf relative Stärke im "
            f"Sektor gelegt — ein bestätigter Trend hat die Signale für {f} "
            f"getriggert.")


def auto_question(ctx):
    """Fallback-Interaktionsfrage, falls Claude keine `--frage` setzt."""
    f = ctx["featured"]["ticker"]
    return (f"Hättest du {f} bei diesem Kurs auch gekauft – oder auf einen "
            f"Rücksetzer gewartet? Schreib's unten rein!")


def build_from_store(fmt, ctx, outdir):
    """Wochen-Carousel aus den persistenten Daten (store.compute)."""
    saved = []
    emit = _emitter(fmt, outdir, saved)
    di = ctx["date_iso"]

    # 1) Dynamic Hook (visueller Stopper, KEIN Dashboard) — Schlagzeile + Beweis
    emit("hook", lambda c: render.slide_hook_dynamic(
        c, di, ctx["hook"], _hook_metrics(ctx), kw=ctx["kw"]))
    # 2) Performance (Eye-Catcher) inkl. Kennzahlen unter dem Graph
    emit("performance", lambda c: render.slide_performance(
        c, di, ctx["eq_dates"], ctx["eq_vals"], ctx["nas_dates"], ctx["nas_vals"],
        ctx["total_perf"], ctx["nasdaq_total"], False, stats=ctx["stats"]))
    # 3) Wochen-Historie (Mehrrendite ggü. NASDAQ) — erst ab 2+ Wochen sinnvoll (KW15+)
    if len(ctx["history"]) >= 2:
        emit("historie", lambda c: render.slide_history(c, di, ctx["history"]))
    # 4) Stärkste Positionen (nur Positionen mit Kursdaten; ret=None werden ausgeblendet)
    _pos_with_data = [t for t in ctx["top_holdings"] if t["ret"] is not None]
    if _pos_with_data:
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]),
                 "color": render.T.GREEN if t["ret"] >= 0 else render.T.RED,
                 "value_font": "mono"}
                for t in _pos_with_data]
        emit("positionen", lambda c: render.slide_list(
            c, di, "Stärkste Positionen", "Wertzuwachs seit Kauf", rows))
    # 5) Aktie der Woche (Rotation) — vor warum für besseren Lesefluss
    if ctx["featured"]["entry"]:
        emit(f"aktie_{ctx['featured']['ticker'].replace('.', '_')}",
             lambda c: render.slide_featured(c, di, ctx["featured"]))
    # 6) Weitere Positionen (alle außerhalb der Top-5, nur mit Kursdaten) — vor warum
    _rest_with_data = [t for t in ctx.get("rest_holdings", []) if t["ret"] is not None]
    if _rest_with_data:
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]),
                 "color": render.T.GREEN if t["ret"] >= 0 else render.T.RED,
                 "value_font": "mono"}
                for t in _rest_with_data]
        emit("weitere", lambda c: render.slide_list(
            c, di, "Weitere Positionen", "Wertzuwachs seit Kauf", rows))
    # 7) Newcomer (bester Kauf der letzten 3 Wochen, nicht in Top-5) — vor warum
    if ctx.get("newcomer") and ctx["newcomer"]["entry"]:
        emit(f"newcomer_{ctx['newcomer']['ticker'].replace('.', '_')}",
             lambda c: render.slide_featured(c, di, ctx["newcomer"], label="NEWCOMER"))
    # 8) Strategisches „Warum" (KI-Kontext) — nach den Positionsslides
    emit("warum", lambda c: render.slide_why(c, di, ctx["why"]))
    # 9+) Trade der Woche: alle realisierten Verkäufe der KW (Kauf grün + Verkauf rot)
    for _tr in ctx.get("trades", []):
        if _tr.get("entry"):
            _tk = _tr["ticker"].replace(".", "_")
            emit(f"trade_{_tk}",
                 lambda c, t=_tr: render.slide_featured(c, di, t, label="TRADE DER WOCHE"))
    # Last) CTA: Bio-Link-Pfad + dynamische Interaktions-Frage + Risikohinweis
    emit("cta", lambda c: render.slide_cta(
        c, di, question=ctx["question"], account=ctx["account"]))
    return saved


def caption_from_store(ctx):
    """Wochen-Carousel-Caption. SEO-Keyword 'Wikifolio' zuerst (IG indexiert die
    ersten 125 Zeichen besonders stark). Kurz gehalten: Hook + 2 Kennzahlen +
    Slides-CTA — Details (Positionen, Trades, Kennzahlen) stehen auf den Slides."""
    return (
        f"Wikifolio Wochenupdate KW {ctx['kw']}: {ctx['hook']} 📊\n\n"
        f"Gesamtrendite seit Start: {render.fmt_pct(ctx['total_perf'])} | "
        f"Alpha ggü. NASDAQ-100: {render.fmt_pct(ctx['alpha'])}\n\n"
        f"Alle Positionen, Charts und Trades auf den Slides. Speichere für deinen Überblick.\n\n"
        f"👉 Link zum wikifolio AI Alpha Selection in der Bio.\n\n"
        f"💬 {ctx['question']}\n\n"
        f"{render.T.DISCLAIMER_LONG}\n\n"
        f"{HASHTAGS_WEEKLY}"
    )


def reel_caption_from_store(ctx):
    """Caption für das Wochen-Reel (eigener IG-Post, getrennt vom Carousel). Teaser
    → leitet auf den Karussell-Post um (Hybrid-Funnel). Bewusst kurz: Hook + die
    zwei stärksten Kennzahlen (Alpha/Gesamtrendite) als Beweis + Funnel-CTA aufs
    Karussell + Bio-Hinweis + Interaktions-Frage + Disclaimer + 5 Hashtags."""
    return (
        f"Wikifolio Wochenupdate KW {ctx['kw']}: {ctx['hook']} 📊\n\n"
        f"Gesamtrendite seit Start: {render.fmt_pct(ctx['total_perf'])} · "
        f"Alpha ggü. NASDAQ-100: {render.fmt_pct(ctx['alpha'])}\n\n"
        f"🎬 Das ist der Teaser. Alle Positionen, Charts und Trades im "
        f"Karussell-Post auf meinem Profil.\n\n"
        f"👉 Link zum wikifolio AI Alpha Selection in der Bio.\n\n"
        f"💬 {ctx['question']}\n\n"
        f"{render.T.DISCLAIMER_LONG}\n\n"
        f"{HASHTAGS_WEEKLY}"
    )


def _emitter(fmt, outdir, saved):
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):           # veraltete Slides entfernen
        if f.endswith(".png"):
            os.remove(os.path.join(outdir, f))
    counter = {"n": 0}

    def emit(name, draw):
        counter["n"] += 1
        c = render.Canvas(fmt)
        draw(c)
        path = os.path.join(outdir, f"{counter['n']:02d}_{name}.png")
        c.save(path)
        saved.append(path)
    return emit


def build_weekly(fmt, r, benchmark, date_iso, outdir):
    """Wochenreport-Carousel aus instagram/reports/KW<NN>.json."""
    saved = []
    emit = _emitter(fmt, outdir, saved)
    nas_dates, nas_vals = data.benchmark_window(
        benchmark or [], r["eq_dates"][0], r["eq_dates"][-1])

    emit("hook", lambda c: render.slide_hook_weekly(
        c, date_iso, r["kw"], r["period"], r["week_perf"], r["total_perf"]))
    emit("performance", lambda c: render.slide_performance(
        c, date_iso, r["eq_dates"], r["eq_vals"], nas_dates, nas_vals,
        r["total_perf"], r["nasdaq_total"], False))
    emit("kpis", lambda c: render.slide_kpis_weekly(
        c, date_iso, r["total_perf"], r["alpha"], r["weeks_beaten"],
        r["weeks_total"], r["avg_win"], r["avg_loss"]))
    emit("historie", lambda c: render.slide_history(c, date_iso, r["history"]))

    if r["buys"]:
        rows = [{"main": b["ticker"], "sub": f"{b['name']} · {b['date']}",
                 "value": render.fmt_pct(b.get("size", 0), signed=False),
                 "color": render.T.GREEN} for b in r["buys"]]
        emit("kaeufe", lambda c: render.slide_list(
            c, date_iso, "Käufe der Woche", "Positionsgröße im Depot", rows))
    if r["top_holdings"]:
        rows = [{"main": t["ticker"], "sub": t.get("name", ""),
                 "value": render.fmt_pct(t["ret"]), "color": render.T.GREEN}
                for t in r["top_holdings"]]
        emit("top", lambda c: render.slide_list(
            c, date_iso, "Stärkste Positionen", "Wertzuwachs seit Kauf", rows))
    if r["sells"]:
        rows = [{"main": s["ticker"], "sub": f"{s['name']} · {s['date']}",
                 "value": render.fmt_pct(s["ret"]),
                 "color": render.T.GREEN if s["ret"] >= 0 else render.T.RED}
                for s in r["sells"]]
        emit("verkaeufe", lambda c: render.slide_list(
            c, date_iso, "Verkäufe der Woche", "Performance bei Verkauf", rows))

    emit("cta", lambda c: render.slide_cta(c, date_iso))
    return saved


def build_weekly_caption(r):
    def line_buys():
        return "\n".join(f"✅ {b['ticker']} — {b['name']} ({b['date']}, "
                         f"{render.fmt_pct(b.get('size', 0), signed=False)})"
                         for b in r["buys"])

    def line_sells():
        return "\n".join(f"{'✅' if s['ret'] >= 0 else '❌'} {s['ticker']} — "
                         f"{s['name']} ({s['date']}, {render.fmt_pct(s['ret'])})"
                         for s in r["sells"])

    parts = [
        f"Wikifolio Wochenupdate KW {r['kw']} 📊\n",
        f"Gesamtrendite seit Start: {render.fmt_pct(r['total_perf'])} | "
        f"Alpha ggü. NASDAQ-100: {render.fmt_pct(r['alpha'])}\n",
    ]
    if r["buys"]:
        parts.append("Käufe:\n" + line_buys() + "\n")
    if r["sells"]:
        parts.append("Verkäufe:\n" + line_sells() + "\n")
    parts.append("Alle Charts und Positionen auf den Slides. "
                 "👉 Link zum wikifolio AI Alpha Selection in der Bio.\n")
    parts.append(render.T.DISCLAIMER_LONG)
    parts.append("\n" + HASHTAGS_WEEKLY)
    return "\n".join(parts)


# ── Aktien-Analyse-Post (analyses/TICKER.md) ──────────────────────────────────
def _has_scenarios(a):
    sc = a["scenarios"]
    return all(sc[k]["prob"] is not None for k in ("bull", "base", "bear"))


def _has_longterm(a):
    lt = a["longterm"]
    return any(lt[k] and lt[k].get("low") is not None for k in ("bull", "base", "bear"))


def build_analysis(fmt, a, date_iso, outdir):
    """Analyse-Carousel aus einer geparsten Analyse (analyses/TICKER.md)."""
    saved = []
    emit = _emitter(fmt, outdir, saved)

    emit("cover",         lambda c: render.slide_analysis_cover(c, a, date_iso))
    emit("einschaetzung", lambda c: render.slide_analysis_verdict(c, a, date_iso))
    # Geschäftsmodell VOR Szenarien — logischer Lesefluss
    if a.get("business_bullets"):
        emit("unternehmen", lambda c: render.slide_analysis_business(c, a, date_iso))
    if _has_scenarios(a):
        emit("szenarien", lambda c: render.slide_analysis_scenarios(c, a, date_iso))
    if _has_scenarios(a):
        # Overflow-Check: wieviele Szenarien passen auf eine Slide?
        # Verfügbar: H(1350) - 160(footer_y-offset) - 300(top0) = 890 px
        _avail = 890
        _gap = 22
        _items = render._cases_item_data(a)
        # Finde maximale Anzahl Items, die auf eine Slide passen
        _fit1, _used = [], 0
        for _it in _items:
            _needed = _it["rh"] + (_gap if _fit1 else 0)
            if _used + _needed <= _avail:
                _fit1.append(_it)
                _used += _needed
            else:
                break
        _rest = _items[len(_fit1):]
        if not _rest:
            emit("szenarien_erklaert",
                 lambda c, _i=_items: render.slide_analysis_cases(c, a, date_iso, _i))
        else:
            emit("szenarien_erklaert_1",
                 lambda c, _i=_fit1: render.slide_analysis_cases(c, a, date_iso, _i))
            # Rest ggf. weiter aufteilen
            _fit2, _used2 = [], 0
            for _it in _rest:
                _needed = _it["rh"] + (_gap if _fit2 else 0)
                if _used2 + _needed <= _avail:
                    _fit2.append(_it)
                    _used2 += _needed
                else:
                    break
            _rest2 = _rest[len(_fit2):]
            emit("szenarien_erklaert_2",
                 lambda c, _i=_fit2: render.slide_analysis_cases(c, a, date_iso, _i))
            if _rest2:
                emit("szenarien_erklaert_3",
                     lambda c, _i=_rest2: render.slide_analysis_cases(c, a, date_iso, _i))
    elif a.get("pro_bullets") or a.get("con_bullets"):
        emit("chancen_risiken", lambda c: render.slide_analysis_chances(c, a, date_iso))
    if a["sections"].get(6):
        emit("fundamentals",  lambda c: render.slide_analysis_fundamentals(c, a, date_iso))
    if a["sections"].get(7):
        emit("bewertung",     lambda c: render.slide_analysis_valuation(c, a, date_iso))
    if a["sections"].get(8):
        emit("risiko",        lambda c: render.slide_analysis_risk(c, a, date_iso))
    if a["sections"].get(9):
        emit("technical",     lambda c: render.slide_analysis_technical(c, a, date_iso))
    if _has_longterm(a):
        emit("langfrist",     lambda c: render.slide_analysis_longterm(c, a, date_iso))
    emit("fazit",         lambda c: render.slide_analysis_fazit(c, a, date_iso))
    emit("cta",           lambda c: render.slide_analysis_cta(c, a, date_iso))

    # ZIP-Archiv aller Carousel-Slides für einfachen Download
    import zipfile as _zf
    zip_path = os.path.join(os.path.dirname(outdir), f"carousel_{a['ticker']}.zip")
    with _zf.ZipFile(zip_path, "w", _zf.ZIP_DEFLATED) as zf:
        for p in sorted(saved):
            zf.write(p, os.path.basename(p))
    saved.append(zip_path)
    return saved


def build_analysis_reel(a, date_iso, outdir):
    """Reel-Teaser (9:16): kurz & knackig, leitet auf den Karussell-Post um."""
    saved = []
    emit = _emitter("reel", outdir, saved)
    emit("hook", lambda c: render.slide_reel_hook(c, a, date_iso))
    if _has_scenarios(a):
        emit("szenarien", lambda c: render.slide_reel_scenarios(c, a, date_iso))
    emit("fazit", lambda c: render.slide_reel_takeaway(c, a, date_iso))
    emit("cta", lambda c: render.slide_reel_cta(c, a, date_iso))
    return saved


def reel_script(a):
    """Fertiges Voiceover-Script + KI-Generator-Prompt (InVideo/Veo/CapCut).
    Dynamisch aus der Analyse — im Stil eines düsteren, professionellen
    Finanz-Reels (9:16)."""
    name = render.A.short_name(a["name"])
    t = a["ticker"]
    broll = {
        "Technology": "Makroaufnahmen glühender Mikrochips, Serverräume mit "
                      "blinkenden LEDs, fließender Code auf Monitoren, abstrakte "
                      "3D-Aktiencharts",
        "Healthcare": "moderne Labore, DNA-/Molekül-Visualisierungen, Pipetten "
                      "und Reinräume, abstrakte 3D-Aktiencharts",
        "Industrials": "Roboterarme in Fabriken, Stromnetze und Turbinen, "
                       "Hightech-Produktion, abstrakte 3D-Aktiencharts",
        "Energy": "Windräder und Solarfelder, Stromnetze bei Nacht, Turbinen, "
                  "abstrakte 3D-Aktiencharts",
    }.get(a.get("sector", ""), "abstrakte Hightech- und Finanz-Visualisierungen, "
          "Serverräume, fließender Code, 3D-Aktiencharts")

    pe = ana.pe_multiples(a["sections"].get(7, ""))
    misconception = ""
    if pe["trailing"] and pe["forward"]:
        misconception = (f"Wer nur auf das optische KGV von {pe['trailing']}x schaut, "
                         f"versteht die Aktie nicht — relevant ist das Forward-KGV "
                         f"von {pe['forward']}x.")

    sc = a["scenarios"]
    def rng(k): return ana.fmt_range(sc[k]["range"]) if _has_scenarios(a) else ""
    targets = ""
    if _has_scenarios(a):
        lo = rng("bear").split("–")[0] if rng("bear") else ""
        hi = rng("bull").split("–")[-1] if rng("bull") else ""
        targets = f"{lo} bis {hi}".strip()

    bear = ana.clean_for_slide(sc["bear"]["summary"]) if _has_scenarios(a) else ""
    headline = render.analysis_headline(a)

    # Psychologischer Hook (zufällig gezogen, konsistent für diesen Durchlauf)
    psych = hook_generator.get_hook(t)

    L = []
    L.append("# REEL-SCRIPT — " + f"{name} ({t})")
    L.append("# Format 9:16 · ~15–45 Sek · faceless")
    L.append("# Für cinematic_reel.py ODER InVideo AI / Google Veo / CapCut")
    L.append(f"# Hook-Typ: {psych['typ']}")
    L.append("")
    L.append("## [AI-GENERATOR-PROMPT]")
    L.append(
        f"\"Erstelle ein düsteres, hochprofessionelles Finanz-Reel für Instagram "
        f"im Format 9:16. Schnelle, dynamische Schnitte alle ~2–3 Sekunden. "
        f"Visueller Stil: minimalistisch, cineastisch, High-Tech, dunkler "
        f"Hintergrund mit blauen/cyan Akzenten. B-Roll: {broll}. Stimme: tiefe, "
        f"professionelle, charismatische deutsche Männerstimme (KI). Musik: "
        f"subtiler, rhythmischer, dramatischer Tech-Beat. Untertitel groß, fett, "
        f"zentriert, wortweise synchron zum Voiceover aufpoppend.\"")
    L.append("")
    L.append("## [SCRIPT]")
    L.append("[SZENE 1 – 0:00–0:03]  ← HOOK (cinematic_reel.py: Szene 1)")
    L.append(f"Visual: [Pexels: {psych['visual']}]")
    L.append(f"Voiceover: \"{psych['text']}\"")
    L.append("")
    L.append(f"[SZENE 2 – 0:03–0:06]  (Overlay: {t} — {a['verdict']})")
    L.append(f"Visual: [Pexels: {broll.split(',')[0].strip()} 4k]")
    L.append(f"Voiceover: \"{headline} {a.get('hook','')}\"")
    L.append("")
    if misconception:
        L.append(f"[SZENE 3 – 0:06–0:14]  (Overlay: KGV {pe['trailing']}x = irreführend)")
        L.append(f"Visual: [Pexels: abstract financial data neon 4k]")
        L.append(f"Voiceover: \"{misconception}\"")
        L.append("")
    core = ana.clean_for_slide(a["sections"].get(1, ""))
    csents = ana.sentences(core)
    core_vo = " ".join(csents[1:3]).strip() if len(csents) > 1 else core
    if core_vo:
        L.append("[SZENE 4 – 0:14–0:24]  (Overlay: Der Kern)")
        L.append(f"Visual: [Pexels: {broll.split(',')[0].strip()} 4k]")
        L.append(f"Voiceover: \"{core_vo}\"")
        L.append("")
    if bear:
        L.append("[SZENE 5 – 0:24–0:34]  (Overlay: Das größte Risiko)")
        L.append(f"Visual: [Pexels: dark risk warning abstract 4k]")
        L.append(f"Voiceover: \"Das Hauptrisiko: {bear}\"")
        L.append("")
    if _has_scenarios(a):
        L.append("[SZENE 6 – 0:34–0:41]  (Overlay: Szenarien & Kursziele)")
        L.append(f"Visual: [Pexels: stock market chart three scenarios 4k]")
        L.append(f"Voiceover: \"Drei Szenarien auf 12 bis 18 Monate: Bull "
                 f"{sc['bull']['prob']} Prozent, Base {sc['base']['prob']} Prozent, "
                 f"Bear {sc['bear']['prob']} Prozent — Kursziele {targets}.\"")
        L.append("")
    L.append("[SZENE 7 – 0:41–0:46]  (Overlay: Ganze Analyse im Karussell 👆)")
    L.append(f"Visual: [Pexels: dark screen carousel swipe 4k]")
    L.append(f"Voiceover: \"Den kompletten Deep Dive mit allen Kurszielen findest du im "
             f"Karussell-Post auf diesem Profil. Folge {render.BRAND_NAME} für 1–2 "
             f"Profi-Analysen pro Woche.\"")
    L.append("")
    L.append("## [HINWEIS]  Pflicht-Disclaimer einblenden/vorlesen:")
    L.append("Keine Anlageberatung · KI-generierte Analyse · Kursziele sind "
             "Szenarien, keine Prognosen.")
    L.append("")
    L.append("## [CINEMATIC RENDER]")
    L.append("# Cinematisches Rendering (Stage 2 — nach Bestätigung):")
    L.append(f"# python3 instagram/cinematic_reel.py --ticker {t} \\")
    L.append(f"#   --hook-typ {psych['typ']} \\")
    L.append(f"#   --script <pfad>/reel_script.txt \\")
    L.append(f"#   --output <pfad>/reel_cinematic.mp4")
    return "\n".join(L)


# ── Hashtags: max. 5 pro Post (Instagram-Limit seit 2025; optimal 3–5) ───────
# Wenige, hochrelevante Tags = Kontextsignal für den Algorithmus.
# Mix: Ticker + Kern-Keyword + Sektor/Thema + breit + Brand.
HASHTAGS_WEEKLY = "#wikifolio #algotrading #nasdaq100 #investieren #aialphaselection"

_SECTOR_TAG = {
    "Technology": "#technologieaktien",
    "Healthcare": "#healthcare",
    "Industrials": "#industrieaktien",
    "Energy": "#energieaktien",
    "Financial Services": "#finanzaktien",
    "Consumer Cyclical": "#konsumaktien",
}


def hashtags_analysis(a):
    tic = a["ticker"].replace(".", "").lower()
    sector = _SECTOR_TAG.get(a.get("sector", ""), "#börse")
    return f"#{tic} #aktienanalyse {sector} #investieren #aialphaselection"


def hashtags_earnings(e):
    tic = e["ticker"].replace(".", "").lower()
    return f"#{tic} #earnings #quartalszahlen #aktienanalyse #aialphaselection"


def caption_analysis(a):
    """Kurz-Caption für Analyse-Posts. SEO-Zeile: Keyword (Firmenname + Ticker +
    'Aktienanalyse') zuerst, Emoji danach — Instagram indexiert die ersten 125 Zeichen
    besonders stark. Die VOLLE Analyse steht auf den Slides (kein Analyse-Content in
    der Caption). Max. 5 Hashtags (Instagram-Limit seit 2025; optimal 3–5)."""
    v = a["verdict"]
    scal = (f" · Score {a['score']}/100" if a["score"] is not None else "")
    name = render.A.short_name(a["name"])
    DISC = render.T.DISCLAIMER_ANALYSE_SHORT
    parts = [f"{name} ({a['ticker']}) Aktienanalyse: {v}{scal} 📊\n"]
    # Psychologischer Hook als zweite Zeile (Verlustangst / Wissenslücke / Widerspruch)
    psych_hook = hook_generator.get_hook(a["ticker"])
    parts.append(psych_hook["text"] + "\n")
    if a.get("hook") and a["hook"] != psych_hook["text"]:
        parts.append(a["hook"] + "\n")
    parts.append("Die komplette Analyse — Szenarien mit Kurszielen, Bewertung und "
                 "Profi-Fazit — auf den Slides. Speichere für deine Watchlist.\n")
    parts.append("👉 Folge AI Alpha Selection für wöchentliche Profi-Analysen.\n")
    parts.append("❗ " + DISC)
    parts.append("\n" + hashtags_analysis(a))
    return "\n".join(parts)


def reel_caption_analysis(a):
    """Caption für das Reel (eigener IG-Post, getrennt vom Carousel). Das Reel ist
    der Teaser, der Reichweite holt und auf den Karussell-Post umleitet
    (Hybrid-Funnel). Aufbau wie die Carousel-Caption — SEO-Zeile (Keyword zuerst)
    für die Reel-Suche, Hook, aber statt Save-CTA der Funnel-CTA aufs Karussell —
    Disclaimer + dieselben max. 5 Hashtags."""
    v = a["verdict"]
    scal = (f" · Score {a['score']}/100" if a["score"] is not None else "")
    name = render.A.short_name(a["name"])
    DISC = render.T.DISCLAIMER_ANALYSE_SHORT
    parts = [f"{name} ({a['ticker']}) Aktienanalyse: {v}{scal} 📊\n"]
    if a.get("headline") or a.get("hook"):
        parts.append((a.get("headline") or a["hook"]) + "\n")
    parts.append("🎬 Das ist der Teaser. Die komplette Analyse — Szenarien mit "
                 "Kurszielen, Bewertung und Profi-Fazit — im Karussell-Post auf "
                 "meinem Profil.\n")
    parts.append("👉 Folge AI Alpha Selection für wöchentliche Profi-Analysen.\n")
    parts.append("❗ " + DISC)
    parts.append("\n" + hashtags_analysis(a))
    return "\n".join(parts)


# ── Earnings-Analyse-Post (instagram/data/earnings/TICKER.json) ───────────────
def build_earnings(fmt, e, date_iso, outdir):
    """Earnings-Carousel: Beat-Story + Earnings-Tiefgang + Verknüpfung zur These.
    Eigenständig; die Basis-Analyse (e['analysis']) liefert Geschäftsmodell,
    Verdict, Bewertung, Sterne, Szenarien & Kursziele. Earnings-spezifische
    Tiefen-Slides (Quartals-Trend, Segmente) erscheinen nur, wenn die Daten in der
    Earnings-JSON stehen."""
    saved = []
    emit = _emitter(fmt, outdir, saved)
    a = e.get("analysis")

    # ── Earnings-Block: die News ──────────────────────────────────────────────
    emit("cover",     lambda c: render.slide_earnings_cover(c, e, date_iso))
    emit("zahlen",    lambda c: render.slide_earnings_numbers(c, e, date_iso))
    if e.get("quarterly"):
        emit("quartale", lambda c: render.slide_earnings_quarterly(c, e, date_iso))
    if e.get("reaction_ohlcv"):
        emit("reaktion", lambda c: render.slide_earnings_reaction(c, e, date_iso))
    if e.get("guidance") or e.get("drivers") or e.get("key_metric_value"):
        emit("ausblick", lambda c: render.slide_earnings_guidance(c, e, date_iso))
    if e.get("segments"):
        emit("segmente", lambda c: render.slide_earnings_segments(c, e, date_iso))
    # ── Unternehmen & These aus der Basis-Analyse ─────────────────────────────
    if a and a.get("business_bullets"):
        emit("unternehmen", lambda c: render.slide_analysis_business(c, a, date_iso))
    if a and e.get("context"):
        emit("einordnung", lambda c: render.slide_earnings_context(c, e, date_iso))
    if a and a["sections"].get(7):
        emit("bewertung", lambda c: render.slide_analysis_valuation(c, a, date_iso))
    if a and any(a["ratings"].values()):
        emit("ratings", lambda c: render.slide_earnings_ratings(c, e, date_iso))
    if a and _has_scenarios(a):
        emit("szenarien", lambda c: render.slide_analysis_scenarios(c, a, date_iso))
    if a and _has_longterm(a):
        emit("langfrist", lambda c: render.slide_analysis_longterm(c, a, date_iso))
    if a:
        emit("fazit", lambda c: render.slide_analysis_fazit(c, a, date_iso))
    emit("cta",       lambda c: render.slide_earnings_cta(c, e, date_iso))

    import zipfile as _zf
    zip_path = os.path.join(os.path.dirname(outdir), f"carousel_{e['ticker']}.zip")
    with _zf.ZipFile(zip_path, "w", _zf.ZIP_DEFLATED) as zf:
        for p in sorted(saved):
            zf.write(p, os.path.basename(p))
    saved.append(zip_path)
    return saved


def build_earnings_reel(e, date_iso, outdir):
    """Reel-Teaser (9:16): spiegelt die ersten drei Earnings-Slides (Cover →
    Beat in Zahlen → Kursreaktion) und schließt mit Hybrid-CTA aufs Karussell."""
    saved = []
    emit = _emitter("reel", outdir, saved)
    emit("cover",  lambda c: render.slide_earnings_cover(c, e, date_iso))
    emit("zahlen", lambda c: render.slide_earnings_numbers(c, e, date_iso))
    if e.get("reaction_ohlcv"):
        emit("reaktion", lambda c: render.slide_earnings_reaction(c, e, date_iso))
    emit("cta",    lambda c: render.slide_earnings_reel_cta(c, e, date_iso))
    return saved


def caption_earnings(e):
    """Kurz-Caption für Earnings-Posts. SEO-Zeile: Firmenname + Ticker + 'Earnings'
    zuerst, Emoji danach (Keyword-Signal). Alle Zahlen und Einordnung auf den Slides.
    SEO-Zeile + Beat-Einzeiler + Save-/Folge-CTA + Disclaimer + max. 5 Hashtags."""
    a = e.get("analysis")
    name = render.A.short_name(a["name"]) if a and a.get("name") else e["ticker"]
    beat_word = "Beat" if (e.get("eps_surprise_pct") or 0) >= 0 else "Miss"
    DISC = render.T.DISCLAIMER_ANALYSE_SHORT

    teaser = []
    if e.get("eps_surprise_pct") is not None:
        teaser.append(f"EPS-Überraschung {earn.fmt_pct_pts(e['eps_surprise_pct'], 0)}")
    if e.get("jump_pct") is not None:
        teaser.append(f"Kurssprung {render.fmt_pct(e['jump_pct'])} am Tag der Zahlen")
    parts = [f"{name} ({e['ticker']}) Earnings {e['quarter']}: {beat_word} 📊\n"]
    if teaser:
        parts.append("🚀 " + " · ".join(teaser) + ".\n")
    parts.append("Zahlen, Kursreaktion, Guidance und Einordnung auf den Slides. "
                 "Speichere für deine Watchlist.\n")
    parts.append("👉 Folge AI Alpha Selection für Earnings & Profi-Analysen.\n")
    parts.append("❗ " + DISC)
    parts.append("\n" + hashtags_earnings(e))
    return "\n".join(parts)


def reel_caption_earnings(e):
    """Caption für das Earnings-Reel (eigener IG-Post). Teaser → leitet auf den
    Karussell-Post um. Keyword-first SEO-Zeile + Beat-Einzeiler + Funnel-CTA +
    Disclaimer + max. 5 Hashtags (wie caption_earnings, aber mit Reel-CTA)."""
    a = e.get("analysis")
    name = render.A.short_name(a["name"]) if a and a.get("name") else e["ticker"]
    beat_word = "Beat" if (e.get("eps_surprise_pct") or 0) >= 0 else "Miss"
    DISC = render.T.DISCLAIMER_ANALYSE_SHORT
    teaser = []
    if e.get("eps_surprise_pct") is not None:
        teaser.append(f"EPS-Überraschung {earn.fmt_pct_pts(e['eps_surprise_pct'], 0)}")
    if e.get("jump_pct") is not None:
        teaser.append(f"Kurssprung {render.fmt_pct(e['jump_pct'])} am Tag der Zahlen")
    parts = [f"{name} ({e['ticker']}) Earnings {e['quarter']}: {beat_word} 📊\n"]
    if teaser:
        parts.append("🚀 " + " · ".join(teaser) + ".\n")
    parts.append("🎬 Das ist der Teaser. Zahlen, Kursreaktion und Guidance im "
                 "Karussell-Post auf meinem Profil.\n")
    parts.append("👉 Folge AI Alpha Selection für Earnings & Profi-Analysen.\n")
    parts.append("❗ " + DISC)
    parts.append("\n" + hashtags_earnings(e))
    return "\n".join(parts)


def write_alt_texts(base, saved, meta):
    """Schreibt alt_texts.txt: vorgeschlagene ALT-Texte für jeden Slide.
    Beim manuellen IG-Upload eintragen → Accessibility + Suchalgorithmus.
    Jede Zeile: 'Slide N: <keyword-reicher Text>'."""
    _DESC = {
        # Analyse
        "cover":                "{name} ({ticker}) {kind} — Verdict {verdict} · Score {score}/100",
        "einschaetzung":        "{name} Gesamteinschätzung: Investment-Case und Sterne-Ratings",
        "unternehmen":          "Was macht {name}? Geschäftsmodell und Highlights",
        "szenarien":            "{name} Kursszenarien 12–18 Monate: Bull / Base / Bear mit Eintrittswahrscheinlichkeit",
        "szenarien_erklaert":   "{name} Szenarien erklärt: Treiber für Bull, Base und Bear Case",
        "szenarien_erklaert_1": "{name} Szenarien erklärt (Teil 1): Bull und Base Case Treiber",
        "szenarien_erklaert_2": "{name} Szenarien erklärt (Teil 2): weitere Treiber",
        "szenarien_erklaert_3": "{name} Szenarien erklärt (Teil 3): weitere Treiber",
        "chancen_risiken":      "{name} Chancen und Risiken: Pro und Contra Übersicht",
        "fundamentals":         "{name} Fundamentaldaten: Wachstum, Margen und Kennzahlen",
        "bewertung":            "{name} Bewertung: KGV-Analyse Trailing vs. Forward",
        "risiko":               "{name} Risiko und Realitätscheck: Positionsgröße und Erwartungen",
        "technical":            "{name} Technische Analyse: Chartsignal und Trend",
        "langfrist":            "{name} Langfrist-Kursziele 3–5 Jahre: Szenarien und Spannen",
        "fazit":                "{name} Profi-Fazit und vergleichbare Titel (Peers)",
        "cta":                  "AI Alpha Selection — für Watchlist speichern · wöchentliche Profi-Analysen",
        # Earnings
        "zahlen":               "{name} ({ticker}) {quarter} Quartalszahlen: EPS {eps_actual} vs. Erwartung {eps_estimate}",
        "quartale":             "{name} Bereinigtes EPS je Quartal: Gewinntrend {quarter}",
        "reaktion":             "{name} Kursreaktion am Meldetag: 50 Handelstage Candle-Chart",
        "ausblick":             "{name} Guidance und Wachstumstreiber {quarter}",
        "segmente":             "{name} Was den Beat getragen hat: Segment-Analyse {quarter}",
        "einordnung":           "{name} Einordnung: Was die Zahlen für die These bedeuten · Verdict {verdict}",
        "ratings":              "{name} Qualität auf einen Blick: vier Sterne-Ratings",
        # Weekly
        "hook":                 "AI Alpha Selection Wochenupdate KW {kw} — {hook}",
        "performance":          "Equity-Kurve AI Alpha Selection vs. NASDAQ-100: {total_perf} vs. {nasdaq_total} seit Start",
        "historie":             "Wöchentliche Mehrrendite ggü. NASDAQ-100 seit Portfoliostart",
        "positionen":           "Stärkste Positionen AI Alpha Selection KW {kw}: Top-5 nach Wertzuwachs",
        "weitere":              "Weitere Positionen AI Alpha Selection KW {kw}: alle Titel außerhalb Top-5",
        "warum":                "Strategischer Kontext KW {kw}: warum das KI-Modell diese Woche so entschieden hat",
    }
    m = {
        "kind": "Aktienanalyse", "name": "", "ticker": "", "verdict": "",
        "score": "—", "quarter": "", "eps_actual": "—", "eps_estimate": "—",
        "kw": "", "hook": "", "total_perf": "", "nasdaq_total": "",
    }
    m.update({k: (v if v is not None else "—") for k, v in meta.items()})

    lines = []
    slide_n = 0
    for path in saved:
        fname = os.path.basename(path)
        # Nur Carousel-Slides — Reels werden als Video hochgeladen (kein ALT-Text nötig)
        if not fname.endswith(".png") or os.sep + "reel" + os.sep in path:
            continue
        slide_n += 1
        stem_m = re.match(r"^\d+_(.+)\.png$", fname)
        stem = stem_m.group(1) if stem_m else fname[:-4]

        if stem in _DESC:
            desc = _DESC[stem].format_map(m)
        elif stem.startswith("aktie_"):
            t = stem[6:].replace("_", ".")
            desc = f"Aktie der Woche KW {m['kw']}: {t} — Kursverlauf mit Kauf-Signal"
        elif stem.startswith("newcomer_"):
            t = stem[9:].replace("_", ".")
            desc = f"Newcomer KW {m['kw']}: {t} — bester Kauf der letzten 3 Wochen"
        elif stem.startswith("trade_"):
            t = stem[6:].replace("_", ".")
            desc = f"Trade der Woche KW {m['kw']}: {t} — realisierter Gewinn/Verlust"
        else:
            desc = f"AI Alpha Selection — {stem.replace('_', ' ')}"

        lines.append(f"Slide {slide_n}: {desc}")

    if lines:
        with open(os.path.join(base, "alt_texts.txt"), "w", encoding="utf-8") as f:
            f.write("# ALT-Texte für Instagram-Upload\n"
                    "# Beim manuellen Hochladen pro Slide eintragen "
                    "(Accessibility + Suchalgorithmus)\n\n")
            f.write("\n".join(lines) + "\n")


def build(fmt, ctx, outdir):
    os.makedirs(outdir, exist_ok=True)
    date_iso = ctx["date_iso"]
    saved = []

    def emit(name, draw):
        c = render.Canvas(fmt)
        draw(c)
        path = os.path.join(outdir, name)
        c.save(path)
        saved.append(path)

    emit("01_hook.png", lambda c: render.slide_hook(
        c, date_iso, ctx["wf_ret"], ctx["out_ret"], ctx["period_label"]))
    emit("02_performance.png", lambda c: render.slide_performance(
        c, date_iso, ctx["wf_dates"], ctx["wf_vals"], ctx["nas_dates"],
        ctx["nas_vals"], ctx["wf_ret"], ctx["nas_ret"], ctx["is_sample"]))
    emit("03_kpis.png", lambda c: render.slide_kpis(
        c, date_iso, ctx["wf_ret"], ctx["out_ret"], ctx["n_signals"],
        ctx["n_tickers"], ctx["top_ticker"]))
    for i, (ticker, sig, ret, ohlcv, entry) in enumerate(ctx["signals"], start=4):
        emit(f"{i:02d}_signal_{ticker.replace('.', '_')}.png",
             lambda c, t=ticker, s=sig, r=ret, o=ohlcv, e=entry:
             render.slide_signal(c, date_iso, t, s, r, o, e))
    emit(f"{4 + len(ctx['signals']):02d}_cta.png",
         lambda c: render.slide_cta(c, date_iso))
    return saved


def build_caption(ctx):
    sig_lines = "\n".join(
        f"• {t}: {render.fmt_pct(r)} seit Signal ({render.short_date(e['d'])})"
        for t, s, r, o, e in ctx["signals"] if r is not None)
    return (
        f"📊 AI Alpha Selection — Update {ctx['period_label']}\n\n"
        f"Das wikifolio liegt bei {render.fmt_pct(ctx['wf_ret'])} und schlägt "
        f"den NASDAQ-100 um {render.fmt_pct(ctx['out_ret'])}.\n\n"
        f"Ausgewählte Signale des Systems:\n{sig_lines}\n\n"
        f"Das System kombiniert relative Stärke mit Breakout-Logik und wählt "
        f"datengetrieben aus über {ctx['n_tickers']} beobachteten Titeln.\n\n"
        f"➡️ Mehr Updates: {render.BRAND_NAME} — Link in Bio.\n\n"
        f"{render.T.DISCLAIMER_LONG}\n\n"
        f"{HASHTAGS_WEEKLY}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["carousel", "reel", "both"], default="both")
    ap.add_argument("--signals", type=int, default=2)
    ap.add_argument("--kw", type=int, help="Kalenderwoche – baut den Wochenpost aus instagram/data/")
    ap.add_argument("--report", help="Pfad zu instagram/reports/KW<NN>.json (manueller Modus)")
    ap.add_argument("--analysis", help="Ticker oder Pfad zu analyses/TICKER.md (Analyse-Post)")
    ap.add_argument("--earnings", help="Ticker oder Pfad zu instagram/data/earnings/TICKER.json (Earnings-Post)")
    ap.add_argument("--headline", help="Eigene Cover-Headline (Frage/These) für den Analyse-/Earnings-Post")
    ap.add_argument("--hook", help="Dynamic-Hook-Schlagzeile für Slide 1 (Wochenpost)")
    ap.add_argument("--why", help="Strategisches „Warum“ (KI-Kontext-Slide, Wochenpost)")
    ap.add_argument("--frage", help="Dynamische Interaktions-Frage für die CTA-Slide")
    ap.add_argument("--date", help="Slide-Datum (YYYY-MM-DD). Ohne Angabe: Samstag "
                                   "der KW (bzw. heute, falls dieser Samstag noch "
                                   "in der Zukunft liegt).")
    args = ap.parse_args()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Earnings-Post aus instagram/data/earnings/TICKER.json ─────────────────
    if args.earnings:
        e = earn.load_earnings(args.earnings)
        # Slide-Datum (oben rechts) = standardmäßig der Tag NACH dem Earningscall
        # (so wird der Post immer am Folgetag der Zahlen datiert, auch rückwirkend);
        # ein explizites --date hat Vorrang.
        if args.date:
            date_iso = args.date
        else:
            try:
                from datetime import timedelta
                rd = datetime.strptime(e["report_date"][:10], "%Y-%m-%d").date()
                date_iso = (rd + timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                date_iso = today
        if e.get("analysis") is None:
            print(f"⚠ Keine Basis-Analyse gefunden: analyses/{e['ticker'].lower()}.md")
            print("  Bitte zuerst die Aktienanalyse erzeugen (siehe analyses/PROMPT.md),")
            print("  dann den Earnings-Post bauen. Szenarien/Verdict/Fazit fehlen sonst.")
        if args.headline:
            e["headline"] = args.headline
        slug = e["ticker"].replace(".", "_")
        base = os.path.join(ROOT, "out", "instagram", f"{date_iso}_EARNINGS_{slug}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            if fmt == "reel":
                all_saved += build_earnings_reel(e, date_iso, os.path.join(base, fmt))
            else:
                all_saved += build_earnings(fmt, e, date_iso, os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption_earnings(e))
        if "reel" in fmts:
            with open(os.path.join(base, "reel_caption.txt"), "w", encoding="utf-8") as f:
                f.write(reel_caption_earnings(e))
        _a = e.get("analysis") or {}
        write_alt_texts(base, all_saved, {
            "kind": f"Earnings {e.get('quarter','')}",
            "name": render.A.short_name(_a["name"]) if _a.get("name") else e["ticker"],
            "ticker": e["ticker"],
            "verdict": _a.get("verdict", ""),
            "score": _a.get("score"),
            "quarter": e.get("quarter", ""),
            "eps_actual": e.get("eps_actual", "—"),
            "eps_estimate": e.get("eps_estimate", "—"),
        })

        reel_dir = os.path.join(base, "reel")
        if "reel" in fmts and os.path.isdir(reel_dir):
            frames = sorted(os.path.join(reel_dir, f) for f in os.listdir(reel_dir)
                            if f.endswith(".png"))
            try:
                from . import video
                mp4 = video.build_reel_video(frames, os.path.join(base, "reel.mp4"))
                all_saved.append(mp4)
                print(f"  🎬 Reel-Video: {os.path.relpath(mp4, ROOT)}")
            except Exception as ex:
                print(f"  ⚠ Reel-MP4 übersprungen ({ex.__class__.__name__}: {ex}).")

        jp = e.get("jump_pct")
        print(f"✓ {len(all_saved)} Dateien (Earnings {e['ticker']} {e['quarter']}) in {base}")
        print(f"  EPS-Surprise {earn.fmt_pct_pts(e.get('eps_surprise_pct'),0)} · "
              f"Kurssprung {render.fmt_pct(jp) if jp is not None else '–'} · "
              f"Beat {'ja' if e.get('beat') else 'NEIN'}")
        if not e.get("meets_jump") or not e.get("meets_surprise"):
            print(f"  ⚠ Schwellen-Hinweis: Kurssprung≥5% {e.get('meets_jump')} · "
                  f"EPS-Surprise≥10% {e.get('meets_surprise')} "
                  f"(Post wird trotzdem gebaut)")
        if not render.T.company_logo_file(e["ticker"]):
            print(f"  ⚠ Kein Firmenlogo — Cover nutzt Wortmarke. "
                  f"Logo: instagram/assets/logos/{slug}.png")
        for p in all_saved:
            print("  ", os.path.relpath(p, ROOT))
        return

    # ── Analyse-Post aus analyses/TICKER.md ───────────────────────────────────
    if args.analysis:
        date_iso = args.date or today
        a = ana.parse_analysis(args.analysis)
        if args.headline:
            a["headline"] = args.headline
        slug = a["ticker"].replace(".", "_")
        base = os.path.join(ROOT, "out", "instagram", f"{date_iso}_ANALYSE_{slug}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            if fmt == "reel":
                all_saved += build_analysis_reel(a, date_iso, os.path.join(base, fmt))
            else:
                all_saved += build_analysis(fmt, a, date_iso, os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption_analysis(a))
        if "reel" in fmts:
            with open(os.path.join(base, "reel_caption.txt"), "w", encoding="utf-8") as f:
                f.write(reel_caption_analysis(a))
        write_alt_texts(base, all_saved, {
            "name": render.A.short_name(a["name"]),
            "ticker": a["ticker"],
            "verdict": a.get("verdict", ""),
            "score": a.get("score"),
        })
        # Reel-Skript speichern und cinematic_reel.py direkt aufrufen
        script_txt = reel_script(a)
        script_path = os.path.join(base, "reel_script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_txt)
        print(f"  📄 Reel-Skript: {os.path.relpath(script_path, ROOT)}")

        reel_out = os.path.join(base, "reel.mp4")
        try:
            from . import cinematic_reel
            psych = hook_generator.get_hook(a["ticker"])
            cinematic_reel.render(
                ticker=a["ticker"],
                hook_typ=psych["typ"],
                script_path=script_path,
                output_path=reel_out,
                score=a.get("score"),
                verdict=a.get("verdict"),
                hype_aktie="Nvidia",
            )
            all_saved.append(reel_out)
            print(f"  🎬 Cinematic Reel: {os.path.relpath(reel_out, ROOT)}")
        except Exception as ex:
            print(f"  ⚠ Cinematic Reel übersprungen ({ex.__class__.__name__}: {ex})")

        full = _has_scenarios(a)
        print(f"✓ {len(all_saved)} Dateien (Analyse {a['ticker']}) in {base}")
        print(f"  Verdict {a['verdict']} · Score {a['score']} · "
              f"Szenarien {'ja' if full else 'NEIN (Alt-Schema → reduziert)'}")
        if not render.T.company_logo_file(a["ticker"]):
            print(f"  ⚠ Kein Firmenlogo gefunden — Cover nutzt Wortmarke. "
                  f"Logo ablegen unter instagram/assets/logos/{slug}.png")
        for p in all_saved:
            print("  ", os.path.relpath(p, ROOT))
        return

    universe, benchmark = data.load_universe()

    # ── Wochenmodus aus persistenten Daten (Hauptweg) ─────────────────────────
    if args.kw:
        # Slide-Datum = Samstag der KW (rückwirkend), sonst heute (siehe report.slide_date)
        year = store.load_config().get("year", int(today[:4]))
        date_iso = report.slide_date(year, args.kw, args.date)
        ctx = store.compute(args.kw, universe, benchmark, ref_date=date_iso)
        ctx["date_iso"] = date_iso
        # Dynamische Felder: Claude übergibt sie via CLI; sonst datenbasierter Fallback
        ctx["hook"] = args.hook or auto_hook(ctx)
        ctx["why"] = args.why or auto_why(ctx)
        # Auto-append realized trade returns so all sold tickers always show %
        # Claude schreibt in --why nur den narrativen Text (ohne %-Werte der Trades);
        # die Renditen werden hier automatisch als "Realisiert:"-Zeile angehängt.
        if ctx.get("trades"):
            trade_parts = [f"{t['ticker']} {render.fmt_pct(t['ret'])}"
                           for t in ctx["trades"] if t.get("ret") is not None]
            if trade_parts:
                trade_line = "Realisiert: " + " · ".join(trade_parts)
                if trade_line not in ctx["why"]:
                    ctx["why"] = ctx["why"].rstrip() + "\n\n" + trade_line
        ctx["question"] = args.frage or auto_question(ctx)
        base = os.path.join(ROOT, "out", "instagram", f"{date_iso}_KW{args.kw}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            all_saved += build_from_store(fmt, ctx, os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption_from_store(ctx))
        if "reel" in fmts:
            with open(os.path.join(base, "reel_caption.txt"), "w", encoding="utf-8") as f:
                f.write(reel_caption_from_store(ctx))
        write_alt_texts(base, all_saved, {
            "kind": "Wochenupdate",
            "kw": ctx["kw"],
            "hook": ctx["hook"][:80],
            "total_perf": render.fmt_pct(ctx["total_perf"]),
            "nasdaq_total": render.fmt_pct(ctx["nasdaq_total"]),
        })
        # ZIP der Carousel-PNGs für einfachen Versand / Upload
        import zipfile
        carousel_dir = os.path.join(base, "carousel")
        if os.path.isdir(carousel_dir):
            zip_path = os.path.join(base, f"carousel_KW{args.kw:02d}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in sorted(os.listdir(carousel_dir)):
                    if fname.endswith(".png"):
                        zf.write(os.path.join(carousel_dir, fname), fname)
            all_saved.append(zip_path)
            print(f"  📦 ZIP: {os.path.relpath(zip_path, ROOT)}")
        print(f"✓ {len(all_saved)} Slides (KW{args.kw}) in {base}")
        print(f"  Datum (Slide): {date_iso} · Aktie der Woche: {ctx['featured']['ticker']}")
        for p in all_saved:
            print("  ", os.path.relpath(p, ROOT))
        return

    # ── Wochenmodus (report-getrieben) ────────────────────────────────────────
    if args.report:
        r = report.load_report(args.report)
        date_iso = report.slide_date(r["year"], r["kw"], args.date)
        base = os.path.join(ROOT, "out", "instagram", f"{date_iso}_KW{r['kw']}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            all_saved += build_weekly(fmt, r, benchmark, date_iso,
                                      os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(build_weekly_caption(r))
        write_alt_texts(base, all_saved, {
            "kind": "Wochenupdate", "kw": r["kw"],
            "total_perf": render.fmt_pct(r["total_perf"]),
            "nasdaq_total": render.fmt_pct(r["nasdaq_total"]),
        })
        print(f"✓ {len(all_saved)} Slides (Wochenreport KW{r['kw']}) in {base}")
        for p in all_saved:
            print("  ", os.path.relpath(p, ROOT))
        return

    signals = data.load_signals()
    wf_dates, wf_vals, is_sample, meta = data.load_performance()

    start, end = wf_dates[0], wf_dates[-1]
    wf_ret = wf_vals[-1] / wf_vals[0] - 1.0
    nas_dates, nas_vals = data.benchmark_window(benchmark or [], start, end)
    nas_ret = (nas_vals[-1] / nas_vals[0] - 1.0) if nas_vals else 0.0
    out_ret = wf_ret - nas_ret

    n_signals = sum(1 for sigs in signals.values() for s in sigs
                    if s.get("signal_date", "") >= start)
    n_tickers = len(universe)
    top_ticker = max(universe, key=lambda t: universe[t]["score"] or 0)

    chosen = []
    for ticker, sig in data.recent_signals(signals, universe, limit=args.signals):
        ret, entry, last = data.signal_return(universe, ticker, sig["signal_date"])
        if entry is None:
            continue
        chosen.append((ticker, sig, ret, universe[ticker]["ohlcv"], entry))

    date_iso = args.date or today
    ctx = {
        "date_iso": date_iso,
        "period_label": f"{render.fmt_de_date(start)} – {render.fmt_de_date(end)}",
        "wf_dates": wf_dates, "wf_vals": wf_vals, "is_sample": is_sample,
        "nas_dates": nas_dates, "nas_vals": nas_vals,
        "wf_ret": wf_ret, "nas_ret": nas_ret, "out_ret": out_ret,
        "n_signals": n_signals, "n_tickers": n_tickers, "top_ticker": top_ticker,
        "signals": chosen,
    }

    base = os.path.join(ROOT, "out", "instagram", date_iso)
    fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
    all_saved = []
    for fmt in fmts:
        all_saved += build(fmt, ctx, os.path.join(base, fmt))

    with open(os.path.join(base, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(build_caption(ctx))

    print(f"✓ {len(all_saved)} Slides erzeugt in {base}")
    if is_sample:
        print("⚠ Wikifolio-Performance = BEISPIELDATEN "
              "(data/wikifolio_performance.json fehlt).")
    for p in all_saved:
        print("  ", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()

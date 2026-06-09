"""
AI Alpha Selections — Instagram-Generator (Prototyp)

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
from datetime import datetime

from . import data, render, report, store
from . import analysis as ana
from . import earnings as earn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pos_sub(t):
    s = t.get("name", "")
    if t.get("buy_date"):
        s += f" · Kauf {render.fmt_de_date(t['buy_date'])}"
    if t.get("buy_price_eur"):
        s += f" · {t['buy_price_eur']:.2f}".replace(".", ",") + " €"
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
    # 4) Stärkste Positionen (Top-5, mit Kaufdatum + Kaufpreis)
    if ctx["top_holdings"]:
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]) if t["ret"] is not None else "—",
                 "color": (render.T.GREEN if t["ret"] >= 0 else render.T.RED)
                          if t["ret"] is not None else render.T.SUBTLE,
                 "value_font": "mono" if t["ret"] is not None else "sans"}
                for t in ctx["top_holdings"]]
        emit("positionen", lambda c: render.slide_list(
            c, di, "Stärkste Positionen", "Wertzuwachs seit Kauf", rows))
    # 5) Aktie der Woche (Rotation) — vor warum für besseren Lesefluss
    if ctx["featured"]["entry"]:
        emit(f"aktie_{ctx['featured']['ticker'].replace('.', '_')}",
             lambda c: render.slide_featured(c, di, ctx["featured"]))
    # 6) Weitere Positionen (alle außerhalb der Top-5) — vor warum
    if ctx.get("rest_holdings"):
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]) if t["ret"] is not None else "—",
                 "color": (render.T.GREEN if t["ret"] >= 0 else render.T.RED)
                          if t["ret"] is not None else render.T.SUBTLE,
                 "value_font": "mono" if t["ret"] is not None else "sans"}
                for t in ctx["rest_holdings"]]
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
    top = "\n".join(f"• {t['ticker']} ({t.get('name','')}): "
                    + (render.fmt_pct(t["ret"]) if t["ret"] is not None else "—")
                    for t in ctx["top_holdings"][:5])
    s = ctx["stats"]
    pf = "∞" if s["profit_factor"] is None else f"{s['profit_factor']:.1f}".replace(".", ",")
    f = ctx["featured"]
    feat = (f"\n🔎 Aktie der Woche: {f['ticker']} – seit Kauf {render.fmt_pct(f['ret'])}."
            if f.get("ret") is not None else "")
    nc = ctx.get("newcomer")
    newc = (f"\n🆕 Newcomer: {nc['ticker']} – {render.fmt_pct(nc['ret'])} seit Kauf."
            if nc and nc.get("ret") is not None else "")
    why = f"\n🤖 Hinter den Kulissen: {ctx['why']}\n" if ctx.get("why") else ""
    return (
        f"📊 {ctx['hook']}\n\n"
        f"Wochenupdate KW {ctx['kw']} ({ctx['period']})\n"
        f"Diese Woche: {render.fmt_pct(ctx['week_perf'])} | "
        f"NASDAQ-100: {render.fmt_pct(ctx['nasdaq_week'])}\n"
        f"Gesamtrendite seit Start: {render.fmt_pct(ctx['total_perf'])} | "
        f"NASDAQ: {render.fmt_pct(ctx['nasdaq_total'])} | "
        f"Alpha: {render.fmt_pct(ctx['alpha'])}\n"
        f"{ctx['weeks_beaten']} von {ctx['weeks_total']} Wochen den NASDAQ geschlagen.\n"
        f"Trades: {s['trades']} · Trefferquote {round(s['win_rate']*100)} % · "
        f"Profitfaktor {pf} · Ø Gewinn {render.fmt_pct(s['avg_win'])} · "
        f"Ø Verlust {render.fmt_pct(s['avg_loss'])}\n\n"
        f"Stärkste Positionen (Zuwachs seit Kauf):\n{top}\n"
        f"{feat}{newc}\n"
        f"{why}\n"
        f"👉 Den Link zum Live-Depot findest du aktuell in unserer Bio! {ctx['account']}\n\n"
        f"💬 {ctx['question']}\n\n"
        f"{render.T.DISCLAIMER_LONG}\n\n"
        f"#wikifolio #aktien #investing #nasdaq #trading #boerse "
        f"#geldanlage #finanzen #relativestärke #wochenupdate"
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
        f"📊 Wochenreport KW {r['kw']} ({r['period']})\n",
        f"Musterdepot diese Woche: {render.fmt_pct(r['week_perf'])} | "
        f"NASDAQ-100: {render.fmt_pct(r['nasdaq_week'])}",
        f"Gesamtrendite seit Start: {render.fmt_pct(r['total_perf'])} | "
        f"NASDAQ: {render.fmt_pct(r['nasdaq_total'])} | "
        f"Alpha: {render.fmt_pct(r['alpha'])}",
        f"{r['weeks_beaten']} von {r['weeks_total']} Wochen den NASDAQ geschlagen.\n",
    ]
    if r["buys"]:
        parts.append("Käufe:\n" + line_buys() + "\n")
    if r["sells"]:
        parts.append("Verkäufe:\n" + line_sells() + "\n")
    parts.append(f"➡️ Mehr: {render.HANDLE}\n")
    parts.append(render.T.DISCLAIMER_LONG)
    parts.append("\n#wikifolio #aktien #investing #nasdaq #trading #boerse "
                 "#geldanlage #finanzen #relativestärke #wochenreport")
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

    L = []
    L.append("# REEL-SCRIPT — " + f"{name} ({t})")
    L.append("# Format 9:16 · ~45 Sek · faceless · für InVideo AI / Google Veo / "
             "CapCut Script-to-Video")
    L.append("")
    L.append("## [AI-GENERATOR-PROMPT]")
    L.append(
        f"\"Erstelle ein düsteres, hochprofessionelles Finanz-Reel für Instagram "
        f"im Format 9:16. Schnelle, dynamische Schnitte alle ~1,5 Sekunden. "
        f"Visueller Stil: minimalistisch, cineastisch, High-Tech, dunkler "
        f"Hintergrund mit blauen/cyan Akzenten. B-Roll: {broll}. Stimme: tiefe, "
        f"professionelle, charismatische deutsche Männerstimme (KI). Musik: "
        f"subtiler, rhythmischer, dramatischer Tech-Beat. Untertitel groß, fett, "
        f"zentriert, synchron zum Voiceover aufpoppend.\"")
    L.append("")
    L.append("## [SCRIPT]")
    L.append(f"[0:00–0:05]  (Overlay: {t} — {a['verdict']})")
    L.append(f"VO: \"{headline} {a.get('hook','')}\"")
    L.append("")
    if misconception:
        L.append(f"[0:05–0:13]  (Overlay: KGV {pe['trailing']}x = irreführend)")
        L.append(f"VO: \"{misconception}\"")
        L.append("")
    core = ana.clean_for_slide(a["sections"].get(1, ""))
    csents = ana.sentences(core)
    core_vo = " ".join(csents[1:3]).strip() if len(csents) > 1 else core
    if core_vo:
        L.append("[0:13–0:23]  (Overlay: Der Kern)")
        L.append(f"VO: \"{core_vo}\"")
        L.append("")
    if bear:
        L.append("[0:23–0:33]  (Overlay: Das größte Risiko)")
        L.append(f"VO: \"Das Hauptrisiko: {bear}\"")
        L.append("")
    if _has_scenarios(a):
        L.append("[0:33–0:40]  (Overlay: Szenarien & Kursziele)")
        L.append(f"VO: \"Drei Szenarien auf 12 bis 18 Monate: Bull "
                 f"{sc['bull']['prob']} Prozent, Base {sc['base']['prob']} Prozent, "
                 f"Bear {sc['bear']['prob']} Prozent — Kursziele {targets}.\"")
        L.append("")
    L.append("[0:40–0:45]  (Overlay: Ganze Analyse im Karussell 👆)")
    L.append(f"VO: \"Den kompletten Deep Dive mit allen Kurszielen findest du im "
             f"Karussell-Post auf diesem Profil. Folge {render.HANDLE} für 1–2 "
             f"Profi-Analysen pro Woche.\"")
    L.append("")
    L.append("## [HINWEIS]  Pflicht-Disclaimer einblenden/vorlesen:")
    L.append("Keine Anlageberatung · KI-generierte Analyse · Kursziele sind "
             "Szenarien, keine Prognosen.")
    return "\n".join(L)


def caption_analysis(a):
    """Instagram-Caption als inhaltliche Ergänzung zu den Slides.
    Die 'Weitere Details' (EPYC/Intel, TSMC, HBM, D/E, Analyst) sind
    exklusiver Caption-Content — nicht auf den Slides sichtbar.
    Hashtags: 25-30 Tags für maximale Algorithmus-Reichweite.
    Instagram-Limit 2.200 Zeichen wird beachtet (notfalls Kürzung)."""
    import re as _re
    v = a["verdict"]
    scal = (f" · Score {a['score']}/100" if a["score"] is not None else "")
    head = f"{a['name']} ({a['ticker']}) — Aktienanalyse: {v}{scal}"
    star = lambda n: ("★" * (n or 0)) + ("☆" * (5 - (n or 0)))
    rt = a["ratings"]
    DISC = ("Keine Anlageberatung. Analysen auf Basis öffentlicher Daten. "
            "Kursziele sind Szenarien, keine Prognosen. Kapitalanlagen bergen "
            "Verlustrisiken bis zum Totalverlust.")

    # ── Hashtags: ausführlich, 25–30 Tags ────────────────────────────────────
    tic = a["ticker"].replace(".", "").lower()
    sector_tags = {
        "Technology": "#halbleiter #semiconductor #chips #technologieaktien #techaktien",
        "Healthcare": "#healthcare #pharmaaktien #biotech #gesundheit",
        "Industrials": "#industrie #industrieaktien #infrastruktur",
        "Energy": "#energie #energieaktien #erneuerbar",
        "Financial Services": "#finanzsektor #banken #versicherung",
        "Consumer Cyclical": "#konsumaktien #einzelhandel #konsum",
    }.get(a.get("sector", ""), "#technologieaktien")

    biz_text = " ".join(a.get("business_bullets", []) + [a.get("hook", "")])
    topic_parts = []
    if any(w in biz_text for w in ("GPU", "KI", "AI", "Instinct", "Datacenter")):
        topic_parts.append("#ki #aistock #aiinvesting #datacenter #gpu #aiinfrastructure")
    if any(w in biz_text for w in ("EPYC", "CPU", "Server")):
        topic_parts.append("#cpu #serverchips")
    # Vergleichsticker — zieht Suchanfragen ähnlicher Aktien
    peers = a.get("peers", [])
    peer_tags = " ".join(f"#{p.replace('.','').lower()}"
                         for p in peers[:2] if len(p) <= 6)

    tags = (
        f"#aktien #aktienanalyse #aktienmarkt #börse #boersewissen "
        f"#geldanlage #finanzbildung #vermögensaufbau #wachstumsaktien "
        f"#börsentipps #investing #stockanalysis "
        f"#{tic} #{''.join([tic, 'stock'])} {sector_tags} "
        + " ".join(topic_parts)
        + (f" {peer_tags}" if peer_tags else "")
        + " #aialphaselection"
    ).rstrip()

    # ── "Weitere Details"-Block — immer vollständig, nie weglassen ───────────
    sec2 = ana.clean_for_slide(a["sections"].get(2, ""))
    sec3 = ana.clean_for_slide(a["sections"].get(3, ""))
    sec6 = ana.clean_for_slide(a["sections"].get(6, ""))
    sec7 = ana.clean_for_slide(a["sections"].get(7, ""))

    extra = []
    # EPYC vs. Intel (aus Section 3 oder Section 2)
    if _re.search(r'EPYC|Intel', sec2 + sec3, _re.I):
        extra.append("EPYC vs. Intel: AMD gewinnt im Rechenzentrum-CPU-Markt "
                     "kontinuierlich Marktanteile — profitabler Cashflow-Sockel "
                     "der GPU-Wette")
    # TSMC-Fabless (immer wenn vorhanden — auch wenn in Bullets)
    if _re.search(r'TSMC|Fabless', sec2, _re.I):
        extra.append("TSMC-Abhängigkeit: Fabless-Modell = volle Abhängigkeit "
                     "von TSMC-Kapazität (3nm/5nm) + CoWoS-HBM-Packaging")
    # HBM-Risiko (immer wenn vorhanden)
    if _re.search(r'HBM', sec2, _re.I):
        extra.append("HBM-Risiko: MI-GPUs benötigen HBM3e von SK Hynix/Samsung "
                     "— Lieferkette ist kritischer Engpass bei hoher AI-Nachfrage")
    # D/E aus Section 6
    m_de = _re.search(r'D/E[^0-9]*([0-9]+(?:[,\.][0-9]+)?)', sec6)
    if m_de:
        extra.append(f"Bilanz: D/E {m_de.group(1)} — konservative Verschuldung, "
                     f"solide Bilanz, ~7 Mrd. $ FCF (2024)")
    # Analyst-Konsensus aus Section 7
    m_ac = _re.search(
        r'(?:[Kk]onsensus|[Kk]onsensziel|[Aa]nalysten)[^0-9$]*\$?\s*([0-9]{2,}(?:[.,][0-9]+)?)',
        sec7)
    if m_ac:
        extra.append(f"Analyst-Konsensus: {m_ac.group(1).rstrip('.')} $ Kursziel "
                     f"— Analysten laufen der Kursrally aktuell hinterher")

    def assemble(biz_n, with_longterm, with_cases):
        parts = [f"📊 {head}\n"]
        if a.get("hook"):
            parts.append(a["hook"] + "\n")
        if a.get("business_bullets") and biz_n:
            bl = "\n".join(f"› {b}" for b in a["business_bullets"][:biz_n])
            parts.append("🏭 Das Unternehmen:\n" + bl + "\n")
        if _has_scenarios(a):
            sc = a["scenarios"]
            emo = {"bull": "🟢", "base": "🔵", "bear": "🔴"}
            lines = []
            for key, name in (("bull", "Bull"), ("base", "Base"), ("bear", "Bear")):
                prob = sc[key]["prob"]
                rng = ana.fmt_range(sc[key]["range"])
                seg = f"{emo[key]} {name} {prob}%" if prob is not None else f"{emo[key]} {name}"
                if rng:
                    seg += f" · Ziel {rng}"
                if with_cases and sc[key]["summary"]:
                    seg += f"\n   {sc[key]['summary']}"
                lines.append(seg)
            parts.append("🎯 Szenarien · 12–18 Monate (= 100 %):\n"
                         + "\n".join(lines) + "\n")
            if with_longterm and _has_longterm(a):
                lt = a["longterm"]
                lts = " · ".join(f"{n} {ana.fmt_range(lt[k])}"
                                 for k, n in (("bull", "Bull"), ("base", "Base"),
                                              ("bear", "Bear")) if ana.fmt_range(lt[k]))
                parts.append("🔭 Langfristig · 3–5 Jahre: " + lts + "\n")
        elif a.get("pro_bullets") or a.get("con_bullets"):
            if a.get("pro_bullets"):
                parts.append("🟢 Chancen:\n" + "\n".join(
                    f"› {b}" for b in a["pro_bullets"][:biz_n or 3]) + "\n")
            if a.get("con_bullets"):
                parts.append("🔴 Risiken:\n" + "\n".join(
                    f"› {b}" for b in a["con_bullets"][:biz_n or 3]) + "\n")
        if any(rt.values()):
            parts.append(f"⭐ Rating: Qualität {star(rt.get('Qualität'))} · "
                         f"Wachstum {star(rt.get('Wachstum'))} · "
                         f"Bewertung {star(rt.get('Bewertung'))} · "
                         f"Katalysator {star(rt.get('Katalysator'))}\n")
        if a.get("fazit_core"):
            parts.append("🧭 Fazit: " + a["fazit_core"] + "\n")
        if a.get("peers"):
            parts.append("📌 Vergleichbar: " + ", ".join(a["peers"]) + "\n")
        # Weitere Details — caption-exklusiver Content, immer vollständig
        if extra:
            parts.append("💡 Nicht auf den Slides:\n"
                         + "\n".join(f"› {e}" for e in extra) + "\n")
        parts.append("👉 Folge für wöchentliche Analysen.\n")
        parts.append("❗ " + DISC)
        parts.append("\n" + tags)
        return "\n".join(parts)

    # Schrittweise kürzen (Bullets → Cases → Longterm); Weitere Details bleiben immer
    for biz_n, lt, cases in ((4, True, True), (4, True, False), (3, True, False),
                             (3, False, False), (2, False, False), (0, False, False)):
        cap = assemble(biz_n, lt, cases)
        if len(cap) <= 2200:
            return cap
    return assemble(0, False, False)[:2180].rsplit(" ", 1)[0] + " …"


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
    """Instagram-Caption für den Earnings-Post. SEO: erste Zeile mit Keyword
    'Earnings-Analyse'. Beat-Zahlen + Guidance + These + Disclaimer + Hashtags,
    auf 2.200 Zeichen zugeschnitten."""
    a = e.get("analysis")
    cur = e.get("currency", "")
    name = render.A.short_name(a["name"]) if a and a.get("name") else e["ticker"]
    tic = e["ticker"].replace(".", "").lower()
    beat_word = "Beat" if (e.get("eps_surprise_pct") or 0) >= 0 else "Miss"
    head = f"{name} ({e['ticker']}) — Earnings-Analyse {e['quarter']}: {beat_word}"

    DISC = render.T.DISCLAIMER_ANALYSE_SHORT
    sector_tags = {
        "Technology": "#halbleiter #technologieaktien #techaktien",
        "Healthcare": "#healthcare #pharmaaktien #gesundheit #medicaid",
        "Industrials": "#industrie #industrieaktien",
        "Energy": "#energie #energieaktien",
        "Financial Services": "#finanzsektor #banken #versicherung",
    }.get((a or {}).get("sector", ""), "")
    tags = (
        f"#earnings #quartalszahlen #earningsseason #aktien #aktienanalyse "
        f"#börse #boersewissen #geldanlage #finanzbildung #investing "
        f"#stockanalysis #turnaround #{tic} #{tic}stock {sector_tags} "
        f"#aialphaselection"
    ).rstrip()

    def assemble(with_context, with_cases, with_drivers):
        P = [f"📊 {head}\n"]
        # Beat-Zahlen
        beat = []
        if e.get("eps_actual") is not None:
            beat.append(f"› EPS {cur}{earn.fmt_num(e['eps_actual'])} vs. "
                        f"{cur}{earn.fmt_num(e.get('eps_estimate'))} erwartet "
                        f"({earn.fmt_pct_pts(e.get('eps_surprise_pct'), 0)})")
        if e.get("revenue_actual") is not None:
            # revenue_unit ('Mrd. $') trägt bereits die Währung → kein cur-Präfix
            beat.append(f"› Umsatz {earn.fmt_num(e['revenue_actual'])} "
                        f"{e.get('revenue_unit','')} vs. "
                        f"{earn.fmt_num(e.get('revenue_estimate'))} erwartet "
                        f"({earn.fmt_pct_pts(e.get('revenue_surprise_pct'), 1)})")
        if e.get("jump_pct") is not None:
            beat.append(f"› Kurssprung {render.fmt_pct(e['jump_pct'])} am Tag der Zahlen")
        if beat:
            P.append("🚀 Die Zahlen:\n" + "\n".join(beat) + "\n")
        if e.get("guidance"):
            P.append("🎯 Ausblick: " + e["guidance"] + "\n")
        if e.get("key_metric_value"):
            P.append(f"🔑 {e['key_metric_label']}: {e['key_metric_value']} "
                     f"— {e.get('key_metric_note','')}".rstrip(" —") + "\n")
        if with_drivers and e.get("drivers"):
            P.append("📌 Treiber:\n" + "\n".join(
                f"› {d}" for d in e["drivers"][:3]) + "\n")
        if with_context and e.get("context"):
            P.append("🧭 Einordnung: " + e["context"] + "\n")
        # Investment-These aus der Basis-Analyse
        if a:
            if a.get("verdict"):
                scal = f" · Score {a['score']}/100" if a.get("score") is not None else ""
                P.append(f"⚖️ KI-Verdict: {a['verdict']}{scal}\n")
            if _has_scenarios(a) and with_cases:
                sc = a["scenarios"]
                emo = {"bull": "🟢", "base": "🔵", "bear": "🔴"}
                lines = []
                for key, nm in (("bull", "Bull"), ("base", "Base"), ("bear", "Bear")):
                    prob = sc[key]["prob"]
                    rng = ana.fmt_range(sc[key]["range"])
                    seg = f"{emo[key]} {nm} {prob}%" if prob is not None else f"{emo[key]} {nm}"
                    if rng:
                        seg += f" · Ziel {rng}"
                    lines.append(seg)
                P.append("📈 Szenarien · 12–18 Monate:\n" + "\n".join(lines) + "\n")
            if a.get("fazit_core"):
                P.append("💡 Fazit: " + a["fazit_core"] + "\n")
        P.append("👉 Ganze Analyse im Karussell. Folge für Earnings & Analysen.\n")
        P.append("❗ " + DISC)
        P.append("\n" + tags)
        return "\n".join(P)

    for ctx_, cases, drv in ((True, True, True), (True, True, False),
                             (False, True, False), (False, False, False)):
        cap = assemble(ctx_, cases, drv)
        if len(cap) <= 2200:
            return cap
    return assemble(False, False, False)[:2180].rsplit(" ", 1)[0] + " …"


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
        f"📊 AI Alpha Selections — Update {ctx['period_label']}\n\n"
        f"Das wikifolio liegt bei {render.fmt_pct(ctx['wf_ret'])} und schlägt "
        f"den NASDAQ-100 um {render.fmt_pct(ctx['out_ret'])}.\n\n"
        f"Ausgewählte Signale des Systems:\n{sig_lines}\n\n"
        f"Das System kombiniert relative Stärke mit Breakout-Logik und wählt "
        f"datengetrieben aus über {ctx['n_tickers']} beobachteten Titeln.\n\n"
        f"➡️ Mehr Updates: {render.HANDLE} — Link in Bio.\n\n"
        f"{render.T.DISCLAIMER_LONG}\n\n"
        f"#wikifolio #aktien #investing #nasdaq #trading #boerse "
        f"#geldanlage #finanzen #relativestärke #aktienanalyse"
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
    today = datetime.utcnow().strftime("%Y-%m-%d")

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
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(caption_earnings(e))

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
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(caption_analysis(a))
        with open(os.path.join(base, "reel_script.txt"), "w") as f:
            f.write(reel_script(a))

        # Einfache Reel-MP4 aus den 9:16-Frames (ffmpeg via imageio-ffmpeg)
        reel_dir = os.path.join(base, "reel")
        if "reel" in fmts and os.path.isdir(reel_dir):
            frames = sorted(os.path.join(reel_dir, f) for f in os.listdir(reel_dir)
                            if f.endswith(".png"))
            try:
                from . import video
                mp4 = video.build_reel_video(frames, os.path.join(base, "reel.mp4"))
                all_saved.append(mp4)
                print(f"  🎬 Reel-Video: {os.path.relpath(mp4, ROOT)}")
            except Exception as e:
                print(f"  ⚠ Reel-MP4 übersprungen ({e.__class__.__name__}: {e}). "
                      f"pip install imageio imageio-ffmpeg")

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
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(caption_from_store(ctx))
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
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(build_weekly_caption(r))
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

    with open(os.path.join(base, "caption.txt"), "w") as f:
        f.write(build_caption(ctx))

    print(f"✓ {len(all_saved)} Slides erzeugt in {base}")
    if is_sample:
        print("⚠ Wikifolio-Performance = BEISPIELDATEN "
              "(data/wikifolio_performance.json fehlt).")
    for p in all_saved:
        print("  ", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()

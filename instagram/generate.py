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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pos_sub(t):
    s = t.get("name", "")
    if t.get("buy_date"):
        s += f" · Kauf {render.fmt_de_date(t['buy_date'])}"
    if t.get("buy_price_eur"):
        s += f" · {t['buy_price_eur']:.2f}".replace(".", ",") + " €"
    return s


def build_from_store(fmt, ctx, outdir):
    """Wochen-Carousel aus den persistenten Daten (store.compute)."""
    saved = []
    emit = _emitter(fmt, outdir, saved)
    di = ctx["date_iso"]

    # 1) Performance (Eye-Catcher) inkl. Kennzahlen unter dem Graph
    emit("performance", lambda c: render.slide_performance(
        c, di, ctx["eq_dates"], ctx["eq_vals"], ctx["nas_dates"], ctx["nas_vals"],
        ctx["total_perf"], ctx["nasdaq_total"], False, stats=ctx["stats"]))
    # 2) Wochen-Historie (Mehrrendite ggü. NASDAQ)
    emit("historie", lambda c: render.slide_history(c, di, ctx["history"]))
    # 3) Stärkste Positionen (Top-5, mit Kaufdatum + Kaufpreis)
    if ctx["top_holdings"]:
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]),
                 "color": render.T.GREEN if t["ret"] >= 0 else render.T.RED}
                for t in ctx["top_holdings"]]
        emit("positionen", lambda c: render.slide_list(
            c, di, "Stärkste Positionen", "Wertzuwachs seit Kauf", rows))
    # 4) Aktie der Woche (Rotation)
    if ctx["featured"]["entry"]:
        emit(f"aktie_{ctx['featured']['ticker'].replace('.', '_')}",
             lambda c: render.slide_featured(c, di, ctx["featured"]))
    # 4b) Weitere Positionen (alle außerhalb der Top-5)
    if ctx.get("rest_holdings"):
        rows = [{"main": t["ticker"], "sub": _pos_sub(t),
                 "value": render.fmt_pct(t["ret"]),
                 "color": render.T.GREEN if t["ret"] >= 0 else render.T.RED}
                for t in ctx["rest_holdings"]]
        emit("weitere", lambda c: render.slide_list(
            c, di, "Weitere Positionen", "Wertzuwachs seit Kauf", rows))
    # 5) Newcomer (bester Kauf der letzten 3 Wochen, nicht in Top-5)
    if ctx.get("newcomer") and ctx["newcomer"]["entry"]:
        emit(f"newcomer_{ctx['newcomer']['ticker'].replace('.', '_')}",
             lambda c: render.slide_featured(c, di, ctx["newcomer"], label="NEWCOMER"))
    # 6) CTA + Risikohinweis
    emit("cta", lambda c: render.slide_cta(c, di))
    return saved


def caption_from_store(ctx):
    top = "\n".join(f"• {t['ticker']} ({t.get('name','')}): {render.fmt_pct(t['ret'])}"
                    for t in ctx["top_holdings"][:5])
    s = ctx["stats"]
    pf = "∞" if s["profit_factor"] is None else f"{s['profit_factor']:.1f}".replace(".", ",")
    f = ctx["featured"]
    feat = (f"\n🔎 Aktie der Woche: {f['ticker']} – seit Kauf {render.fmt_pct(f['ret'])}."
            if f.get("ret") is not None else "")
    nc = ctx.get("newcomer")
    newc = (f"\n🆕 Newcomer: {nc['ticker']} – {render.fmt_pct(nc['ret'])} seit Kauf."
            if nc and nc.get("ret") is not None else "")
    return (
        f"📊 Wochenupdate KW {ctx['kw']} ({ctx['period']})\n\n"
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
        f"{feat}{newc}\n\n"
        f"➡️ Mehr: {ctx['account']}\n\n"
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

    emit("cover", lambda c: render.slide_analysis_cover(c, a, date_iso))
    emit("einschaetzung", lambda c: render.slide_analysis_verdict(c, a, date_iso))
    if _has_scenarios(a):
        emit("szenarien", lambda c: render.slide_analysis_scenarios(c, a, date_iso))
    if _has_longterm(a):
        emit("langfrist", lambda c: render.slide_analysis_longterm(c, a, date_iso))
    if a.get("business_bullets"):
        emit("unternehmen", lambda c: render.slide_analysis_business(c, a, date_iso))
    if _has_scenarios(a):
        emit("szenarien_erklaert", lambda c: render.slide_analysis_cases(c, a, date_iso))
    emit("fazit", lambda c: render.slide_analysis_fazit(c, a, date_iso))
    return saved


def caption_analysis(a):
    v = a["verdict"]
    lab = render.VERDICT_LABEL.get((v or "").upper(), v)
    scal = (f" · Score {a['score']}/100" if a["score"] is not None else "")
    head = f"{a['name']} ({a['ticker']}) — Aktienanalyse: {v}{scal}"

    parts = [f"📊 {head}\n"]
    if a.get("hook"):
        parts.append(a["hook"] + "\n")

    if _has_scenarios(a):
        sc = a["scenarios"]
        lines = []
        for key, name in (("bull", "Bull"), ("base", "Base"), ("bear", "Bear")):
            prob = sc[key]["prob"]
            rng = ana.fmt_range(sc[key]["range"])
            seg = f"• {name}: {prob}%" if prob is not None else f"• {name}:"
            if rng:
                seg += f" · Kursziel {rng}"
            lines.append(seg)
        parts.append("🎯 Szenarien (12–18 Monate):\n" + "\n".join(lines) + "\n")

    if a.get("business_bullets"):
        bl = "\n".join(f"• {b}" for b in a["business_bullets"][:4])
        parts.append("🏭 Geschäftsmodell:\n" + bl + "\n")

    if a.get("fazit_core"):
        parts.append("🧭 Profi-Fazit:\n" + a["fazit_core"] + "\n")

    if a.get("peers"):
        parts.append("📌 Vergleichbar: " + ", ".join(a["peers"]) + "\n")

    parts.append(f"➡️ Mehr Analysen: {render.HANDLE} — Link in Bio.\n")
    parts.append(render.T.DISCLAIMER_ANALYSE_LONG)

    sector_tag = {
        "Technology": "#technologie #tech", "Healthcare": "#healthcare #pharma",
        "Industrials": "#industrie", "Energy": "#energie",
        "Financial Services": "#finanzen", "Consumer Cyclical": "#konsum",
    }.get(a.get("sector", ""), "")
    tic = a["ticker"].replace(".", "").lower()
    parts.append(
        f"\n#aktien #aktienanalyse #börse #investing #{tic} #boersewissen "
        f"#geldanlage #finanzen #stockanalysis #aialphaselection {sector_tag}".rstrip())
    return "\n".join(parts)


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
    ap.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    # ── Analyse-Post aus analyses/TICKER.md ───────────────────────────────────
    if args.analysis:
        a = ana.parse_analysis(args.analysis)
        slug = a["ticker"].replace(".", "_")
        base = os.path.join(ROOT, "out", "instagram", f"{args.date}_ANALYSE_{slug}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            all_saved += build_analysis(fmt, a, args.date, os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(caption_analysis(a))
        full = _has_scenarios(a)
        print(f"✓ {len(all_saved)} Slides (Analyse {a['ticker']}) in {base}")
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
        ctx = store.compute(args.kw, universe, benchmark, ref_date=args.date)
        ctx["date_iso"] = args.date
        base = os.path.join(ROOT, "out", "instagram", f"{args.date}_KW{args.kw}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            all_saved += build_from_store(fmt, ctx, os.path.join(base, fmt))
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "caption.txt"), "w") as f:
            f.write(caption_from_store(ctx))
        print(f"✓ {len(all_saved)} Slides (KW{args.kw}) in {base}")
        print(f"  Aktie der Woche: {ctx['featured']['ticker']}")
        for p in all_saved:
            print("  ", os.path.relpath(p, ROOT))
        return

    # ── Wochenmodus (report-getrieben) ────────────────────────────────────────
    if args.report:
        r = report.load_report(args.report)
        base = os.path.join(ROOT, "out", "instagram", f"{args.date}_KW{r['kw']}")
        fmts = ["carousel", "reel"] if args.format == "both" else [args.format]
        all_saved = []
        for fmt in fmts:
            all_saved += build_weekly(fmt, r, benchmark, args.date,
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

    ctx = {
        "date_iso": args.date,
        "period_label": f"{render.fmt_de_date(start)} – {render.fmt_de_date(end)}",
        "wf_dates": wf_dates, "wf_vals": wf_vals, "is_sample": is_sample,
        "nas_dates": nas_dates, "nas_vals": nas_vals,
        "wf_ret": wf_ret, "nas_ret": nas_ret, "out_ret": out_ret,
        "n_signals": n_signals, "n_tickers": n_tickers, "top_ticker": top_ticker,
        "signals": chosen,
    }

    base = os.path.join(ROOT, "out", "instagram", args.date)
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

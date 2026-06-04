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

from . import data, render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    ap.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    universe, benchmark = data.load_universe()
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

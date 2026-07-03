"""
backtest_v2/run.py — CLI: führt den Portfolio-Backtest aus und schreibt einen
Report nach backtest_v2/results/.

Nutzung: python3 backtest_v2/run.py [market]   (Default: nasdaq)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT / "backtest_v2"))

from engine import run_backtest                    # noqa: E402
from metrics import (                               # noqa: E402
    equity_curve_stats, trade_stats, exposure_pct, benchmark_alpha, sma_rule_return,
)

MARKET_FILES = {
    "nasdaq": "rs_full.json", "sp500": "rs_sp500.json",
    "dax": "rs_dax.json", "smallcap": "rs_smallcap.json",
}

DISCLAIMER = """\
BEKANNTE EINSCHRÄNKUNGEN DIESES LAUFS (siehe backtest_v2/engine.py Docstring):
- Survivorship-Bias: aktuelles Universum rückwirkend gehandelt (Regel B3 offen)
- Nur ~2 Jahre synchronisierte Historie verfügbar — keine 2016-2021-Trainings-
  periode, kein echter Bärenmarkt-Test wie 2022 (Regeln B4/B5 offen)
- Kein 4H im historischen Walk (Regel B9) — Entry verlangt Weekly+Daily (2/2)
- Fundamentaldaten sind ein aktueller Snapshot, nicht point-in-time
Dieser Report ist ein Smoke-/Validierungslauf der Engine-Architektur,
KEINE abgeschlossene Strategie-Kalibrierung."""


def regime_breakdown(result):
    by_regime = {}
    equity_by_date = dict(result["equity_curve"])
    dates = [d for d, _ in result["equity_curve"]]
    for i, (day, label, _n) in enumerate(result["regime_by_day"]):
        if label is None:
            continue
        by_regime.setdefault(label, {"days": 0, "start_equity": None, "end_equity": None})
        by_regime[label]["days"] += 1
        eq = equity_by_date[day]
        if by_regime[label]["start_equity"] is None:
            by_regime[label]["start_equity"] = eq
        by_regime[label]["end_equity"] = eq
    out = {}
    for label, v in by_regime.items():
        ret = (v["end_equity"] / v["start_equity"] - 1) * 100 if v["start_equity"] else None
        out[label] = {"days": v["days"], "return_pct_while_active": round(ret, 2) if ret is not None else None}
    return out


def run_for_cost(market, cost_pct, raw, fundamentals):
    result = run_backtest(raw, fundamentals, market, cost_pct=cost_pct)
    if result is None:
        return None
    eq_stats = equity_curve_stats(result["equity_curve"])
    t_stats = trade_stats(result["trades"])
    exp = exposure_pct([(d, n) for d, _, n in result["regime_by_day"]])
    alpha = benchmark_alpha(result["equity_curve"], result["benchmark_closes"])
    sma_rule = sma_rule_return(result["benchmark_closes"], result["benchmark_dates"])
    regimes = regime_breakdown(result)
    return {
        "cost_pct": cost_pct,
        "n_universe": result["n_universe"],
        "n_trading_days": len(result["equity_curve"]),
        "period": {"from": result["benchmark_dates"][0], "to": result["benchmark_dates"][-1]},
        "equity": eq_stats,
        "trades": t_stats,
        "exposure_pct": exp,
        "vs_benchmark": alpha,
        "vs_sma200_rule_pct": sma_rule,
        "by_regime": regimes,
        "exit_reasons": _exit_reason_counts(result["trades"]),
    }


def _exit_reason_counts(trades):
    counts = {}
    for t in trades:
        if t.get("is_open"):
            continue
        counts[t["reason"]] = counts.get(t["reason"], 0) + 1
    return counts


def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "nasdaq"
    if market not in MARKET_FILES:
        print(f"Unbekannter Markt '{market}'. Verfügbar: {list(MARKET_FILES)}")
        sys.exit(1)

    data_dir = _ROOT / "data"
    raw = json.loads((data_dir / MARKET_FILES[market]).read_text(encoding="utf-8"))
    fundamentals = json.loads((data_dir / "fundamentals.json").read_text(encoding="utf-8")).get("tickers", {})

    print(f"Backtest 2.0 — Markt: {market}  (Universum-Datei: {MARKET_FILES[market]})")
    runs = {}
    for cost_pct in (0.001, 0.002):
        print(f"  Lauf mit {cost_pct*100:.1f}% Kosten je Seite …")
        runs[f"cost_{cost_pct}"] = run_for_cost(market, cost_pct, raw, fundamentals)

    out = {
        "market": market,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "disclaimer": DISCLAIMER,
        "runs": runs,
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{market}_{datetime.now().strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGespeichert: {out_path}")

    for key, r in runs.items():
        if r is None:
            continue
        print(f"\n── {key} ──")
        print(f"  Zeitraum: {r['period']['from']} – {r['period']['to']}  ({r['n_trading_days']} Handelstage, {r['n_universe']} Ticker im Universum)")
        print(f"  Gesamtrendite: {r['equity']['total_return_pct']}%  CAGR: {r['equity']['cagr_pct']}%  Sharpe: {r['equity']['sharpe']}")
        print(f"  Max-DD: {r['equity']['max_dd_pct']}%  ({r['equity']['max_dd_days']} Handelstage)  Calmar: {r['equity']['calmar']}")
        print(f"  Trades: {r['trades']['n_trades']}  Winrate: {r['trades']['win_rate_pct']}%  Profit-Factor: {r['trades']['profit_factor']}")
        print(f"  Exposure: {r['exposure_pct']}%")
        print(f"  vs. Benchmark Buy&Hold: {r['vs_benchmark']}")
        print(f"  vs. simple 200d-Regel auf Benchmark: {r['vs_sma200_rule_pct']}%")
        print(f"  Regime-Aufschlüsselung: {r['by_regime']}")
        print(f"  Exit-Gründe: {r['exit_reasons']}")


if __name__ == "__main__":
    main()

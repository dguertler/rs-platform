"""
Prüft die Depot-Simulation backtest_history/portfolio.js an einem von Hand
nachgerechneten Beispiel (2 Slots, Zinseszins, ausgelassenes Signal) und die
Positionsgrößen-Staffel (erst mehr Plätze bis 20, dann größerer Einsatz).

Aufruf: python3 -m pytest test_portfolio.py -q
"""
import json
import os
import subprocess

_REPO = os.path.dirname(os.path.abspath(__file__))

SCRIPT = r"""
const { simulatePortfolio, portfolioStats } = require(process.argv[1]);
const closes = {
  A: new Map([['2020-01-02', 10], ['2020-01-03', 11], ['2020-01-06', 12]]),
  B: new Map([['2020-01-02', 20], ['2020-01-03', 18]]),
  C: new Map([['2020-01-02', 5], ['2020-01-03', 5]]),
  D: new Map([['2020-01-06', 10], ['2020-01-07', 11]]),
};
const t = (ticker, rank, entryDate, entryPrice, exitDate, exitPrice, invested, isOpen = false) =>
  ({ ticker, rank, entryDate, entryPrice, exitDate, exitPrice, invested, isOpen });
const trades = [
  t('A', 1, '2020-01-02', 10, '2020-01-06', 12, 10000),
  t('B', 2, '2020-01-02', 20, '2020-01-03', 18, 5000),
  t('C', 3, '2020-01-02', 5, '2020-01-03', 5, 10000),
  t('D', 4, '2020-01-06', 10, '2020-01-07', 11, 10000, true),
];
const sim = simulatePortfolio(trades, closes, { maxPositions: 2, baseSlot: 50000 });
const stats = portfolioStats(sim, trades);
console.log(JSON.stringify({
  equity: sim.equityByDay,
  results: trades.map((x) => sim.results.get(x)),
  stats: { endEquity: stats.endEquity, taken: stats.taken, skipped: stats.skipped, maxDD: stats.maxDD },
}));
"""


def run():
    out = subprocess.run(["node", "-e", SCRIPT, os.path.join(_REPO, "backtest_history", "portfolio.js")],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_equity_path_with_compounding():
    r = run()
    assert r["equity"] == [
        ["2020-01-02", 100000],           # A 50.000 €, B 25.000 € (halber Slot), C ausgelassen
        ["2020-01-03", 102500],           # B raus zu 18 (−2.500 €), A steht bei 11
        ["2020-01-06", 107500],           # A raus zu 12 (+10.000 €), D mit 53.750 € (Slot aus 107.500 €)
        ["2020-01-07", 112875],           # D offen, Schluss 11
    ]


def test_trade_results_and_skips():
    a, b, c, d = run()["results"]
    assert a == {"taken": True, "depotInvested": 50000, "depotPnl": 10000}
    assert b == {"taken": True, "depotInvested": 25000, "depotPnl": -2500}
    assert c == {"taken": False}
    assert d["taken"] and d["stillOpen"] and d["depotInvested"] == 53750
    assert abs(d["depotPnl"] - 5375) < 1e-6


def test_stats():
    s = run()["stats"]
    assert s["endEquity"] == 112875
    assert s["taken"] == 3 and s["skipped"] == 1
    assert s["maxDD"] == 0


SIZING = r"""
const { sizing } = require(process.argv[1]);
console.log(JSON.stringify([90000, 100000, 155000, 199999, 200000, 300000].map((e) => sizing(e, 10000, 20))));
"""


def test_sizing_grows_positions_before_slot_size():
    out = subprocess.run(["node", "-e", SIZING, os.path.join(_REPO, "backtest_history", "portfolio.js")],
                         check=True, capture_output=True, text=True).stdout
    assert json.loads(out) == [
        {"limit": 9, "slot": 10000},       # nach Verlusten: weniger Plätze, Einsatz bleibt 10.000 €
        {"limit": 10, "slot": 10000},
        {"limit": 15, "slot": 10000},
        {"limit": 19, "slot": 10000},
        {"limit": 20, "slot": 10000},      # ab 200.000 €: alle 20 Plätze
        {"limit": 20, "slot": 15000},      # danach wächst der Einsatz je Trade
    ]

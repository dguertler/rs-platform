"""
Prüft simulateFromEntry (frontend/backtest_logic.js), mit dem jeder verschickte
Live-Alert als Trade bewertet wird: Kauf zur Eröffnung, Stopp am letzten
Swing-Tief × 0,99, Verkauf zur Eröffnung nach Schluss unter dem Stopp.

Aufruf: python3 -m pytest test_live_alerts.py -q
"""
import json
import os
import subprocess

_REPO = os.path.dirname(os.path.abspath(__file__))

SCRIPT = r"""
const fs = require('fs'), vm = require('vm');
vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8') + ';globalThis.E={simulateFromEntry};');
const bar = (d, o, h, l, c) => ({ d, o, h, l, c });
const days = [
  bar('2026-01-02', 100, 101, 99, 100), bar('2026-01-05', 100, 101, 95, 96),   // Swing-Tief 95
  bar('2026-01-06', 96, 102, 97, 101), bar('2026-01-07', 101, 104, 100, 103),
  bar('2026-01-08', 104, 106, 103, 105),                                       // Einstieg (Alert-Tag)
  bar('2026-01-09', 105, 106, 92, 93),                                          // Schluss unter Stopp 94,05
  bar('2026-01-12', 92, 94, 90, 91),                                            // Verkauf zur Eröffnung
];
console.log(JSON.stringify([
  globalThis.E.simulateFromEntry(days, '2026-01-08'),
  globalThis.E.simulateFromEntry(days, '2026-01-07T00'),     // vor Einstieg: nächster Handelstag
  globalThis.E.simulateFromEntry(days, '2027-01-01'),        // nach Datenende
]));
"""


def run():
    out = subprocess.run(["node", "-e", SCRIPT, os.path.join(_REPO, "frontend", "backtest_logic.js")],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_entry_stop_and_exit():
    t, _, none = run()
    assert t["entryDate"] == "2026-01-08" and t["entryPrice"] == 104
    assert abs(t["stopPrice"] - 95 * 0.99) < 1e-9
    assert t["shares"] == 96                     # 10.000 € / 104 (Risiko 9,95 € je Stück < 1.000 €)
    assert t["exitDate"] == "2026-01-12" and t["exitPrice"] == 92 and not t["isOpen"]
    assert abs(t["pnl"] - (92 - 104) * 96) < 1e-9
    assert none is None


def test_entry_uses_next_trading_day():
    _, t, _ = run()
    assert t["entryDate"] == "2026-01-08"


def test_top20_tracking_uses_sent_alerts():
    """Top-20-Performance seit Live-Start = Bilanz der verschickten Alerts."""
    for cmd in (["node", "live_alerts/evaluate_alerts.js"], ["node", "track_top20_performance.js"]):
        subprocess.run(cmd, cwd=_REPO, check=True, capture_output=True)
    live = json.load(open(os.path.join(_REPO, "data", "live_alerts_performance.json")))
    top = json.load(open(os.path.join(_REPO, "data", "top20_performance.json")))
    for src in ("QQQ", "SPX"):
        a, b = live["groups"][src], top["indices"][src]["kpis"]
        assert a["nTrades"] == b["nTrades"] and a["totalPnl"] == b["totalPnl"]
        assert abs(a["profitFactor"] - b["profitFactor"]) < 1e-9
    assert top["total"]["nTrades"] == live["groups"]["alle"]["nTrades"]

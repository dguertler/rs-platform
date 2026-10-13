"""test_reference_trades.py — Freigegebene Referenz-Trades (data/reference_trades.json).

Läuft ohne Netzwerk:  python3 -m unittest test_reference_trades

Jede Änderung an Signal- oder Ausstiegslogik muss diese Trades unverändert
wiedergeben — in der Backtest-Engine (check_reference_trades.js) und in der
Live-Prüfung der Verkäufe (check_exits.find_exit).
"""
import json
import os
import subprocess
import unittest

from check_exits import STOP_BUFFER, find_exit, load_earnings
from gws_core import swing_low_stop

_REPO = os.path.dirname(os.path.abspath(__file__))
REFS = json.load(open(os.path.join(_REPO, "data", "reference_trades.json")))["trades"]


def chart(ticker):
    with open(os.path.join(_REPO, "data", "backtest_history", "charts", f"{ticker}.json")) as f:
        c = json.load(f)
    bars = lambda rows: [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in rows]
    return bars(c["d"]), bars(c["h"])


class TestReferenceTradesBacktest(unittest.TestCase):
    """Backtest-Engine: Signal, Kauf und Verkauf wie freigegeben."""

    def test_engine_reproduces_reference_trades(self):
        run = subprocess.run(["node", "check_reference_trades.js"], cwd=_REPO,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class TestReferenceTradesLive(unittest.TestCase):
    """Live-Verkaufsprüfung: Ausstiegssignal am freigegebenen Tag."""

    def test_live_exit_signal_on_reference_day(self):
        earnings = load_earnings()
        for ref in REFS:
            with self.subTest(ref["id"]):
                earn, entry, expected = earnings.get(ref["ticker"]), ref["entry"], ref["exit"]
                self.assertTrue(earn, f"keine Earnings-Termine für {ref['ticker']}")
                daily, h4 = chart(ref["ticker"])
                entry_bar = next(b for b in h4 if b["d"] == f"{entry['date']} {entry['time']}")
                before = [b for b in daily if b["d"] < entry["date"]]
                position = {"entry_date": entry["date"], "entry_price": entry_bar["o"],
                            "stop_price": swing_low_stop(before, STOP_BUFFER)}
                exit_ = find_exit(daily, position, None, earn, h4)
                self.assertIsNotNone(exit_, "kein Ausstieg gefunden")
                self.assertEqual(exit_["signal_date"], expected["signal_date"],
                                 f"Verkaufssignal {exit_['signal_date']} ({exit_['reason']}), "
                                 f"erwartet {expected['signal_date']} ({expected['reason']})")

if __name__ == "__main__":
    unittest.main()

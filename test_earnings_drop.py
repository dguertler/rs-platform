"""Tests für die Sperre nach fallendem Kurs auf Earnings (check_exits.earnings_drop_block,
identisch zu earningsDropBlocks in frontend/backtest_logic.js).

Schließt der Reaktionstag mindestens 5 % unter dem Schluss vor den Zahlen, gibt es keinen
Kauf, bis Daily danach einmal rot war oder ein Schluss über dem Kurs vor den Zahlen liegt.
"""
import json
import os
import subprocess
import unittest
from unittest import mock

import check_exits

ROOT = os.path.dirname(os.path.abspath(__file__))
AVGO_CHART = os.path.join(ROOT, "data", "backtest_history", "charts", "AVGO.json")
EARNINGS = os.path.join(ROOT, "data", "earnings_history.json")


def day_bars(closes, start=1):
    return [{"d": f"2024-01-{start + i:02d}", "o": c, "h": c, "l": c, "c": c} for i, c in enumerate(closes)]


class EarningsDropRuleTest(unittest.TestCase):
    earnings = [["2024-01-02", "amc"]]          # Reaktionstag 03.01.

    def block(self, closes, day, green=True):
        with mock.patch("check_alerts.analyze_daily_structure", return_value={"broken": green}):
            return check_exits.earnings_drop_block(self.earnings, day_bars(closes), day)

    def test_drop_of_five_percent_blocks(self):
        self.assertEqual(self.block([100, 100, 94, 95, 96], "2024-01-06"), ["2024-01-02", "amc"])

    def test_small_drop_does_not_block(self):
        self.assertIsNone(self.block([100, 100, 97, 98, 99], "2024-01-06"))

    def test_close_above_pre_earnings_close_releases(self):
        self.assertIsNone(self.block([100, 100, 94, 101, 96], "2024-01-06"))

    def test_daily_red_releases(self):
        self.assertIsNone(self.block([100, 100, 94, 95, 96], "2024-01-06", green=False))


@unittest.skipUnless(os.path.exists(AVGO_CHART) and os.path.exists(EARNINGS), "Kurs- oder Termindatei fehlt")
class AvgoSeptember2023Test(unittest.TestCase):
    """AVGO: Zahlen 31.08.2023 nach Börsenschluss, 01.09. Schluss 84,02 nach 88,79 (−5,4 %),
    Daily bleibt grün → kein Kauf am 14.09.; Daily wird Ende September rot → ab Oktober frei."""

    def test_live_block(self):
        d = [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in json.load(open(AVGO_CHART))["d"]]
        e = json.load(open(EARNINGS))["tickers"]["AVGO"]
        got = [bool(check_exits.earnings_drop_block(e, [b for b in d if b["d"] < day], day))
               for day in ("2023-09-01", "2023-09-14", "2023-10-02")]
        self.assertEqual(got, [False, True, False])

    def test_backtest_engine_skips_trade(self):
        out = subprocess.run(["node", "inspect_ticker.js", "AVGO", "2023-09-01", "2023-09-30"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertNotIn("Signal 2023-09-14", out)


if __name__ == "__main__":
    unittest.main()

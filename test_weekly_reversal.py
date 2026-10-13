"""Tests für die Weekly-Trendumkehr-Regel (check_alerts.weekly_reversal_blocks).

Zeigt Weekly eine Trendumkehr (nur gehalten oder tieferes Tief in Bildung), zählt ein
4H-Signal erst, wenn Daily tatsächlich über seine Marke ausgebrochen ist und 4H nach dem
Tag dieses Ausbruchs einmal rot war — identisch zu weeklyReversal/simulateTradesPIT in
frontend/backtest_logic.js. AVGO: kein Kauf 31.07. und 13.08.2024, Kauf 12.09.2024.
"""
import json
import os
import unittest
from datetime import date, timedelta

import check_alerts

ROOT = os.path.dirname(os.path.abspath(__file__))
AVGO_CHART = os.path.join(ROOT, "data", "backtest_history", "charts", "AVGO.json")


def bars(rows):
    return [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in rows]


def monday(day):
    d = date.fromisoformat(day[:10])
    return (d - timedelta(days=d.weekday())).isoformat()


class LowerLowFormingTest(unittest.TestCase):
    # Marke idx 1, Swing-Tief idx 3 (5), danach tiefer (4) → Umkehr in Bildung
    def test_lower_low_below_last_swing_low(self):
        self.assertTrue(check_alerts._weekly_lower_low_forming([6, 7, 6, 5, 6, 4], 1))

    def test_higher_low_no_reversal(self):
        self.assertFalse(check_alerts._weekly_lower_low_forming([6, 7, 6, 5, 6, 5.5], 1))

    def test_swing_low_before_mark_ignored(self):
        self.assertFalse(check_alerts._weekly_lower_low_forming([6, 5, 6, 7, 8, 4], 3))


@unittest.skipUnless(os.path.exists(AVGO_CHART), "Kursdatei AVGO fehlt")
class AvgoWeeklyReversalTest(unittest.TestCase):
    """Signale (4H-Kerze 14:00) AVGO 2024 mit Tageskerze bis jetzt und laufender Woche."""

    def setUp(self):
        chart = json.load(open(AVGO_CHART))
        self.w, self.d, self.h = bars(chart["w"]), bars(chart["d"]), bars(chart["h"])

    def blocks(self, bar):
        day = bar[:10]
        h4 = [b for b in self.h if b["d"] <= bar][-60:]
        today = next(b for b in self.d if b["d"] == day)
        daily = [b for b in self.d if b["d"] < day] + [{
            "d": day, "o": today["o"], "h": max(today["o"], h4[-1]["h"]),
            "l": min(today["o"], h4[-1]["l"]), "c": h4[-1]["c"]}]
        wk = monday(day)
        week_days = [b for b in daily if monday(b["d"]) == wk]
        weekly = [b for b in self.w if monday((date.fromisoformat(b["d"]) + timedelta(days=2)).isoformat()) < wk][-59:]
        weekly.append({"d": wk, "o": week_days[0]["o"], "h": max(b["h"] for b in week_days),
                       "l": min(b["l"] for b in week_days), "c": week_days[-1]["c"]})
        info = check_alerts.count_points({"ohlcv_w": weekly, "ohlcv": daily, "ohlcv_4h": h4})
        self.assertEqual(info["points"], 3, bar)
        return check_alerts.weekly_reversal_blocks(info, daily, h4)

    def test_no_buy_while_daily_only_held(self):
        self.assertTrue(self.blocks("2024-07-31 14:00"))
        self.assertTrue(self.blocks("2024-08-13 14:00"))

    def test_buy_after_daily_breakout_and_4h_retracement(self):
        self.assertFalse(self.blocks("2024-09-12 14:00"))


if __name__ == "__main__":
    unittest.main()

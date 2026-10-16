"""Tests für das Signal-Halten nach Trendumkehr (Weekly und Daily, gws_core.held_after_breakout).

Bildet ein tieferes Tief eine neue Marke, bleibt die Ebene grün, solange seit der
Ausbruchskerze der zuletzt gebrochenen Marke kein Schluss unter dem Anker liegt (Weekly:
letztes Swing-Tief vor der Ausbruchswoche, gebrochen beim ersten Tagesschluss darunter, Daily:
letztes Swing-Tief, das die Trendumkehr noch nicht unterschritten hat, geprüft ab der Trendumkehr) —
identisch zu heldAfterBreakout in frontend/backtest_logic.js.
"""
import json
import os
import subprocess
import unittest

import check_alerts
from gws_core import held_after_breakout, tu_anchor_low

ROOT = os.path.dirname(os.path.abspath(__file__))
AVGO_CHART = os.path.join(ROOT, "data", "backtest_history", "charts", "AVGO.json")


def bars(rows):
    return [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in rows]


class HeldAfterBreakoutTest(unittest.TestCase):
    # Marke bei 10 (idx 1), Ausbruch idx 3 (Schluss 11, Tief 9), danach neue Marke bei 14
    closes = [8, 9, 8, 11, 13, 12, 10]
    lows = [7, 8, 7, 9, 12, 11, 9.5]
    cands = [{"idx": 1, "price": 10}, {"idx": 4, "price": 14}]

    def test_holds_while_no_close_below_breakout_low(self):
        self.assertTrue(held_after_breakout(self.cands, self.closes, self.lows, 7, min_margin=0))

    def test_ends_with_close_below_breakout_low(self):
        closes = self.closes[:-1] + [8.5]
        self.assertFalse(held_after_breakout(self.cands, closes, self.lows, 7, min_margin=0))

    def test_without_broken_mark_stays_red(self):
        self.assertFalse(held_after_breakout([{"idx": 4, "price": 14}], self.closes, self.lows, 7, min_margin=0))


class TuAnchorTest(unittest.TestCase):
    """Daily-Anker nach Trendumkehr: letztes Swing-Tief vor tief_neu, das tiefer liegt."""
    # Ausbruch idx 2 (Tief 9), Swing-Tiefs bei idx 5 (11) und idx 9 (13), Trendumkehr idx 13 (12)
    lows = [8, 8.5, 9, 12, 11.5, 11, 12, 13, 13.5, 13, 14, 15, 14, 12, 13, 14]

    def test_anchor_is_swing_low_below_trend_reversal(self):
        nxt = {"idx": 11, "price": 16, "tief_neu": {"idx": 13, "price": 12}}
        self.assertEqual(tu_anchor_low(nxt, self.lows, 2), 11)

    def test_without_trend_reversal_breakout_low(self):
        self.assertEqual(tu_anchor_low(None, self.lows, 2), 9)


@unittest.skipUnless(os.path.exists(AVGO_CHART), "Kursdatei AVGO fehlt")
class AvgoDailyTest(unittest.TestCase):
    """AVGO Daily 2023: Trendumkehr 04.08. (84,09) deaktiviert nur den Trade; Daily bleibt
    gehalten bis zum Schluss unter dem Swing-Tief vom 06.07. (81,29) am 10.08. (81,16) und ist
    rot bis zum neuen Ausbruch am 21.08.: Schluss 83,30 über der Marke 82,28 (Hoch 15.08.), die
    das tiefere Tief vom 18.08. bildet — der Ausbruch bestätigt dieses Swing-Tief schon mit
    einer Folgekerze. Live und in der Backtest-Engine gleich."""
    days = ["2023-08-08", "2023-08-09", "2023-08-10", "2023-08-18", "2023-08-21", "2023-08-22"]
    expected = [True, True, False, False, True, True]

    def test_live_daily(self):
        d = bars(json.load(open(AVGO_CHART))["d"])
        got = [check_alerts.analyze_daily_structure([b for b in d if b["d"] <= day])["broken"]
               for day in self.days]
        self.assertEqual(got, self.expected)

    def test_backtest_engine_daily(self):
        script = (
            "require('vm').runInThisContext(require('fs').readFileSync('frontend/backtest_logic.js','utf8'));"
            "const c=require('./data/backtest_history/charts/AVGO.json');"
            "const D=c.d.map(a=>({d:a[0],o:a[1],h:a[2],l:a[3],c:a[4]}));"
            f"console.log(JSON.stringify({json.dumps(self.days)}.map(t=>analyzeStructure(D.filter(x=>x.d<=t)).broken)));")
        out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), self.expected)


@unittest.skipUnless(os.path.exists(AVGO_CHART), "Kursdatei AVGO fehlt")
class AvgoDailyOctober2023Test(AvgoDailyTest):
    """AVGO 30.10.2023: Trendumkehr (Tief 26.10. bei 79,22, neue Marke 85,48) — Daily bleibt
    gehalten, weil das Swing-Tief vor dem Ausbruch 11.10. (78,58 vom 06.10., grüne Linie) per
    Schluss nicht unterschritten wird; ab 07.11. wieder regulär grün."""
    days = ["2023-10-27", "2023-10-30", "2023-11-03", "2023-11-07"]
    expected = [True, True, True, True]


@unittest.skipUnless(os.path.exists(AVGO_CHART), "Kursdatei AVGO fehlt")
class AvgoWeeklyTest(unittest.TestCase):
    """AVGO KW 15.07.2024: tieferes Wochentief → Marke 137,12 → 173,51. Das Tief der
    Ausbruchswoche 13.05.2024 (129,48) hält, Weekly bleibt grün."""

    def setUp(self):
        chart = json.load(open(AVGO_CHART))
        self.w, self.d = bars(chart["w"]), bars(chart["d"])
        self.addCleanup(setattr, check_alerts, "HOLD_WEEKLY", check_alerts.HOLD_WEEKLY)

    def weekly(self, day):
        return check_alerts.analyze_weekly_structure([b for b in self.w if b["d"] <= day][-60:],
                                                     [b for b in self.d if b["d"] <= day])

    def test_new_mark_from_trend_reversal(self):
        self.assertAlmostEqual(self.weekly("2024-08-12")["gws_price"], 173.51, places=2)

    def test_weekly_held_green(self):
        check_alerts.HOLD_WEEKLY = True
        self.assertTrue(self.weekly("2024-08-12")["broken"])

    def test_weekly_red_without_hold(self):
        check_alerts.HOLD_WEEKLY = False
        self.assertFalse(self.weekly("2024-08-12")["broken"])

    def test_weekly_held_through_november_2024(self):
        # Ausbruch über 173,51 am 26.09.2024; Wochenschluss 11.11. (162,03) unter dem Tief der
        # Ausbruchswoche (165,48), aber kein Tagesschluss unter dem Swing-Tief davor (132,17) → grün
        check_alerts.HOLD_WEEKLY = True
        st = self.weekly("2024-12-02")
        self.assertAlmostEqual(st["gws_price"], 181.90, places=2)
        self.assertTrue(st["broken"])

    def test_backtest_engine_holds_weekly(self):
        script = (
            "require('vm').runInThisContext(require('fs').readFileSync('frontend/backtest_logic.js','utf8'));"
            "const c=require('./data/backtest_history/charts/AVGO.json');"
            "const b=a=>({d:a[0],o:a[1],h:a[2],l:a[3],c:a[4]});"
            "const W=normalizeWeekly(c.w.map(b)), D=c.d.map(b).filter(x=>x.d<='2024-07-23');"
            "const r=[analyzeWeeklyStructure(weeklyUpTo(W,D),D).broken];"
            "setHoldSignal({w:false,d:true});r.push(analyzeWeeklyStructure(weeklyUpTo(W,D),D).broken);"
            "console.log(JSON.stringify(r));")
        out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), [True, False])


PANW_CHART = os.path.join(ROOT, "data", "backtest_history", "charts", "PANW.json")


@unittest.skipUnless(os.path.exists(PANW_CHART), "Kursdatei PANW fehlt")
class PanwWeeklyBreakTest(unittest.TestCase):
    """PANW 2022: Ausbruch über 95,44 (Woche 28.02.), Anker = Swing-Tief davor 77,75 (21.02.).
    Wochentief 09.05.2022 bei 75,05 darunter → Weekly rot, obwohl die Marke noch gebrochen ist
    und der Wochenschluss (81,83) darüber liegt; erst am 22.02.2023 wieder grün."""

    def setUp(self):
        with open(PANW_CHART) as f:
            chart = json.load(f)
        self.w, self.d = bars(chart["w"]), bars(chart["d"])

    def weekly(self, day):
        return check_alerts.analyze_weekly_structure([b for b in self.w if b["d"] <= day][-60:],
                                                     [b for b in self.d if b["d"] <= day])

    def test_live_weekly_green_before_close_below_anchor(self):
        self.assertTrue(self.weekly("2022-05-06")["broken"])

    def test_live_weekly_red_after_weekly_low_below_anchor(self):
        for day in ("2022-05-09", "2022-06-02", "2022-07-05", "2022-08-22"):
            with self.subTest(day=day):
                self.assertFalse(self.weekly(day)["broken"])

    def test_backtest_engine_matches_live(self):
        script = (
            "require('vm').runInThisContext(require('fs').readFileSync('frontend/backtest_logic.js','utf8'));"
            "const c=require('./data/backtest_history/charts/PANW.json');"
            "const b=a=>({d:a[0],o:a[1],h:a[2],l:a[3],c:a[4]});const W=normalizeWeekly(c.w.map(b));"
            "console.log(JSON.stringify(['2022-05-06','2022-05-09','2022-07-05'].map(day=>{"
            "const D=c.d.map(b).filter(x=>x.d<=day);return analyzeWeeklyStructure(weeklyUpTo(W,D),D).broken;})));"
        )
        out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), [True, False, False])


ZS_CHART = os.path.join(ROOT, "data", "backtest_history", "charts", "ZS.json")


@unittest.skipUnless(os.path.exists(ZS_CHART), "Kursdatei ZS fehlt")
class ZsWeeklyTrailTest(unittest.TestCase):
    """ZS 2024: Woche 08.01. schließt bei 230,77 über dem Swing-Hoch 227,29 (25.12.2023) → Anker
    rückt auf 206,67 (Tief der Woche 01.01.); Woche 19.02. Tief 202,44 darunter → Weekly rot."""

    def setUp(self):
        with open(ZS_CHART) as f:
            chart = json.load(f)
        self.w, self.d = bars(chart["w"]), bars(chart["d"])

    def weekly(self, day):
        return check_alerts.analyze_weekly_structure([b for b in self.w if b["d"] <= day][-60:],
                                                     [b for b in self.d if b["d"] <= day])

    def test_live_green_before_and_red_after_trailing_anchor(self):
        self.assertTrue(self.weekly("2024-02-16")["broken"])
        for day in ("2024-02-23", "2024-05-17"):
            with self.subTest(day=day):
                self.assertFalse(self.weekly(day)["broken"])

    def test_backtest_engine_matches_live(self):
        script = (
            "require('vm').runInThisContext(require('fs').readFileSync('frontend/backtest_logic.js','utf8'));"
            "const c=require('./data/backtest_history/charts/ZS.json');"
            "const b=a=>({d:a[0],o:a[1],h:a[2],l:a[3],c:a[4]});const W=normalizeWeekly(c.w.map(b));"
            "console.log(JSON.stringify(['2024-02-16','2024-02-21','2024-05-17'].map(day=>{"
            "const D=c.d.map(b).filter(x=>x.d<=day);const s=analyzeWeeklyStructure(weeklyUpTo(W,D),D);"
            "return [s.broken, s.zone ? +s.zone.anchor.toFixed(2) : null];})));"
        )
        out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), [[True, 206.67], [False, None], [False, None]])


if __name__ == "__main__":
    unittest.main()


class TestRetracementZone(unittest.TestCase):
    """Daily erlischt erst bei Schluss unter der Untergrenze; sie rückt nur nach einem Rücksetzer
    von mindestens 10 Handelstagen nach (gws_core.retracement_zone = retracementZone in JS)."""

    @staticmethod
    def series(lows_closes, highs):
        return [h for h in highs], [l for l, _ in lows_closes], [c for _, c in lows_closes]

    def js(self, highs, lows, closes, b):
        import json, subprocess
        snippet = ("const fs = require('fs'), vm = require('vm');"
                   "vm.runInThisContext(fs.readFileSync('frontend/backtest_logic.js', 'utf8'));"
                   f"const z = retracementZone({json.dumps(highs)}, {json.dumps(lows)}, {json.dumps(closes)}, {b}, {len(highs)});"
                   "console.log(JSON.stringify(z ? z.low : null));")
        return json.loads(subprocess.run(["node", "-e", snippet], capture_output=True, text=True, check=True).stdout)

    def check(self, highs, lows, closes, b, expected):
        from gws_core import retracement_zone
        self.assertEqual(retracement_zone(highs, lows, closes, b, len(highs)), expected)
        self.assertEqual(self.js(highs, lows, closes, b), expected)

    def test_tief_darunter_schluss_darueber_bleibt(self):
        # Swing-Tief 8 vor dem Ausbruch (Index 4); Index 6 Tief 7 < 8, Schluss 9 > 8 → bleibt
        highs  = [10, 9, 9.5, 9, 11, 12, 11]
        lows   = [9, 8.5, 8, 8.5, 10, 11, 7]
        closes = [9.5, 9, 9, 9, 10.8, 11.5, 9]
        self.check(highs, lows, closes, 4, 8)

    def test_kurzer_ruecksetzer_ruekt_nicht_nach(self):
        # neues Hoch 3 Tage nach dem alten → Untergrenze bleibt 8, Schluss 8,5 hält
        highs  = [10, 9, 9.5, 9, 11, 12, 11.5, 11, 13, 10]
        lows   = [9, 8.5, 8, 8.5, 10, 11, 10.5, 10, 12, 8.2]
        closes = [9.5, 9, 9, 9, 10.8, 11.5, 11, 10.5, 12.5, 8.5]
        self.check(highs, lows, closes, 4, 8)

    def test_langer_ruecksetzer_setzt_neues_tief(self):
        # Hoch 12 an Index 5, Rücksetzer bis Index 15 (10 Tage), Tief 10,2 → neue Untergrenze
        highs  = [10, 9, 9.5, 9, 11, 12] + [11.5] * 9 + [12.5, 12]
        lows   = [9, 8.5, 8, 8.5, 10, 11] + [10.5, 10.4, 10.2] + [10.6] * 6 + [11.5, 11]
        closes = [9.5, 9, 9, 9, 10.8, 11.5] + [11] * 9 + [12.4, 11.8]
        self.check(highs, lows, closes, 4, 10.2)
        self.check(highs + [10.5], lows + [9.9], closes + [10.0], 4, None)   # Schluss unter 10,2 → erloschen

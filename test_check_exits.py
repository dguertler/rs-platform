"""test_check_exits.py — Regressionstests für die Verkaufssignale.

Läuft ohne Netzwerk:  python3 -m unittest test_check_exits

Geprüft wird die Regel aus frontend/backtest_logic.js: Signal am Tagesschluss
(Schluss unter dem Trendumkehr-Tief — letztes Swing-Tief vor dem letzten
Swing-Hoch — oder unter dem Stopp), Ausführung zur Eröffnung des Folgetages.
"""
import unittest

from check_exits import collect_new_positions, daily_structure, derive_entry, find_exit


def bar(date, open_, high, low, close):
    return {"d": date, "o": open_, "h": high, "l": low, "c": close}


def rising(n, start=100.0, step=1.0, first_day=1):
    """Gleichmäßig steigende Tageskerzen — erzeugt eine intakte Struktur."""
    rows = []
    for i in range(n):
        base = start + i * step
        rows.append(bar(f"2026-01-{first_day + i:02d}", base, base + 1, base - 1, base + 0.5))
    return rows


class TestDeriveEntry(unittest.TestCase):
    """Einstieg = Eröffnung des Folgetages, Stopp = letztes Swing-Tief × 0,99."""

    def test_einstieg_ist_die_eroeffnung_am_alert_tag(self):
        rows = rising(40)
        entry = derive_entry(rows, "2026-01-21")       # Mail vor Börsenbeginn am 21.
        self.assertEqual(entry["entry_date"], "2026-01-21")
        self.assertAlmostEqual(entry["entry_price"], rows[20]["o"])

    def test_stopp_liegt_unter_dem_einstieg(self):
        entry = derive_entry(rising(40), "2026-01-20")
        self.assertLess(entry["stop_price"], entry["entry_price"])

    def test_ohne_kerze_am_alert_tag_kein_einstieg(self):
        rows = rising(40)
        self.assertIsNone(derive_entry(rows, "2026-02-28"))


class TestFindExit(unittest.TestCase):

    def setUp(self):
        self.position = {"entry_date": "2026-01-31", "entry_price": 130.0, "stop_price": 120.0}

    def test_kein_ausstieg_im_intakten_aufwaertstrend(self):
        rows = rising(45)
        pos = {"entry_date": rows[30]["d"], "entry_price": rows[30]["o"], "stop_price": 90.0}
        self.assertIsNone(find_exit(rows, pos, None))

    def test_ausstieg_wenn_der_schluss_unter_den_stopp_faellt(self):
        rows = rising(40)
        rows.append(bar("2026-02-10", 139.0, 139.5, 100.0, 101.0))   # Einbruch
        rows.append(bar("2026-02-11", 99.0, 100.0, 98.0, 99.5))      # Ausführungstag
        pos = {"entry_date": rows[30]["d"], "entry_price": 130.0, "stop_price": 120.0}
        hit = find_exit(rows, pos, None)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["signal_date"], "2026-02-10")
        self.assertEqual(hit["exit_date"], "2026-02-11")
        self.assertAlmostEqual(hit["exit_price"], 99.0)   # Eröffnung des Folgetages
        self.assertFalse(hit["pending"])

    def test_signal_ohne_folgetag_bleibt_offen(self):
        rows = rising(40)
        rows.append(bar("2026-02-10", 139.0, 139.5, 100.0, 101.0))
        pos = {"entry_date": rows[30]["d"], "entry_price": 130.0, "stop_price": 120.0}
        hit = find_exit(rows, pos, None)
        self.assertTrue(hit["pending"])

    def test_bereits_geprueft_wird_uebersprungen(self):
        rows = rising(40)
        rows.append(bar("2026-02-10", 139.0, 139.5, 100.0, 101.0))
        rows.append(bar("2026-02-11", 99.0, 100.0, 98.0, 99.5))
        pos = {"entry_date": rows[30]["d"], "entry_price": 130.0, "stop_price": 120.0}
        self.assertIsNone(find_exit(rows, pos, "2026-02-11"))

    def test_tage_vor_dem_einstieg_zaehlen_nicht(self):
        rows = rising(20) + [bar("2026-01-21", 118.0, 118.5, 100.0, 100.5)] + rising(25, start=140.0, first_day=22)
        pos = {"entry_date": "2026-02-01", "entry_price": 150.0, "stop_price": 100.0}
        hit = find_exit(rows, pos, None)
        self.assertTrue(hit is None or hit["signal_date"] >= "2026-02-01")


class TestBreakEvenStop(unittest.TestCase):
    """Einstands-Stopp wie breakEven in backtest_logic.js: nach einem Schluss ≥ Einstieg + 2R gilt
    der Einstieg als Stopp, ein Schluss darunter → Verkauf „Einstand“."""

    def test_einstand_nach_2r(self):
        from check_exits import effective_stop
        rows = rising(40)                                   # Schlusskurse steigen bis ~139
        pos = {"entry_date": rows[20]["d"], "entry_price": 125.0, "stop_price": 120.0}   # R = 5, 2R bei 135
        self.assertEqual(effective_stop(rows, pos, 21), (120.0, False))
        self.assertEqual(effective_stop(rows, pos, len(rows)), (125.0, True))

    def test_verkauf_einstand_bei_schluss_unter_dem_einstieg(self):
        rows = rising(40)
        rows.append(bar("2026-02-10", 139.0, 139.5, 123.0, 124.0))   # unter Einstieg 125, über Stopp 120
        rows.append(bar("2026-02-11", 124.0, 125.0, 122.0, 124.5))
        pos = {"entry_date": rows[20]["d"], "entry_price": 125.0, "stop_price": 120.0}
        hit = find_exit(rows, pos, None)
        self.assertEqual(hit["reason"], "Einstand")
        self.assertEqual(hit["signal_date"], "2026-02-10")


class TestVerbrauchtesTrendumkehrTief(unittest.TestCase):
    """Trendumkehr-Tief, das schon vor dem Kauf per Schluss unterschritten war, zählt nicht —
    es gilt das tiefste Tief seit dem Bruch (wie entryTrendLow in backtest_logic.js)."""

    def test_cdns_2026(self):
        import json, os
        from check_exits import entry_trend_low
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backtest_history", "charts", "CDNS.json")
        if not os.path.exists(path):
            self.skipTest("Kursdatei CDNS fehlt")
        with open(path) as f:
            d = [{"d": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4]} for r in json.load(f)["d"]]
        if d[-1]["d"] < "2026-06-30":
            self.skipTest("Kursdatei CDNS endet vor 06/2026")
        rows = [b for b in d if b["d"] < "2026-06-30"]
        self.assertAlmostEqual(entry_trend_low(rows, daily_structure(rows), "2026-06-29"), 358.76, places=2)


class TestCollectNewPositions(unittest.TestCase):
    """Nur 4H-Auslöser, nur Watchlist-Titel, keine bereits abgeschlossenen Signale."""

    def setUp(self):
        self.market = {"MU": {"ohlcv": rising(40), "source": "QQQ"}}
        self.signals = {
            "MU":   [{"signal_date": "2026-01-20", "trigger_tf": "4h", "source": "QQQ"}],
            "AAPL": [{"signal_date": "2026-01-20", "trigger_tf": "4h", "source": "QQQ"}],
        }

    def test_nimmt_watchlist_titel_mit_4h_signal_auf(self):
        positions = {}
        opened, _ = collect_new_positions({"MU"}, self.market, self.signals, positions, {})
        self.assertEqual(opened, ["MU"])
        self.assertTrue(positions["MU"]["adopted"])

    def test_ignoriert_titel_ausserhalb_der_watchlist(self):
        positions = {}
        collect_new_positions(set(), self.market, self.signals, positions, {})
        self.assertEqual(positions, {})

    def test_ignoriert_daily_und_weekly_ausloeser(self):
        signals = {"MU": [{"signal_date": "2026-01-20", "trigger_tf": "daily", "source": "QQQ"},
                          {"signal_date": "2026-01-19", "trigger_tf": "weekly", "source": "QQQ"}]}
        positions = {}
        opened, _ = collect_new_positions({"MU"}, self.market, signals, positions, {})
        self.assertEqual(opened, [])

    def test_nimmt_abgeschlossenes_signal_nicht_erneut_auf(self):
        positions = {}
        opened, _ = collect_new_positions({"MU"}, self.market, self.signals, positions,
                                          {"MU": "2026-01-20"})
        self.assertEqual(opened, [])

    def test_meldet_signal_ohne_kerze_am_alert_tag_als_wartend(self):
        signals = {"MU": [{"signal_date": "2026-03-31",
                           "trigger_tf": "4h", "source": "QQQ"}]}
        positions = {}
        opened, pending = collect_new_positions({"MU"}, self.market, signals, positions, {})
        self.assertEqual(opened, [])
        self.assertEqual(len(pending), 1)


class TestVerkaufImmerMelden(unittest.TestCase):
    """Jedes Verkaufssignal kommt in die Mail — auch bei einer gerade erst erfassten Position."""

    def run_watchlist(self, rows, state):
        from unittest import mock
        import check_exits
        saved = {}
        with mock.patch.object(check_exits, "load_watchlist", return_value={"MU"}), \
             mock.patch.object(check_exits, "load_json", return_value=state), \
             mock.patch.object(check_exits, "load_earnings", return_value={}), \
             mock.patch.object(check_exits, "save_state", side_effect=lambda s: saved.update(s)):
            exits, _ = check_exits.process_watchlist({"MU": {"ohlcv": rows, "source": "QQQ"}}, {})
        return exits, saved

    def position(self, rows):
        return {"ticker": "MU", "source": "QQQ", "signal_date": rows[29]["d"], "last_checked": None,
                "adopted": True, "entry_date": rows[30]["d"], "entry_price": 130.0, "stop_price": 120.0}

    def test_neu_erfasste_position_mit_offenem_verkauf_wird_gemeldet(self):
        rows = rising(40) + [bar("2026-02-10", 139.0, 139.5, 100.0, 101.0)]
        exits, saved = self.run_watchlist(rows, {"positions": {"MU": self.position(rows)}, "closed": {}})
        self.assertEqual([e["signal_date"] for e in exits], ["2026-02-10"])
        self.assertIn("MU", saved["positions"])          # Ausführung erst zur nächsten Eröffnung

    def test_neu_erfasste_position_mit_ausgefuehrtem_verkauf_wird_gemeldet(self):
        rows = rising(40) + [bar("2026-02-10", 139.0, 139.5, 100.0, 101.0),
                             bar("2026-02-11", 99.0, 100.0, 98.0, 99.5)]
        exits, saved = self.run_watchlist(rows, {"positions": {"MU": self.position(rows)}, "closed": {}})
        self.assertEqual(len(exits), 1)
        self.assertNotIn("MU", saved["positions"])

    def test_bereits_gemeldeter_verkauf_nicht_doppelt(self):
        rows = rising(40) + [bar("2026-02-10", 139.0, 139.5, 100.0, 101.0),
                             bar("2026-02-11", 99.0, 100.0, 98.0, 99.5)]
        pos = {**self.position(rows), "exit_reported": "2026-02-10"}
        exits, _ = self.run_watchlist(rows, {"positions": {"MU": pos}, "closed": {}})
        self.assertEqual(exits, [])


if __name__ == "__main__":
    unittest.main()


class TestZeitstoppUndSL(unittest.TestCase):
    """Zeitstopp (10 Handelstage, mind. +5 %), wirksamer SL und Modell-Depot (10 Plätze)."""

    def test_zeitstopp_abgeschaltet(self):
        rows = rising(31) + [bar(f"2026-02-{d:02d}", 131.0, 132.0, 130.0, 131.0) for d in range(1, 13)]
        pos = {"entry_date": rows[30]["d"], "entry_price": rows[30]["o"], "stop_price": 90.0}
        self.assertIsNone(find_exit(rows, pos, None))

    def test_zeitstopp_wenn_eingeschaltet_nach_10_tagen_unter_plus_5_prozent(self):
        import check_exits
        rows = rising(31) + [bar(f"2026-02-{d:02d}", 131.0, 132.0, 130.0, 131.0) for d in range(1, 13)]
        pos = {"entry_date": rows[30]["d"], "entry_price": rows[30]["o"], "stop_price": 90.0}
        check_exits.TIME_STOP_ENABLED = True
        try:
            hit = find_exit(rows, pos, None)
        finally:
            check_exits.TIME_STOP_ENABLED = False
        self.assertEqual(hit["reason"], "Zeitstopp")
        self.assertEqual(hit["signal_date"], rows[40]["d"])      # 10. Handelstag nach dem Einstieg
        self.assertEqual(hit["exit_date"], rows[41]["d"])        # Verkauf zur nächsten Eröffnung

    def test_kein_zeitstopp_bei_mehr_als_plus_5_prozent(self):
        rows = rising(31) + [bar(f"2026-02-{d:02d}", 131.0 + 2 * d, 132.0 + 2 * d, 130.0 + 2 * d,
                                 131.5 + 2 * d) for d in range(1, 13)]
        pos = {"entry_date": rows[30]["d"], "entry_price": rows[30]["o"], "stop_price": 90.0}
        self.assertIsNone(find_exit(rows, pos, None))

    def test_sl_ist_mindestens_der_stopp(self):
        from check_exits import exit_level
        level, kind = exit_level(rising(45), 90.0)
        self.assertGreaterEqual(level, 90.0)
        self.assertIn(kind, ("Stopp", "Trendumkehr-Tief"))

    def test_depot_hoechstens_10_kaeufe(self):
        import os
        import tempfile
        import check_exits
        rows = rising(40)
        market = {f"T{i}": {"ohlcv": rows, "source": "QQQ"} for i in range(12)}
        alerts = [{"ticker": f"T{i}", "rank": i + 1, "stop_price": 120.0, "source": "QQQ"} for i in range(12)]
        old = check_exits.DEPOT_FILE
        with tempfile.TemporaryDirectory() as tmp:
            check_exits.DEPOT_FILE = os.path.join(tmp, "live_depot.json")
            try:
                check_exits.depot_decisions(alerts, {}, market, rows[-1]["d"])
            finally:
                check_exits.DEPOT_FILE = old
        self.assertEqual(sum(a["decision"] == "Kauf" for a in alerts), 10)
        self.assertTrue(alerts[-1]["decision"].startswith("Kein Kauf"))


class TestEarnings(unittest.TestCase):
    """Kein Kauf < 4 Kalendertage vor den Zahlen; Verkauf 14-Uhr-Kerze am letzten Handelstag davor."""

    def setUp(self):
        self.ohlcv = rising(20)            # 2026-01-01 … 2026-01-20, gleichmäßig steigend
        self.pos = {"entry_date": "2026-01-02", "entry_price": 101.0, "stop_price": 50.0}

    def test_kauf_gesperrt_weniger_als_4_tage_vorher(self):
        from check_exits import earnings_blocks_entry
        self.assertTrue(earnings_blocks_entry([["2026-01-12", "amc"]], "2026-01-09"))
        self.assertFalse(earnings_blocks_entry([["2026-01-12", "amc"]], "2026-01-08"))
        self.assertFalse(earnings_blocks_entry(None, "2026-01-08"))

    def test_verkauf_nach_boersenschluss_am_selben_tag_zum_14_uhr_schluss(self):
        h4 = [{"d": "2026-01-10 14:00", "o": 1, "h": 1, "l": 1, "c": 111.11}]
        hit = find_exit(self.ohlcv, self.pos, None, [["2026-01-10", "amc"]], h4)
        self.assertEqual((hit["signal_date"], hit["exit_date"], hit["exit_price"]), ("2026-01-10", "2026-01-10", 111.11))
        self.assertFalse(hit["pending"])

    def test_verkauf_vor_boersenbeginn_am_vortag(self):
        hit = find_exit(self.ohlcv, self.pos, None, [["2026-01-10", "bmo"]])
        self.assertEqual(hit["exit_date"], "2026-01-09")

    def test_bereits_vergangene_zahlen_loesen_nicht_nachtraeglich_aus(self):
        # MRVL 12.10.2026: Zahlen lagen vor dem ersten geprüften Tag → kein Earnings-Verkauf
        earnings = [["2026-01-05", "amc"], ["2026-01-30", "amc"]]
        self.assertIsNone(find_exit(self.ohlcv, self.pos, "2026-01-08", earnings, today="2026-01-20"))

    def test_naechste_zahlen_nach_der_pruefung_gelten_weiter(self):
        earnings = [["2026-01-05", "amc"], ["2026-01-15", "amc"]]
        hit = find_exit(self.ohlcv, self.pos, "2026-01-08", earnings)
        self.assertEqual(hit["exit_date"], "2026-01-15")

    def test_ab_2r_durch_die_zahlen_halten(self):
        # R = 101 − 95 = 6, 2R bei 113 — Schluss 113,5 am 14.01., Zahlen 17.01. → kein Verkauf
        pos = {"entry_date": "2026-01-02", "entry_price": 101.0, "stop_price": 95.0}
        self.assertIsNone(find_exit(self.ohlcv, pos, None, [["2026-01-17", "amc"]]))

    def test_unter_2r_vor_den_zahlen_verkaufen(self):
        pos = {"entry_date": "2026-01-02", "entry_price": 101.0, "stop_price": 95.0}
        hit = find_exit(self.ohlcv, pos, None, [["2026-01-10", "amc"]])
        self.assertTrue(hit["earnings"])
        self.assertEqual(hit["exit_date"], "2026-01-10")

    def test_anstehender_verkauf_wird_am_verkaufstag_gemeldet(self):
        hit = find_exit(self.ohlcv, self.pos, None, [["2026-01-21", "amc"]], today="2026-01-21")
        self.assertTrue(hit["pending"])
        self.assertEqual(hit["exit_date"], "2026-01-21")
        self.assertIsNone(find_exit(self.ohlcv, self.pos, None, [["2026-01-21", "amc"]], today="2026-01-20"))


class TestVerbrauchtesStoppTief(unittest.TestCase):
    """Stopp-Tief, das schon vor dem Kauf per Schluss unterschritten war, zählt nicht — es gilt
    das tiefste Tief seit dem Bruch, live (gws_core.swing_low_stop) wie im Backtest
    (recentSwingLowOf in frontend/backtest_logic.js). NFLX-Kauf 27.09.2017."""

    BARS = [bar("2017-09-18", 18.36, 18.55, 18.27, 18.46), bar("2017-09-19", 18.50, 18.62, 18.42, 18.57),
            bar("2017-09-20", 18.61, 18.65, 18.32, 18.55), bar("2017-09-21", 18.58, 19.00, 18.45, 18.88),
            bar("2017-09-22", 18.84, 18.98, 18.64, 18.73), bar("2017-09-25", 18.65, 18.66, 17.77, 17.86),
            bar("2017-09-26", 18.07, 18.09, 17.66, 17.94)]

    def js_stop(self, bars):
        import json, subprocess
        snippet = ("const fs = require('fs'), vm = require('vm');"
                   "vm.runInThisContext(fs.readFileSync('frontend/backtest_logic.js', 'utf8'));"
                   f"console.log(JSON.stringify(recentSwingLowOf({json.dumps(bars)})));")
        return json.loads(subprocess.run(["node", "-e", snippet], capture_output=True, text=True, check=True).stdout)

    def test_nflx_2017_tiefstes_tief_seit_dem_bruch(self):
        from gws_core import swing_low_stop
        self.assertAlmostEqual(swing_low_stop(self.BARS), 17.66 * 0.99, places=4)
        self.assertAlmostEqual(self.js_stop(self.BARS), 17.66, places=4)

    def test_ungebrochenes_swing_tief_bleibt(self):
        from gws_core import swing_low_stop
        bars = self.BARS[:5]
        self.assertAlmostEqual(swing_low_stop(bars), 18.32 * 0.99, places=4)
        self.assertAlmostEqual(self.js_stop(bars), 18.32, places=4)

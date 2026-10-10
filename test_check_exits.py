"""test_check_exits.py — Regressionstests für die Verkaufssignale.

Läuft ohne Netzwerk:  python3 -m unittest test_check_exits

Geprüft wird die Regel aus frontend/backtest_logic.js: Signal am Tagesschluss
(Struktur gebrochen und Schluss unter dem letzten Swing-Tief, oder Schluss unter
dem Stopp), Ausführung zur Eröffnung des Folgetages.
"""
import unittest

from check_exits import collect_new_positions, derive_entry, find_exit


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

    def test_einstieg_ist_die_eroeffnung_des_folgetages(self):
        rows = rising(40)
        entry = derive_entry(rows, "2026-01-20")
        self.assertEqual(entry["entry_date"], "2026-01-21")
        self.assertAlmostEqual(entry["entry_price"], rows[20]["o"])

    def test_stopp_liegt_unter_dem_einstieg(self):
        entry = derive_entry(rising(40), "2026-01-20")
        self.assertLess(entry["stop_price"], entry["entry_price"])

    def test_ohne_folgetag_kein_einstieg(self):
        rows = rising(40)
        self.assertIsNone(derive_entry(rows, rows[-1]["d"]))


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

    def test_meldet_signal_ohne_folgetag_als_wartend(self):
        signals = {"MU": [{"signal_date": self.market["MU"]["ohlcv"][-1]["d"],
                           "trigger_tf": "4h", "source": "QQQ"}]}
        positions = {}
        opened, pending = collect_new_positions({"MU"}, self.market, signals, positions, {})
        self.assertEqual(opened, [])
        self.assertEqual(len(pending), 1)


if __name__ == "__main__":
    unittest.main()


class TestZeitstoppUndSL(unittest.TestCase):
    """Zeitstopp (10 Handelstage, mind. +5 %), wirksamer SL und Modell-Depot (10 Plätze)."""

    def test_zeitstopp_wenn_nach_10_tagen_unter_plus_5_prozent(self):
        rows = rising(31) + [bar(f"2026-02-{d:02d}", 131.0, 132.0, 130.0, 131.0) for d in range(1, 13)]
        pos = {"entry_date": rows[30]["d"], "entry_price": rows[30]["o"], "stop_price": 90.0}
        hit = find_exit(rows, pos, None)
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
        self.assertIn(kind, ("Stopp", "letztes Swing-Tief"))

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

"""
Rekonstruiert, welche Breakout-Alerts tatsächlich per Mail/Telegram verschickt
wurden — Grundlage der echten Live-Bilanz (live_alerts/evaluate_alerts.js).

check_alerts.py protokolliert jeden neuen Alert in data/signals.json, meldet
aber nur Titel, die in dem Moment in den Top 20 der RS-Datei standen
(data['top20']). Dieses Feld steht nicht im Protokoll, darum wird es aus der
Git-Historie gelesen: für jeden Alert der Stand von rs_full.json bzw.
rs_sp500.json, der zum Zeitpunkt des Commits galt, mit dem der Alert ins
Protokoll kam.

Einträge, die schon im ersten Commit von signals.json standen (nachgetragene
Alerts vor Mitte Mai 2026), haben keinen Versandzeitpunkt. Für sie gilt der
älteste verfügbare Stand der RS-Datei und darin die Top-20-Historie des
Signaltags — als Näherung gekennzeichnet (basis = "naeherung").

Neue Alerts tragen in_top20 inzwischen selbst (check_alerts.py); dann gilt
dieser Wert (basis = "protokoll").

Voraussetzung: vollständige Git-Historie (Checkout mit fetch-depth: 0).
Ausgabe: data/live_alerts.json
"""
import bisect
import json
import os
import subprocess
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS = "data/signals.json"
RS_FILES = {"QQQ": "data/rs_full.json", "SPX": "data/rs_sp500.json"}
OUT_FILE = os.path.join(_REPO, "data", "live_alerts.json")
SOURCE_ORDER = {"QQQ": 0, "SPX": 1}          # check_alerts dedupliziert QQQ vor SPX


def git(*args):
    return subprocess.run(["git", *args], cwd=_REPO, check=True,
                          capture_output=True, text=True).stdout


def history(path):
    """[(zeit_utc_iso, commit), ...] aufsteigend."""
    out = []
    for line in git("log", "--reverse", "--format=%H %cI", "--", path).splitlines():
        sha, ts = line.split(" ", 1)
        out.append((datetime.fromisoformat(ts).astimezone(timezone.utc).isoformat(), sha))
    return out


def load_at(sha, path):
    return json.loads(git("show", f"{sha}:{path}"))


_top20_cache = {}


def top20_at(sha, path):
    """Nur die Top-20-Liste eines Stands merken — die RS-Dateien sind groß."""
    key = (sha, path)
    if key not in _top20_cache:
        _top20_cache[key] = set(load_at(sha, path).get("top20", []))
    return _top20_cache[key]


def version_at(hist, when):
    """Letzter Commit mit Zeit <= when, sonst None."""
    times = [t for t, _ in hist]
    i = bisect.bisect_right(times, when) - 1
    return hist[i][1] if i >= 0 else None


def alert_key(ticker, e):
    return (ticker, e.get("signal_date"), e.get("source"), e.get("trigger_tf"))


def collect_alerts():
    """Alle Alerts mit dem Zeitpunkt, zu dem sie ins Protokoll kamen."""
    seen, alerts = set(), []
    commits = history(SIGNALS)
    for n, (when, sha) in enumerate(commits):
        for ticker, entries in load_at(sha, SIGNALS).items():
            for e in entries:
                key = alert_key(ticker, e)
                if key in seen or not e.get("signal_date"):
                    continue
                seen.add(key)
                alerts.append({"ticker": ticker, **e, "logged_at": when if n > 0 else None})
    return alerts


def top20_for(alert, rs_hist):
    if alert.get("in_top20") is not None:
        return bool(alert["in_top20"]), "protokoll"
    hist = rs_hist.get(alert["source"])         # DAX wurde im Sept. 2026 entfernt
    if not hist:
        return None, "unbekannt"
    if alert["logged_at"]:
        sha = version_at(hist, alert["logged_at"])
        if sha:
            return alert["ticker"] in top20_at(sha, RS_FILES[alert["source"]]), "git"
    # Nachgetragen: ältester Stand, Top-20-Historie des Signaltags (Näherung)
    oldest = oldest_history(hist[0][1], RS_FILES[alert["source"]])
    day = alert["signal_date"]
    days = sorted(d for d in oldest if d <= day)
    if not days:
        return None, "unbekannt"
    return alert["ticker"] in oldest[days[-1]], "naeherung"


_oldest_cache = {}


def oldest_history(sha, path):
    if path not in _oldest_cache:
        _oldest_cache[path] = load_at(sha, path).get("top20_history", {})
    return _oldest_cache[path]


def main():
    rs_hist = {src: history(path) for src, path in RS_FILES.items()}
    alerts = collect_alerts()
    for a in alerts:
        a["in_top20"], a["basis"] = top20_for(a, rs_hist)
    # check_alerts meldet je Ticker und Tag nur eine Quelle (QQQ vor SPX)
    alerts.sort(key=lambda a: (a["signal_date"], a["ticker"], SOURCE_ORDER.get(a["source"], 9)))
    sent, done = [], set()
    for a in alerts:
        a["sent"] = bool(a["in_top20"]) and (a["ticker"], a["signal_date"]) not in done
        if a["sent"]:
            done.add((a["ticker"], a["signal_date"]))
            sent.append(a)
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "note": "sent = per Mail/Telegram verschickt (Top 20 zum Versandzeitpunkt); "
                "basis: protokoll | git | naeherung (vor Mitte Mai 2026 nachgetragen)",
        "alerts": alerts,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    by_basis = {}
    for a in sent:
        by_basis[a["basis"]] = by_basis.get(a["basis"], 0) + 1
    print(f"{len(alerts)} Alerts protokolliert, {len(sent)} verschickt ({by_basis}) → {OUT_FILE}")


if __name__ == "__main__":
    main()

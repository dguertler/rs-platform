"""
check_alerts_4h.py — Breakout-Prüfung direkt nach dem Schluss einer 4H-Kerze

Die 4H-Kerzen laufen wie bei TradingView ab 10, 14, 18 und 22 Uhr Berliner
Zeit (4–8, 8–12, 12–16, 16–20 Uhr New York). Gekauft werden kann von 10:00 bis
22:10 Uhr. Dieser Job prüft kurz nach dem Schluss der Kerzen 10–14 Uhr und
14–18 Uhr, ob die Top-20-Titel jetzt 3 von 3 Punkten haben und der 4H-Punkt
mit genau dieser Kerze neu hinzugekommen ist — dann kommt sofort die Kaufmail
(Kauf zur nächsten 4H-Kerze, also noch am selben Tag). Kerzen, die um 22 bzw.
2 Uhr schließen, meldet weiter der Nachtlauf (check_alerts.py, Kauf ab 10 Uhr).

Punkte zeitpunktgenau: Wochen- und Tageskerze enthalten nur den Handel bis
jetzt (Studie 10/2026: Signale an jedem Kerzenschluss, Kauf zur nächsten
Kerze — PF 1,72 → 1,94 gegenüber Kauf am nächsten Tag).

Doppelte Meldungen verhindert data/intraday_alert_state.json (je Kerze nur
ein Lauf) und alerts_state.json (der Nachtlauf sieht den Titel schon mit 3
Punkten und dem gemeldeten 4H-Ausbruch und meldet ihn nicht noch einmal).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_exits                                                     # noqa: E402
from alpaca_live import RECENT_DELAY, fetch_intraday                   # noqa: E402
from check_alerts import (_breakout_date, analyze_4h_structure, count_points,   # noqa: E402
                          load_signals, load_state, render_chart, save_signals,
                          save_state, send_alert_email, swing_low_stop)

BERLIN = ZoneInfo("Europe/Berlin")
ET = ZoneInfo("America/New_York")
RUN_STATE_FILE = os.path.join("data", "intraday_alert_state.json")
SOURCES = (("QQQ", "rs_full.json"), ("SPX", "rs_sp500.json"))
CHECK_BLOCKS = {4: "10–14 Uhr", 8: "14–18 Uhr"}   # ET-Beginn der Kerze → Berliner Zeit
MAX_AGE = timedelta(hours=3)                      # danach meldet der Nachtlauf


def bar_times(label):
    """Berliner Kerzenbeginn 'YYYY-MM-DD HH:MM' → (Beginn, Ende) als UTC-Zeit."""
    start = datetime.strptime(label, "%Y-%m-%d %H:%M").replace(tzinfo=BERLIN).astimezone(timezone.utc)
    return start, start + timedelta(hours=4)


def complete_bars(rows, now):
    """Nur Kerzen, deren Daten vollständig vorliegen (SIP 16 Minuten verzögert)."""
    return [r for r in rows if bar_times(r["d"])[1] <= now - RECENT_DELAY]


def week_start(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def with_today(entry, today_bar):
    """Tages- und Wochenkerzen um den Handel von heute bis jetzt ergänzen."""
    daily = [b for b in entry.get("ohlcv", []) if not today_bar or b["d"] < today_bar["d"]]
    weekly = [dict(b) for b in entry.get("ohlcv_w", [])]
    if today_bar:
        daily.append(today_bar)
        wk = week_start(today_bar["d"])
        if weekly and weekly[-1]["d"] == wk:
            last = weekly[-1]
            last.update(h=max(last["h"], today_bar["h"]), l=min(last["l"], today_bar["l"]), c=today_bar["c"])
        else:
            weekly.append({"d": wk, **{k: today_bar[k] for k in "ohlc"}})
    return daily, weekly


def evaluate(entry, intraday, now):
    """Signal an der zuletzt geschlossenen Kerze? Liefert (Kerze, info, Kerzen) oder None."""
    rows = complete_bars(intraday["h4"], now)
    if len(rows) < 10:
        return None
    last = rows[-1]
    start, end = bar_times(last["d"])
    if start.astimezone(ET).hour not in CHECK_BLOCKS or now - end > MAX_AGE:
        return None
    window = max(len(entry.get("ohlcv_4h") or []), 60)
    now_rows, prev_rows = rows[-window:], rows[:-1][-window:]
    daily, weekly = with_today(entry, intraday.get("today"))
    info = count_points({"ohlcv_w": weekly, "ohlcv": daily, "ohlcv_4h": now_rows})
    before = analyze_4h_structure(prev_rows)
    if info["points"] == 3 and info["h4"] and not (before and before.get("broken4h")):
        return last, info, {"w": weekly, "d": daily, "h4": now_rows}
    return None


def build_alert(entry, source, bar, info, series, today):
    ticker = entry["ticker"]
    before_today = [b for b in series["d"] if b["d"] < today]
    stop = swing_low_stop(before_today)
    price = series["h4"][-1]["c"]
    charts = []
    for key, title, struct, sl in (("w", "Weekly", "struct_w", None), ("d", "Daily", "struct_d", stop),
                                   ("h4", "4H", "struct_4h", stop)):
        s = info[struct]
        b64 = render_chart(series[key], ticker, f"{title} (letzten 60 Kerzen)",
                           gws_price=s["gws_price"] if s else None, n_candles=60, stop_price=sl)
        if b64:
            charts.append((b64, title))
    block = CHECK_BLOCKS[bar_times(bar["d"])[0].astimezone(ET).hour]
    return {
        "ticker": ticker, "score": entry.get("score", 0), "windows": entry.get("windows", {}),
        "info": info, "source": source, "charts": charts,
        "new_weekly": False, "new_daily": False, "new_h4": True,
        "weekly_bar_date": _breakout_date(series["w"], info["struct_w"]),
        "daily_bar_date": _breakout_date(series["d"], info["struct_d"]),
        "h4_bar_date": _breakout_date(series["h4"], info["struct_4h"]),
        "in_top20": True, "stop_price": stop, "rank": entry.get("prev_rank"),
        "entry_price": price, "entry_time": bar_times(bar["d"])[1].astimezone(BERLIN).strftime("%H:%M"),
        "buy_text": f"KAUF JETZT (4H-Kerze {block} geschlossen, Kurs ca. {price:.2f})",
        "h4_bar": bar["d"],
    }


def load_universe():
    """Top-20-Titel beider Indizes (NASDAQ-100 zuerst, wie im Nachtlauf)."""
    out = {}
    for source, path in SOURCES:
        payload = json.load(open(os.path.join("data", path)))
        top20 = set(payload.get("top20", []))
        for entry in payload.get("data", []):
            if entry["ticker"] in top20 and entry["ticker"] not in out:
                out[entry["ticker"]] = (source, entry)
    return out


def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(ET).strftime("%Y-%m-%d")
    run_state = check_exits.load_json(RUN_STATE_FILE, {})
    universe = load_universe()
    intraday = fetch_intraday(sorted(universe), today)
    if not intraday:
        print("Keine Alpaca-Kurse – Abbruch ohne Meldung.")
        return

    state, signals = load_state(), load_signals()
    alerted = state.setdefault("alerted", {})
    states = state.setdefault("states", {})
    done = set(run_state.get("processed", []))
    alerts, checked = [], set()
    for ticker, (source, entry) in sorted(universe.items()):
        if ticker not in intraday:
            continue
        hit = evaluate(entry, intraday[ticker], now)
        if not hit:
            continue
        bar, info, series = hit
        checked.add(bar["d"])
        if bar["d"] in done or alerted.get(ticker) == today:
            continue
        print(f"  ALERT {ticker} ({source}): 4H-Kerze {bar['d']} → 3 Punkte")
        alerts.append(build_alert(entry, source, bar, info, series, today))

    if alerts:
        market = check_exits.load_market_data()
        check_exits.depot_decisions(alerts, signals, market, today)
        for a in alerts:
            alerted[a["ticker"]] = today
            states[a["ticker"]] = {"points": 3, "weekly": True, "daily": True, "h4": True, "source": a["source"]}
            signals.setdefault(a["ticker"], []).append({
                "signal_date": today, "trigger_tf": "4h",
                "weekly_bar_date": a["weekly_bar_date"], "daily_bar_date": a["daily_bar_date"],
                "h4_bar_date": a["h4_bar_date"], "source": a["source"], "in_top20": True,
                "intraday_bar": a["h4_bar"], "entry_time": a["entry_time"], "entry_price": a["entry_price"],
            })
        save_signals(signals)
        save_state(state)
        smtp = [os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "ALERT_EMAIL_TO")]
        stamp = now.astimezone(BERLIN).strftime("%d.%m.%Y %H:%M")
        if all(smtp[i] for i in (0, 2, 3, 4)):
            send_alert_email(alerts, smtp[0], smtp[1] or "587", smtp[2], smtp[3], smtp[4],
                             subject_override=f"4H-Breakout {stamp}: {len(alerts)} Signal(e) – Kauf jetzt")
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if token:
            from telegram_handler import resolve_recipients, send_breakout_telegram
            recipients = resolve_recipients(os.environ.get("TELEGRAM_CHAT_ID", ""))
            for a in alerts:
                send_breakout_telegram(token, recipients, a)
    else:
        print("Keine neuen 4H-Breakouts an dieser Kerze.")

    run_state["processed"] = sorted(done | checked)[-20:]
    run_state["updated_at"] = now.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M")
    with open(RUN_STATE_FILE, "w") as f:
        json.dump(run_state, f, indent=1)


if __name__ == "__main__":
    main()

"""earnings_alert_log.py — persistenter Event-Log für gesendete Earnings-Alerts.

Wird von check_earnings_global.py und check_earnings_premarket.py nach jedem
Mailversand aufgerufen. Der Chat-Trigger `earning`/`earningsanalyse` (siehe
CLAUDE.md, Abschnitt "Earnings-Kandidaten-Check") liest diese Datei, um
ohne manuelle Ticker-Angabe zu wissen, welche Ticker seit dem letzten Lauf
gemeldet wurden. Der normale RS-Digest (check_earnings.py) läuft nicht mehr
automatisch (siehe earnings_alert.yml) und schreibt hier nicht mehr rein.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("data/earnings_alerts_log.json")


def already_logged(ticker: str, report_date: str, source: str) -> bool:
    """True, wenn (ticker, report_date, source) bereits im persistenten Log steht.

    Dient als tagesübergreifende Dedupe-Quelle für die Live-Alert-Workflows,
    deren rollierender Tages-Cache um Mitternacht UTC zurückgesetzt wird und
    daher allein keine verlässliche Auskunft über bereits gesendete Alerts
    für ältere Earnings-Termine geben kann."""
    try:
        existing = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return any(
        e["ticker"] == ticker and e["date"] == report_date and e["source"] == source
        for e in existing["alerts"]
    )


def append_alerts(alerts: list[dict], source: str, report_dates: dict[str, str]) -> bool:
    """Hängt neue Alert-Events an data/earnings_alerts_log.json an.

    report_dates: ticker -> Earnings-Datum (YYYY-MM-DD). Dedupliziert per
    (ticker, date, source). Gibt True zurück, wenn die Datei geändert wurde
    (Signal für den Commit-Schritt im Workflow)."""
    try:
        existing = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        existing = {"alerts": []}

    seen = {(e["ticker"], e["date"], e["source"]) for e in existing["alerts"]}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = False

    for alert in alerts:
        ticker = alert["ticker"]
        report_date = report_dates.get(ticker, now[:10])
        key = (ticker, report_date, source)
        if key in seen:
            continue
        existing["alerts"].append({
            "ticker":       ticker,
            "date":         report_date,
            "source":       source,
            "jump_pct":     alert.get("jump_pct"),
            "surprise_pct": alert.get("surprise_pct"),
            "eps_actual":   alert.get("eps_actual"),
            "eps_estimate": alert.get("eps_estimate"),
            # "eps-beat" | "kursreaktion" — steuert im Screening, ob die
            # EPS-Surprise überhaupt als Signal taugt (siehe earnings_gate.py)
            "trigger":      alert.get("trigger"),
            "eps_distorted": alert.get("eps_distorted", False),
            "detected_at":  now,
        })
        seen.add(key)
        changed = True

    if changed:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return changed

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json, os, re, sys, asyncio, urllib.request
from pathlib import Path

# Repo-Root in den Importpfad, damit telegram_handler (Charts-Versand) nutzbar ist
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from auth import (
    init_db, get_user, verify_password, create_token, decode_token,
    get_user_plan, set_user_plan, downgrade_by_customer,
    check_is_admin, set_admin, set_active, change_password,
    create_reset_token, use_reset_token, get_all_users, create_user,
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_telegram_chat_id, set_telegram_chat_id, get_all_telegram_chat_ids,
    get_telegram_recipients_with_email,
    create_tg_link_token, link_telegram_by_token,
)
from news_handler import fetch_news
from stripe_handler import create_checkout_session, parse_webhook
from email_handler import send_reset_email
from gws_analysis import struct_for_entry

app = FastAPI(title="RS Platform")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

DATA_DIR     = Path(os.getenv("DATA_DIR", r"C:\Users\danie\Rel.-Strength"))
MARKET_FILES = {"nasdaq": "rs_full.json", "sp500": "rs_sp500.json", "dax": "rs_dax.json", "smallcap": "rs_smallcap.json"}
PRO_MARKETS  = set()
FREE_LIMIT   = 20
security     = HTTPBearer()

# Per-market cache: {market: {mtime, payload, arr}}
_rs_cache: dict = {}


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_market_cache(market: str):
    """Load, cache, and return {payload, arr} for a market. Reloads when file changes."""
    path = DATA_DIR / MARKET_FILES[market]
    if not path.exists():
        raise HTTPException(503, "Datendatei noch nicht vorhanden")
    ratings_path = DATA_DIR / "ratings" / "index.json"
    mtime = path.stat().st_mtime
    rmtime = ratings_path.stat().st_mtime if ratings_path.exists() else 0
    cache_key = (mtime, rmtime)
    cached = _rs_cache.get(market)
    if cached and cached.get("cache_key") == cache_key:
        return cached
    raw = _load(path)
    arr = raw if isinstance(raw, list) else raw.get("data", [])
    last_date = ""
    for entry in arr:
        ohlcv = entry.get("ohlcv", [])
        if ohlcv:
            d = ohlcv[-1].get("d", "")
            if d > last_date:
                last_date = d
    ratings_map = {}
    if ratings_path.exists():
        try:
            for r in _load(ratings_path).get("ratings", []):
                ratings_map[r["ticker"].upper()] = r
        except Exception:
            pass
    stripped = []
    for entry in arr:
        s = {k: v for k, v in entry.items() if k not in ("ohlcv_w", "ohlcv", "ohlcv_4h")}
        s["struct"] = struct_for_entry(entry)
        s["has_ohlcv"] = bool(entry.get("ohlcv"))
        t = entry.get("ticker", "").upper()
        s["rating"] = ratings_map.get(t) or ratings_map.get(t.split(".")[0])
        stripped.append(s)
    payload = {
        "timestamp": last_date or (raw.get("timestamp", "–") if not isinstance(raw, list) else "–"),
        "benchmark": raw.get("benchmark", "QQQ") if not isinstance(raw, list) else "QQQ",
        "benchmark_ohlcv_w": raw.get("benchmark_ohlcv_w", []) if not isinstance(raw, list) else [],
        "benchmark_ohlcv":   raw.get("benchmark_ohlcv",   []) if not isinstance(raw, list) else [],
        "data": stripped,
    }
    _rs_cache[market] = {"cache_key": cache_key, "payload": payload, "arr": arr}
    return _rs_cache[market]


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    email = decode_token(credentials.credentials)
    if not email:
        raise HTTPException(401, "Token ungueltig oder abgelaufen")
    return email


def require_admin(email: str = Depends(require_auth)) -> str:
    if not check_is_admin(email):
        raise HTTPException(403, "Kein Admin-Zugriff")
    return email


class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotRequest(BaseModel):
    email: str

class ResetRequest(BaseModel):
    token: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class AdminCreateUser(BaseModel):
    email: str
    password: str
    plan: str = "free"
    is_admin: bool = False

class AdminPatchUser(BaseModel):
    plan: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None
    new_password: str | None = None

class WatchlistAddRequest(BaseModel):
    ticker: str

class TelegramRequest(BaseModel):
    chat_id: str


# ── Telegram-Hilfsfunktionen ──────────────────────────────────────────────────

ALERT_API_KEY      = os.environ.get("ALERT_API_KEY", "")
# Gültigkeit der Auto-Login-Tokens in den Telegram-Deep-Links (Stunden).
# Bewusst kürzer als die normale Session (7 Tage), da der Token im Chat steht.
MAGIC_LINK_EXPIRE_HOURS = int(os.environ.get("MAGIC_LINK_EXPIRE_HOURS", "72"))
# Mögliche Env-Namen für den Bot-Token (erster gefundener gewinnt)
_TG_TOKEN_NAMES    = ("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TG_BOT_TOKEN")
_bot_info: dict    = {}   # Cache für getMe


def _telegram_token() -> str:
    for name in _TG_TOKEN_NAMES:
        v = os.environ.get(name)
        if v:
            return v
    return ""


def _telegram_api(method: str, payload: dict, timeout: int = 15) -> tuple[bool, dict]:
    """Ruft eine Telegram-Bot-API-Methode auf. Gibt (ok, result_or_error)."""
    token = _telegram_token()
    if not token:
        return False, {"description": "Backend hat keinen Telegram-Token konfiguriert."}
    url  = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            return True, result.get("result", {})
        return False, {"description": result.get("description", "Telegram-Fehler")}
    except Exception as e:
        return False, {"description": str(e)}


def _telegram_send(chat_id: str, text: str) -> tuple[bool, str]:
    ok, res = _telegram_api("sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
    })
    return ok, ("" if ok else res.get("description", "Fehler"))


def _bot_username() -> str:
    """Ermittelt den Bot-Benutzernamen via getMe (gecached)."""
    if "username" in _bot_info:
        return _bot_info["username"]
    username = ""
    if _telegram_token():
        ok, res = _telegram_api("getMe", {})
        if ok:
            username = res.get("username", "")
    _bot_info["username"] = username
    return username


def _set_telegram_webhook() -> None:
    """Registriert den Webhook beim Hochfahren – idempotent.
    Basis-URL aus APP_URL bzw. FRONTEND_URL."""
    base = (os.environ.get("APP_URL") or os.environ.get("FRONTEND_URL") or "").rstrip("/")
    if not _telegram_token() or not base:
        return
    payload = {
        "url": f"{base}/api/telegram/webhook",
        "allowed_updates": ["message"],
    }
    if ALERT_API_KEY:
        payload["secret_token"] = ALERT_API_KEY
    ok, res = _telegram_api("setWebhook", payload)
    print(f"[Telegram] setWebhook → {base}/api/telegram/webhook : "
          f"{'OK' if ok else res.get('description')}")


# Verzögerung, bis die letzten Breakout-Alerts nach dem Willkommenstext kommen
WELCOME_ALERTS_DELAY = 5


def _last_breakout_batch() -> dict | None:
    """Lädt die zuletzt verschickte Breakout-Charge (von check_alerts.py)."""
    path = DATA_DIR / "last_breakout_alerts.json"
    if not path.exists():
        return None
    try:
        return _load(path)
    except Exception:
        return None


def _welcome_payload() -> tuple[str, list, str]:
    """Baut den Willkommenstext + liefert die nachzureichenden Alerts und das
    Datum der letzten Charge."""
    batch  = _last_breakout_batch()
    alerts = (batch or {}).get("alerts") or []
    when   = (batch or {}).get("sent_at_label") or (batch or {}).get("date_label") or ""
    if alerts:
        welcome = (
            "✅ <b>RS-Platform</b> verbunden!\n"
            "Du erhältst ab jetzt Breakout-, 4H- und Earnings-Alerts hier im Chat.\n\n"
            f"📨 Gleich bekommst du die <b>letzten Breakout-Alerts</b> "
            f"(Stand: {when}) nachgereicht."
        )
    else:
        welcome = (
            "✅ <b>RS-Platform</b> verbunden!\n"
            "Du erhältst ab jetzt Breakout-, 4H- und Earnings-Alerts hier im Chat.\n"
            "Aktuell liegen keine vergangenen Breakout-Alerts vor – du bekommst die "
            "nächsten automatisch, sobald sie auftreten."
        )
    return welcome, alerts, when


async def _replay_last_alerts(chat_id: str, alerts: list, when: str) -> None:
    """Reicht 30 s später die zuletzt verschickte Breakout-Charge nach."""
    if not alerts:
        return
    await asyncio.sleep(WELCOME_ALERTS_DELAY)
    await asyncio.to_thread(
        _telegram_send, chat_id,
        f"📨 <b>Letzte Breakout-Alerts</b> (Stand: {when}):",
    )
    token = _telegram_token()
    try:
        from telegram_handler import send_breakout_telegram
        for alert in alerts:
            await asyncio.to_thread(send_breakout_telegram, token, [chat_id], alert)
    except Exception as e:
        print(f"[Telegram] Nachreichung der letzten Alerts fehlgeschlagen: {e}")


async def _welcome_and_replay(chat_id: str) -> None:
    """Einmaliger Willkommenstext nach dem Verbinden; danach Nachreichung."""
    welcome, alerts, when = _welcome_payload()
    await asyncio.to_thread(_telegram_send, chat_id, welcome)
    await _replay_last_alerts(chat_id, alerts, when)


@app.on_event("startup")
async def startup():
    init_db()
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_password and not get_all_users():
        create_user(admin_email, admin_password)
        set_admin(admin_email, True)
        set_user_plan(admin_email, "pro")
    import asyncio
    async def _warm():
        for market in MARKET_FILES:
            path = DATA_DIR / MARKET_FILES[market]
            if path.exists():
                try:
                    await asyncio.to_thread(_get_market_cache, market)
                except Exception:
                    pass
    asyncio.create_task(_warm())
    # Telegram-Webhook für den Ein-Klick-Flow registrieren (idempotent)
    asyncio.create_task(asyncio.to_thread(_set_telegram_webhook))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/debug/email-test")
async def debug_email():
    import smtplib
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    pw   = os.environ.get("SMTP_PASS", "")
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pw)
        return {"status": "ok", "host": host, "port": port, "user": user}
    except Exception as e:
        return {"status": "error", "error": str(e), "host": host, "port": port, "user": user}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = get_user(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "E-Mail oder Passwort falsch")
    return {"token": create_token(req.email), "email": req.email}


@app.post("/api/auth/forgot")
async def forgot(req: ForgotRequest, bg: BackgroundTasks):
    token = create_reset_token(req.email)
    if token:
        app_url = os.environ.get("APP_URL", "http://localhost:8000")
        url = f"{app_url}/reset.html?token={token}"
        bg.add_task(send_reset_email, req.email, url)
    return {"detail": "Wenn deine E-Mail registriert ist, wurde ein Reset-Link versandt."}



@app.post("/api/auth/reset")
async def reset_password(req: ResetRequest):
    if len(req.password) < 8:
        raise HTTPException(400, "Passwort muss mindestens 8 Zeichen lang sein")
    if not use_reset_token(req.token, req.password):
        raise HTTPException(400, "Token ungueltig oder abgelaufen")
    return {"detail": "Passwort erfolgreich geaendert"}


@app.get("/api/user/me")
async def me(email: str = Depends(require_auth)):
    return {
        "email": email,
        "plan": get_user_plan(email),
        "is_admin": check_is_admin(email),
        "telegram_chat_id": get_telegram_chat_id(email),
    }


@app.get("/api/telegram/info")
async def telegram_info():
    """Öffentliche Bot-Infos für die Anleitung im Frontend.
    Bot-Username wird automatisch via getMe aus dem Token ermittelt."""
    uname = _bot_username()
    return {
        "bot_username": uname,
        "bot_url": f"https://t.me/{uname}" if uname else "",
        "one_click": bool(uname),
    }


@app.post("/api/user/telegram/link")
async def telegram_link(email: str = Depends(require_auth)):
    """Liefert einen Deep-Link für den Ein-Klick-Flow. Der User tippt in
    Telegram nur auf Start – der Webhook verknüpft die Chat-ID automatisch."""
    uname = _bot_username()
    if not uname:
        raise HTTPException(503, "Telegram-Bot im Backend nicht konfiguriert.")
    token = create_tg_link_token(email)
    if not token:
        raise HTTPException(400, "Verknüpfung konnte nicht vorbereitet werden.")
    return {"url": f"https://t.me/{uname}?start={token}"}


@app.post("/api/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    """Empfängt Updates von Telegram. Bei '/start <token>' wird die Chat-ID
    automatisch mit dem User verknüpft."""
    if ALERT_API_KEY and x_telegram_bot_api_secret_token != ALERT_API_KEY:
        raise HTTPException(401, "Nicht autorisiert")
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat_id = str((msg.get("chat") or {}).get("id", "") or "")
    if not chat_id or not text.startswith("/start"):
        return {"ok": True}
    parts   = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    if payload:
        email = link_telegram_by_token(payload, chat_id)
        if email:
            # Willkommenstext + Nachreichung der letzten Alerts im Hintergrund,
            # damit der Webhook sofort antwortet.
            asyncio.create_task(_welcome_and_replay(chat_id))
            return {"ok": True}
    _telegram_send(
        chat_id,
        "Bitte starte die Verknüpfung über den Button "
        "<b>„Mit Telegram verbinden“</b> auf deiner Konto-Seite.",
    )
    return {"ok": True}


@app.post("/api/user/telegram")
async def save_telegram(req: TelegramRequest, email: str = Depends(require_auth)):
    """Hinterlegt die persönliche Telegram-Chat-ID. Sendet — wie der Button-
    Flow — den Willkommenstext zur Prüfung und reicht 30 s später die letzten
    Breakout-Alerts nach."""
    chat_id = req.chat_id.strip()
    if not re.fullmatch(r"-?\d{1,20}|@[A-Za-z0-9_]{4,40}", chat_id):
        raise HTTPException(400, "Ungültige Chat-ID. Erlaubt: Zahl (z. B. 123456789) "
                                 "oder @kanalname.")
    welcome, alerts, when = _welcome_payload()
    # Synchron senden, um die Chat-ID zu verifizieren.
    ok, err = await asyncio.to_thread(_telegram_send, chat_id, welcome)
    # Wenn das Backend einen Token hat und das Senden scheitert, ist die ID
    # falsch oder der Bot wurde noch nicht gestartet → nicht speichern.
    if _telegram_token() and not ok:
        raise HTTPException(
            400,
            f"Konnte keine Nachricht senden: {err}. Hast du den Bot gestartet "
            f"(/start) und die richtige Chat-ID eingetragen?",
        )
    set_telegram_chat_id(email, chat_id)
    if ok and alerts:
        asyncio.create_task(_replay_last_alerts(chat_id, alerts, when))
    return {"detail": "Telegram-Benachrichtigungen aktiviert.", "verified": ok}


@app.delete("/api/user/telegram")
async def delete_telegram(email: str = Depends(require_auth)):
    set_telegram_chat_id(email, None)
    return {"detail": "Telegram-Benachrichtigungen deaktiviert."}


@app.get("/api/telegram/recipients")
async def telegram_recipients(x_alert_key: str = Header(default="")):
    """Liefert alle registrierten Chat-IDs für den Alert-Versand.
    Geschützt durch den gemeinsamen ALERT_API_KEY (Header X-Alert-Key)."""
    if not ALERT_API_KEY or x_alert_key != ALERT_API_KEY:
        raise HTTPException(401, "Nicht autorisiert")
    # Pro Chat-ID einen kurzlebigen Auto-Login-Token mitliefern, damit der
    # Telegram-Button direkt in die Plattform führt (ohne erneutes Anmelden im
    # In-App-Browser). Tokens sind optional — fehlt einer, greift der normale
    # Login-Flow.
    tokens: dict[str, str] = {}
    for chat_id, email in get_telegram_recipients_with_email():
        if chat_id not in tokens:
            tokens[chat_id] = create_token(email, MAGIC_LINK_EXPIRE_HOURS)
    chat_ids = list(tokens.keys()) or get_all_telegram_chat_ids()
    return {"chat_ids": chat_ids, "tokens": tokens}


@app.post("/api/user/change-password")
async def user_change_password(req: ChangePasswordRequest, email: str = Depends(require_auth)):
    user = get_user(email)
    if not user or not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(401, "Aktuelles Passwort falsch")
    if len(req.new_password) < 8:
        raise HTTPException(400, "Neues Passwort muss mindestens 8 Zeichen lang sein")
    change_password(email, req.new_password)
    return {"detail": "Passwort geaendert"}


@app.get("/api/admin/users")
async def admin_list_users(_: str = Depends(require_admin)):
    return get_all_users()


@app.post("/api/admin/users")
async def admin_create_user(req: AdminCreateUser, _: str = Depends(require_admin)):
    if get_user(req.email):
        raise HTTPException(409, "E-Mail bereits vergeben")
    if len(req.password) < 8:
        raise HTTPException(400, "Passwort muss mindestens 8 Zeichen lang sein")
    create_user(req.email, req.password, int(req.is_admin))
    if req.plan != "free":
        set_user_plan(req.email, req.plan)
    return {"detail": f"User {req.email!r} angelegt"}


@app.patch("/api/admin/users/{target}")
async def admin_patch_user(target: str, req: AdminPatchUser, admin: str = Depends(require_admin)):
    if req.plan is not None:
        set_user_plan(target, req.plan)
    if req.is_admin is not None:
        if target == admin and not req.is_admin:
            raise HTTPException(400, "Du kannst dir selbst nicht die Admin-Rechte entziehen")
        set_admin(target, req.is_admin)
    if req.is_active is not None:
        set_active(target, req.is_active)
    if req.new_password:
        if len(req.new_password) < 8:
            raise HTTPException(400, "Passwort muss mindestens 8 Zeichen lang sein")
        change_password(target, req.new_password)
    return {"detail": "Gespeichert"}


@app.get("/api/rs/{market}")
async def get_rs(market: str, email: str = Depends(require_auth)):
    if market not in MARKET_FILES:
        raise HTTPException(404, f"Unbekannter Markt '{market}'")
    plan = get_user_plan(email)
    if market in PRO_MARKETS and plan != "pro":
        raise HTTPException(403, "DAX und S&P500 erfordern ein Pro-Abo")
    cache = _get_market_cache(market)
    return JSONResponse(content=cache["payload"])


@app.get("/api/rs/{market}/{ticker}")
async def get_rs_ticker(market: str, ticker: str, email: str = Depends(require_auth)):
    if market not in MARKET_FILES:
        raise HTTPException(404, f"Unbekannter Markt '{market}'")
    cache = _get_market_cache(market)
    for entry in cache["arr"]:
        if entry.get("ticker", "").upper() == ticker.upper():
            return JSONResponse(content={
                "ohlcv_w":  entry.get("ohlcv_w",  []),
                "ohlcv":    entry.get("ohlcv",    []),
                "ohlcv_4h": entry.get("ohlcv_4h", []),
            })
    raise HTTPException(404, f"Ticker '{ticker}' nicht gefunden")


@app.get("/api/alpha/candidates")
async def get_alpha_candidates(email: str = Depends(require_auth)):
    path = DATA_DIR / "alpha_candidates.json"
    if not path.exists():
        return JSONResponse(content={"updated_at": None, "profiles": {}})
    return JSONResponse(content=_load(path))


@app.get("/api/backtest/{ticker}")
async def get_backtest(ticker: str, email: str = Depends(require_auth)):
    if get_user_plan(email) != "pro":
        raise HTTPException(403, "Backtests erfordern ein Pro-Abo")
    safe = re.sub(r"[^a-z0-9]", "_", ticker.lower())
    path = DATA_DIR / f"backtest_{safe}.json"
    if not path.exists():
        raise HTTPException(404, f"Keine Backtest-Daten fuer '{ticker}'")
    return JSONResponse(content=_load(path))


@app.get("/api/signals")
async def get_signals(email: str = Depends(require_auth)):
    if get_user_plan(email) != "pro":
        raise HTTPException(403, "Signals erfordern ein Pro-Abo")
    path = DATA_DIR / "signals.json"
    if not path.exists():
        return JSONResponse(content={})
    return JSONResponse(content=_load(path))


@app.get("/api/ratings")
async def get_ratings(email: str = Depends(require_auth)):
    path = DATA_DIR / "ratings" / "index.json"
    if not path.exists():
        return JSONResponse(content={"ratings": []})
    return JSONResponse(content=_load(path))


@app.get("/api/ratings/{ticker}/html")
async def get_rating_html(ticker: str, email: str = Depends(require_auth)):
    from fastapi.responses import HTMLResponse
    safe = re.sub(r"[^a-z0-9]", "_", ticker.lower())
    path = DATA_DIR / "ratings" / f"{safe}.html"
    if not path.exists():
        raise HTTPException(404, f"Keine Bewertung für '{ticker}' vorhanden")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


def _find_ticker_in_markets(ticker: str) -> list[dict]:
    """Search all market JSON files for ticker, return list of {name, rank, in_top20, data}."""
    results = []
    for market, filename in MARKET_FILES.items():
        path = DATA_DIR / filename
        if not path.exists():
            continue
        try:
            market_data = _load(path)
            arr = market_data if isinstance(market_data, list) else market_data.get("data", [])
            for idx, entry in enumerate(arr):
                if entry.get("ticker", "").upper() == ticker.upper():
                    results.append({
                        "market": market,
                        "rank": idx + 1,
                        "in_top20": idx < 20,
                        "entry": entry,
                        "benchmark": market_data.get("benchmark", "QQQ") if not isinstance(market_data, list) else "QQQ",
                        "benchmark_ohlcv_w": market_data.get("benchmark_ohlcv_w", []) if not isinstance(market_data, list) else [],
                        "benchmark_ohlcv": market_data.get("benchmark_ohlcv", []) if not isinstance(market_data, list) else [],
                    })
                    break
        except Exception:
            continue
    return results


@app.get("/api/watchlist")
async def get_user_watchlist(email: str = Depends(require_auth)):
    tickers = get_watchlist(email)
    items = []
    for ticker in tickers:
        market_hits = _find_ticker_in_markets(ticker)
        if not market_hits:
            # Ticker not found in any market data – include with minimal info
            items.append({
                "ticker": ticker.upper(),
                "markets": [],
                "score": None,
                "windows": {},
                "prev_rank": None,
                "ohlcv_w": [],
                "ohlcv": [],
                "ohlcv_4h": [],
                "benchmark": "QQQ",
                "benchmark_ohlcv_w": [],
                "benchmark_ohlcv": [],
            })
            continue
        # Use first found market for chart data
        primary = market_hits[0]
        entry = primary["entry"]
        items.append({
            "ticker": ticker.upper(),
            "markets": [{"name": h["market"], "rank": h["rank"], "in_top20": h["in_top20"]} for h in market_hits],
            "score": entry.get("score"),
            "windows": entry.get("windows", {}),
            "prev_rank": entry.get("prev_rank"),
            "new_since": entry.get("new_since"),
            "ohlcv_w": entry.get("ohlcv_w", []),
            "ohlcv": entry.get("ohlcv", []),
            "ohlcv_4h": entry.get("ohlcv_4h", []),
            "benchmark": primary["benchmark"],
            "benchmark_ohlcv_w": primary["benchmark_ohlcv_w"],
            "benchmark_ohlcv": primary["benchmark_ohlcv"],
        })
    return JSONResponse(content={"items": items})


@app.post("/api/watchlist")
async def add_watchlist_ticker(req: WatchlistAddRequest, email: str = Depends(require_auth)):
    ticker = req.ticker.strip().upper()
    if not ticker or len(ticker) > 12:
        raise HTTPException(400, "Ungültiger Ticker")
    added = add_to_watchlist(email, ticker)
    if not added:
        raise HTTPException(409, f"{ticker} ist bereits in deiner Watchlist")
    return {"detail": f"{ticker} zur Watchlist hinzugefügt"}


@app.delete("/api/watchlist/{ticker}")
async def remove_watchlist_ticker(ticker: str, email: str = Depends(require_auth)):
    remove_from_watchlist(email, ticker)
    return {"detail": f"{ticker} aus Watchlist entfernt"}


@app.get("/api/watchlist/news/{ticker}")
async def get_watchlist_news(ticker: str, email: str = Depends(require_auth)):
    news = fetch_news(ticker.upper())
    return JSONResponse(content=news)


@app.get("/api/stripe/checkout")
async def checkout(email: str = Depends(require_auth)):
    return {"url": create_checkout_session(email)}


@app.post("/api/stripe/webhook")
async def webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = parse_webhook(payload, sig)
    except Exception as e:
        raise HTTPException(400, str(e))
    t = event["type"]
    if t == "checkout.session.completed":
        obj = event["data"]["object"]
        set_user_plan(obj["customer_email"], "pro", obj.get("customer"))
    elif t in ("customer.subscription.deleted", "customer.subscription.paused"):
        cid = event["data"]["object"].get("customer")
        if cid:
            downgrade_by_customer(cid)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "data_dir_exists": DATA_DIR.exists()}


_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="static")

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json, os, re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from auth import (
    init_db, get_user, verify_password, create_token, decode_token,
    get_user_plan, set_user_plan, downgrade_by_customer,
    check_is_admin, set_admin, set_active, change_password,
    create_reset_token, use_reset_token, get_all_users, create_user,
)
from stripe_handler import create_checkout_session, parse_webhook
from email_handler import send_reset_email

app = FastAPI(title="RS Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

DATA_DIR     = Path(os.getenv("DATA_DIR", r"C:\Users\danie\Rel.-Strength"))
MARKET_FILES = {"nasdaq": "rs_full.json", "sp500": "rs_sp500.json", "dax": "rs_dax.json"}
PRO_MARKETS  = set()
FREE_LIMIT   = 20
security     = HTTPBearer()


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


@app.on_event("startup")
async def startup():
    init_db()
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_password and not get_all_users():
        create_user(admin_email, admin_password)
        set_admin(admin_email, True)
        set_user_plan(admin_email, "pro")


@app.get("/health")
async def health():
    return {"status": "ok"}


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
    return {"email": email, "plan": get_user_plan(email), "is_admin": check_is_admin(email)}


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
    path = DATA_DIR / MARKET_FILES[market]
    if not path.exists():
        raise HTTPException(503, "Datendatei noch nicht vorhanden")
    data = _load(path)
    return JSONResponse(content=data)


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

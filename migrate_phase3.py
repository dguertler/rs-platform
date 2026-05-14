"""Phase 3 Migration: Stripe + Free/Pro Tiers"""
import os, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

# ── .env.example ──────────────────────────────────────────────────────────────
(ROOT / ".env.example").write_text(
    "SECRET_KEY=change-me-use-openssl-rand-hex-32\n"
    "STRIPE_SECRET_KEY=sk_test_...\n"
    "STRIPE_WEBHOOK_SECRET=whsec_...\n"
    "STRIPE_PRICE_ID=price_...\n"
    "APP_URL=http://localhost:8000\n",
    encoding="utf-8",
)
print("wrote .env.example")

# ── stripe_handler.py ─────────────────────────────────────────────────────────
(BACKEND / "stripe_handler.py").write_text(
    "import os\n"
    "import stripe\n\n"
    "stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')\n\n\n"
    "def create_checkout_session(email: str) -> str:\n"
    "    price_id = os.environ.get('STRIPE_PRICE_ID', '')\n"
    "    app_url  = os.environ.get('APP_URL', 'http://localhost:8000')\n"
    "    session  = stripe.checkout.Session.create(\n"
    "        customer_email=email,\n"
    "        payment_method_types=['card'],\n"
    "        line_items=[{'price': price_id, 'quantity': 1}],\n"
    "        mode='subscription',\n"
    "        success_url=app_url + '/?upgraded=1',\n"
    "        cancel_url=app_url + '/',\n"
    "    )\n"
    "    return session.url\n\n\n"
    "def parse_webhook(payload: bytes, sig: str):\n"
    "    secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')\n"
    "    return stripe.Webhook.construct_event(payload, sig, secret)\n",
    encoding="utf-8",
)
print("wrote backend/stripe_handler.py")

# ── auth.py ───────────────────────────────────────────────────────────────────
(BACKEND / "auth.py").write_text(
    "from datetime import datetime, timedelta\n"
    "from pathlib import Path\n"
    "import os, sqlite3\n\n"
    "from jose import JWTError, jwt\n"
    "from passlib.context import CryptContext\n\n"
    "SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE-ME-use-openssl-rand-hex-32')\n"
    "ALGORITHM = 'HS256'\n"
    "TOKEN_EXPIRE_HOURS = 24 * 7\n\n"
    "pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')\n"
    "DB_PATH = Path(__file__).parent / 'users.db'\n\n\n"
    "def init_db() -> None:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        conn.execute(\"\"\"\n"
    "            CREATE TABLE IF NOT EXISTS users (\n"
    "                id                 INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "                email              TEXT    UNIQUE NOT NULL,\n"
    "                password_hash      TEXT    NOT NULL,\n"
    "                plan               TEXT    DEFAULT 'free',\n"
    "                stripe_customer_id TEXT,\n"
    "                is_active          INTEGER DEFAULT 1,\n"
    "                created_at         TEXT    DEFAULT CURRENT_TIMESTAMP\n"
    "            )\n"
    "        \"\"\")\n"
    "        # migrate existing DB\n"
    "        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)')}\n"
    "        if 'plan' not in cols:\n"
    "            conn.execute(\"ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'\")\n"
    "        if 'stripe_customer_id' not in cols:\n"
    "            conn.execute('ALTER TABLE users ADD COLUMN stripe_customer_id TEXT')\n\n\n"
    "def get_user(email: str) -> dict | None:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        conn.row_factory = sqlite3.Row\n"
    "        row = conn.execute(\n"
    "            'SELECT * FROM users WHERE email = ? AND is_active = 1', (email,)\n"
    "        ).fetchone()\n"
    "    return dict(row) if row else None\n\n\n"
    "def create_user(email: str, password: str) -> None:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        conn.execute(\n"
    "            'INSERT INTO users (email, password_hash) VALUES (?, ?)',\n"
    "            (email, pwd_context.hash(password)),\n"
    "        )\n\n\n"
    "def get_user_plan(email: str) -> str:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        row = conn.execute(\n"
    "            'SELECT plan FROM users WHERE email = ? AND is_active = 1', (email,)\n"
    "        ).fetchone()\n"
    "    return (row[0] if row else None) or 'free'\n\n\n"
    "def set_user_plan(email: str, plan: str, customer_id: str | None = None) -> None:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        if customer_id:\n"
    "            conn.execute(\n"
    "                'UPDATE users SET plan=?, stripe_customer_id=? WHERE email=?',\n"
    "                (plan, customer_id, email),\n"
    "            )\n"
    "        else:\n"
    "            conn.execute('UPDATE users SET plan=? WHERE email=?', (plan, email))\n\n\n"
    "def downgrade_by_customer(customer_id: str) -> None:\n"
    "    with sqlite3.connect(DB_PATH) as conn:\n"
    "        conn.execute(\n"
    "            \"UPDATE users SET plan='free' WHERE stripe_customer_id=?\",\n"
    "            (customer_id,),\n"
    "        )\n\n\n"
    "def verify_password(plain: str, hashed: str) -> bool:\n"
    "    return pwd_context.verify(plain, hashed)\n\n\n"
    "def create_token(email: str) -> str:\n"
    "    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)\n"
    "    return jwt.encode({'sub': email, 'exp': expire}, SECRET_KEY, algorithm=ALGORITHM)\n\n\n"
    "def decode_token(token: str) -> str | None:\n"
    "    try:\n"
    "        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])\n"
    "        return payload.get('sub')\n"
    "    except JWTError:\n"
    "        return None\n",
    encoding="utf-8",
)
print("wrote backend/auth.py")

# ── main.py ───────────────────────────────────────────────────────────────────
(BACKEND / "main.py").write_text(
    "from fastapi import FastAPI, HTTPException, Depends, Request\n"
    "from fastapi.middleware.cors import CORSMiddleware\n"
    "from fastapi.staticfiles import StaticFiles\n"
    "from fastapi.responses import JSONResponse, RedirectResponse\n"
    "from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials\n"
    "from pydantic import BaseModel\n"
    "import json, os, re\n"
    "from pathlib import Path\n\n"
    "from dotenv import load_dotenv\n"
    "load_dotenv(Path(__file__).parent.parent / '.env')\n\n"
    "from auth import (\n"
    "    init_db, get_user, verify_password, create_token, decode_token,\n"
    "    get_user_plan, set_user_plan, downgrade_by_customer,\n"
    ")\n"
    "from stripe_handler import create_checkout_session, parse_webhook\n\n"
    "app = FastAPI(title='RS Platform')\n\n"
    "app.add_middleware(\n"
    "    CORSMiddleware,\n"
    "    allow_origins=['*'],\n"
    "    allow_methods=['GET', 'POST'],\n"
    "    allow_headers=['*'],\n"
    ")\n\n"
    "DATA_DIR = Path(r'C:\\Users\\danie\\Rel.-Strength')\n\n"
    "MARKET_FILES = {\n"
    "    'nasdaq': 'rs_full.json',\n"
    "    'sp500':  'rs_sp500.json',\n"
    "    'dax':    'rs_dax.json',\n"
    "}\n\n"
    "PRO_MARKETS = {'sp500', 'dax'}\n"
    "FREE_LIMIT  = 20\n\n"
    "security = HTTPBearer()\n\n\n"
    "def _load(path: Path):\n"
    "    with open(path, encoding='utf-8') as f:\n"
    "        return json.load(f)\n\n\n"
    "def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:\n"
    "    email = decode_token(credentials.credentials)\n"
    "    if not email:\n"
    "        raise HTTPException(status_code=401, detail='Token ungueltig oder abgelaufen')\n"
    "    return email\n\n\n"
    "class LoginRequest(BaseModel):\n"
    "    email: str\n"
    "    password: str\n\n\n"
    "@app.on_event('startup')\n"
    "async def startup():\n"
    "    init_db()\n\n\n"
    "# ── Auth ──────────────────────────────────────────────────────────────────\n"
    "@app.post('/api/auth/login')\n"
    "async def login(req: LoginRequest):\n"
    "    user = get_user(req.email)\n"
    "    if not user or not verify_password(req.password, user['password_hash']):\n"
    "        raise HTTPException(status_code=401, detail='E-Mail oder Passwort falsch')\n"
    "    return {'token': create_token(req.email), 'email': req.email}\n\n\n"
    "@app.get('/api/user/me')\n"
    "async def me(email: str = Depends(require_auth)):\n"
    "    return {'email': email, 'plan': get_user_plan(email)}\n\n\n"
    "# ── Data ──────────────────────────────────────────────────────────────────\n"
    "@app.get('/api/rs/{market}')\n"
    "async def get_rs(market: str, email: str = Depends(require_auth)):\n"
    "    if market not in MARKET_FILES:\n"
    "        raise HTTPException(404, f\"Unbekannter Markt '{market}'\")\n"
    "    plan = get_user_plan(email)\n"
    "    if market in PRO_MARKETS and plan != 'pro':\n"
    "        raise HTTPException(403, 'DAX und S&P500 erfordern ein Pro-Abo')\n"
    "    path = DATA_DIR / MARKET_FILES[market]\n"
    "    if not path.exists():\n"
    "        raise HTTPException(503, 'Datendatei noch nicht vorhanden')\n"
    "    data = _load(path)\n"
    "    if plan == 'free' and isinstance(data, dict) and 'data' in data:\n"
    "        data = {**data, 'data': data['data'][:FREE_LIMIT]}\n"
    "    return JSONResponse(content=data)\n\n\n"
    "@app.get('/api/backtest/{ticker}')\n"
    "async def get_backtest(ticker: str, email: str = Depends(require_auth)):\n"
    "    plan = get_user_plan(email)\n"
    "    if plan != 'pro':\n"
    "        raise HTTPException(403, 'Backtests erfordern ein Pro-Abo')\n"
    "    safe = re.sub(r'[^a-z0-9]', '_', ticker.lower())\n"
    "    path = DATA_DIR / f'backtest_{safe}.json'\n"
    "    if not path.exists():\n"
    "        raise HTTPException(404, f\"Keine Backtest-Daten fuer '{ticker}'\")\n"
    "    return JSONResponse(content=_load(path))\n\n\n"
    "@app.get('/api/signals')\n"
    "async def get_signals(email: str = Depends(require_auth)):\n"
    "    plan = get_user_plan(email)\n"
    "    if plan != 'pro':\n"
    "        raise HTTPException(403, 'Signals erfordern ein Pro-Abo')\n"
    "    path = DATA_DIR / 'signals.json'\n"
    "    if not path.exists():\n"
    "        return JSONResponse(content={})\n"
    "    return JSONResponse(content=_load(path))\n\n\n"
    "@app.get('/api/ratings')\n"
    "async def get_ratings(email: str = Depends(require_auth)):\n"
    "    path = DATA_DIR / 'ratings' / 'index.json'\n"
    "    if not path.exists():\n"
    "        return JSONResponse(content={'ratings': []})\n"
    "    return JSONResponse(content=_load(path))\n\n\n"
    "# ── Stripe ────────────────────────────────────────────────────────────────\n"
    "@app.get('/api/stripe/checkout')\n"
    "async def checkout(email: str = Depends(require_auth)):\n"
    "    url = create_checkout_session(email)\n"
    "    return {'url': url}\n\n\n"
    "@app.post('/api/stripe/webhook')\n"
    "async def webhook(request: Request):\n"
    "    payload = await request.body()\n"
    "    sig = request.headers.get('stripe-signature', '')\n"
    "    try:\n"
    "        event = parse_webhook(payload, sig)\n"
    "    except Exception as e:\n"
    "        raise HTTPException(400, str(e))\n"
    "    t = event['type']\n"
    "    if t == 'checkout.session.completed':\n"
    "        obj = event['data']['object']\n"
    "        set_user_plan(obj['customer_email'], 'pro', obj.get('customer'))\n"
    "    elif t in ('customer.subscription.deleted', 'customer.subscription.paused'):\n"
    "        cid = event['data']['object'].get('customer')\n"
    "        if cid:\n"
    "            downgrade_by_customer(cid)\n"
    "    return {'ok': True}\n\n\n"
    "@app.get('/health')\n"
    "async def health():\n"
    "    return {'status': 'ok', 'data_dir_exists': DATA_DIR.exists()}\n\n\n"
    "# Frontend static files\n"
    "_frontend = Path(__file__).parent.parent / 'frontend'\n"
    "if _frontend.exists():\n"
    "    app.mount('/', StaticFiles(directory=str(_frontend), html=True), name='static')\n",
    encoding="utf-8",
)
print("wrote backend/main.py")

# ── requirements.txt ──────────────────────────────────────────────────────────
(BACKEND / "requirements.txt").write_text(
    "fastapi==0.115.12\n"
    "uvicorn[standard]==0.34.3\n"
    "python-jose[cryptography]==3.3.0\n"
    "passlib[bcrypt]==1.7.4\n"
    "stripe==11.6.0\n"
    "python-dotenv==1.1.0\n",
    encoding="utf-8",
)
print("wrote backend/requirements.txt")

# ── HTML: inject plan banner + upgrade button ──────────────────────────────────
AUTH_SCRIPT_V3 = """  <script>
    var _token = localStorage.getItem('rs_token');
    if (!_token) { window.location.href = '/login.html'; }
    async function apiFetch(url, opts) {
      opts = opts || {};
      opts.headers = Object.assign({}, opts.headers, { 'Authorization': 'Bearer ' + _token });
      var r = await fetch(url, opts);
      if (r.status === 401) { localStorage.clear(); window.location.href = '/login.html'; }
      return r;
    }
    async function loadUserBanner() {
      try {
        var r = await apiFetch('/api/user/me');
        var u = await r.json();
        var bar = document.getElementById('plan-bar');
        if (!bar) return;
        if (u.plan === 'pro') {
          bar.innerHTML = '<span style="color:#22c55e">&#10003; Pro</span>';
        } else {
          bar.innerHTML = 'Free &nbsp;<a href="#" onclick="upgrade();return false;" style="background:#2563eb;color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;text-decoration:none">Upgrade</a>';
        }
      } catch(e) {}
    }
    async function upgrade() {
      var r = await apiFetch('/api/stripe/checkout');
      var d = await r.json();
      if (d.url) window.location.href = d.url;
    }
    loadUserBanner();
  </script>"""

PLAN_BAR_HTML = ('  <div id="plan-bar" style="position:fixed;top:8px;right:14px;'
                 'font-size:13px;color:#94a3b8;z-index:9999"></div>\n')

OLD_AUTH_SCRIPT = """  <script>
    var _token = localStorage.getItem('rs_token');
    if (!_token) { window.location.href = '/login.html'; }
    function apiFetch(url, opts) {
      opts = opts || {};
      opts.headers = Object.assign({}, opts.headers, { 'Authorization': 'Bearer ' + _token });
      return fetch(url, opts).then(function(r) {
        if (r.status === 401) { localStorage.clear(); window.location.href = '/login.html'; }
        return r;
      });
    }
  </script>"""

html_files = list(FRONTEND.glob("*.html"))
patched = 0
for fpath in html_files:
    if fpath.name == "login.html":
        continue
    text = fpath.read_text(encoding="utf-8")
    changed = False
    # Replace old auth script → v3
    if OLD_AUTH_SCRIPT in text:
        text = text.replace(OLD_AUTH_SCRIPT, AUTH_SCRIPT_V3)
        changed = True
    # Insert plan bar after <body> if not present
    if 'id="plan-bar"' not in text:
        text = text.replace("<body>", "<body>\n" + PLAN_BAR_HTML, 1)
        text = text.replace("<body\n>", "<body>\n" + PLAN_BAR_HTML, 1)  # edge case
        changed = True
    if changed:
        fpath.write_text(text, encoding="utf-8")
        print(f"patched {fpath.name}")
        patched += 1

if patched == 0:
    print("warning: no HTML files patched (auth script pattern not found)")

# ── .env (local, not committed) ───────────────────────────────────────────────
env_path = ROOT / ".env"
if not env_path.exists():
    env_path.write_text(
        "SECRET_KEY=CHANGE-ME-use-openssl-rand-hex-32\n"
        "STRIPE_SECRET_KEY=sk_test_REPLACE_ME\n"
        "STRIPE_WEBHOOK_SECRET=whsec_REPLACE_ME\n"
        "STRIPE_PRICE_ID=price_REPLACE_ME\n"
        "APP_URL=http://localhost:8000\n",
        encoding="utf-8",
    )
    print("wrote .env (local, fill in Stripe keys before testing payments)")

print("\nPhase 3 migration complete.")
print("Next: cd backend && pip install -r requirements.txt")
print("Then: start.bat")

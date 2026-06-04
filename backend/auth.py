from datetime import datetime, timedelta
from pathlib import Path
import os, sqlite3, secrets

import bcrypt as _bcrypt
from jose import JWTError, jwt

SECRET_KEY          = os.environ.get("SECRET_KEY", "CHANGE-ME-use-openssl-rand-hex-32")
ALGORITHM           = "HS256"
TOKEN_EXPIRE_HOURS  = 24 * 7
RESET_EXPIRE_HOURS  = 1

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "users.db")))


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                email             TEXT    UNIQUE NOT NULL,
                password_hash     TEXT    NOT NULL,
                plan              TEXT    DEFAULT 'free',
                stripe_customer_id TEXT,
                is_active         INTEGER DEFAULT 1,
                is_admin          INTEGER DEFAULT 0,
                reset_token       TEXT,
                reset_token_exp   TEXT,
                created_at        TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT    NOT NULL,
                ticker     TEXT    NOT NULL,
                added_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_email, ticker)
            )
        """)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        for col, defn in [
            ("plan",               "TEXT DEFAULT 'free'"),
            ("stripe_customer_id", "TEXT"),
            ("is_admin",           "INTEGER DEFAULT 0"),
            ("reset_token",        "TEXT"),
            ("reset_token_exp",    "TEXT"),
            ("telegram_chat_id",   "TEXT"),
            ("tg_link_token",      "TEXT"),
            ("tg_link_exp",        "TEXT"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")


def get_user(email: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, email, plan, is_active, is_admin, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_user(email: str, password: str, is_admin: int = 0) -> None:
    hashed = _bcrypt.hashpw(password.encode("utf-8")[:72], _bcrypt.gensalt()).decode()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
            (email, hashed, is_admin),
        )


def get_user_plan(email: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT plan FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()
    return (row[0] if row else None) or "free"


def set_user_plan(email: str, plan: str, customer_id: str | None = None) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        if customer_id:
            conn.execute(
                "UPDATE users SET plan=?, stripe_customer_id=? WHERE email=?",
                (plan, customer_id, email),
            )
        else:
            conn.execute("UPDATE users SET plan=? WHERE email=?", (plan, email))


def downgrade_by_customer(customer_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET plan='free' WHERE stripe_customer_id=?",
            (customer_id,),
        )


def check_is_admin(email: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT is_admin FROM users WHERE email=? AND is_active=1", (email,)
        ).fetchone()
    return bool(row and row[0])


def set_admin(email: str, is_admin: bool) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET is_admin=? WHERE email=?", (int(is_admin), email))


def set_active(email: str, is_active: bool) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET is_active=? WHERE email=?", (int(is_active), email))


def change_password(email: str, new_password: str) -> None:
    hashed = _bcrypt.hashpw(new_password.encode("utf-8")[:72], _bcrypt.gensalt()).decode()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hashed, email))


def create_reset_token(email: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email=? AND is_active=1", (email,)
        ).fetchone()
        if not row:
            return None
        token   = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=RESET_EXPIRE_HOURS)).isoformat()
        conn.execute(
            "UPDATE users SET reset_token=?, reset_token_exp=? WHERE email=?",
            (token, expires, email),
        )
    return token


def validate_reset_token(token: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT email, reset_token_exp FROM users WHERE reset_token=? AND is_active=1",
            (token,),
        ).fetchone()
    if not row:
        return None
    if datetime.utcnow().isoformat() > row[1]:
        return None
    return row[0]


def use_reset_token(token: str, new_password: str) -> bool:
    email = validate_reset_token(token)
    if not email:
        return False
    hashed = _bcrypt.hashpw(new_password.encode("utf-8")[:72], _bcrypt.gensalt()).decode()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, reset_token=NULL, reset_token_exp=NULL WHERE email=?",
            (hashed, email),
        )
    return True


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


def create_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_telegram_chat_id(email: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT telegram_chat_id FROM users WHERE email=? AND is_active=1", (email,)
        ).fetchone()
    return (row[0] if row else None) or None


def set_telegram_chat_id(email: str, chat_id: str | None) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET telegram_chat_id=? WHERE email=?",
            (chat_id or None, email),
        )


def create_tg_link_token(email: str) -> str | None:
    """Erzeugt einen kurzen Einmal-Token für den Telegram-Deep-Link
    (https://t.me/<bot>?start=<token>). Läuft nach 15 Minuten ab."""
    token   = secrets.token_urlsafe(16)
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE users SET tg_link_token=?, tg_link_exp=? WHERE email=? AND is_active=1",
            (token, expires, email),
        )
        if cur.rowcount == 0:
            return None
    return token


def link_telegram_by_token(token: str, chat_id: str) -> str | None:
    """Verknüpft eine Chat-ID mit dem User, dem der Token gehört. Gibt die
    E-Mail zurück (oder None bei ungültigem/abgelaufenem Token)."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT email, tg_link_exp FROM users "
            "WHERE tg_link_token=? AND is_active=1",
            (token,),
        ).fetchone()
        if not row:
            return None
        email, exp = row
        if not exp or datetime.utcnow().isoformat() > exp:
            return None
        conn.execute(
            "UPDATE users SET telegram_chat_id=?, tg_link_token=NULL, "
            "tg_link_exp=NULL WHERE email=?",
            (str(chat_id), email),
        )
    return email


def get_all_telegram_chat_ids() -> list[str]:
    """Alle hinterlegten Chat-IDs aktiver User — für den Alert-Versand."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT telegram_chat_id FROM users "
            "WHERE is_active=1 AND telegram_chat_id IS NOT NULL AND telegram_chat_id != ''"
        ).fetchall()
    return [r[0] for r in rows]


def get_watchlist(email: str) -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_email=? ORDER BY added_at",
            (email,)
        ).fetchall()
    return [r[0] for r in rows]


def add_to_watchlist(email: str, ticker: str) -> bool:
    """Returns False if ticker already in watchlist."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO watchlist (user_email, ticker) VALUES (?, ?)",
                (email, ticker.upper()),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_from_watchlist(email: str, ticker: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_email=? AND ticker=?",
            (email, ticker.upper()),
        )

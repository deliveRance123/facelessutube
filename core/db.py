import os
import sqlite3
import json
import hashlib
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlparse
from core.config import STORAGE_DIR, BASE_DIR

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = STORAGE_DIR / "app.db"

class Database:
    def __init__(self):
        self.url = os.getenv("DATABASE_URL", "").strip()
        self.is_postgres = bool(self.url and ("postgres://" in self.url or "postgresql://" in self.url))

    def get_connection(self):
        if self.is_postgres:
            import pg8000.native
            clean_url = self.url.replace("postgres://", "postgresql://")
            parsed = urlparse(clean_url)
            
            user = parsed.username
            password = parsed.password
            host = parsed.hostname
            port = parsed.port or 5432
            database = parsed.path.lstrip("/")
            
            conn = pg8000.native.Connection(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database,
                ssl_context=True
            )
            return conn
        else:
            SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(SQLITE_PATH))
            conn.row_factory = sqlite3.Row
            return conn

    def execute(self, query: str, params: tuple = ()):
        """Executes a query and returns results as list of dicts."""
        if self.is_postgres:
            conn = self.get_connection()
            try:
                pg_query = query
                count = 1
                while "?" in pg_query:
                    pg_query = pg_query.replace("?", f":{count}", 1)
                    count += 1
                
                kwargs = {f"{i+1}": p for i, p in enumerate(params)}
                result = conn.run(pg_query, **kwargs) if params else conn.run(pg_query)
                if conn.columns:
                    col_names = [col["name"] for col in conn.columns]
                    return [dict(zip(col_names, row)) for row in result]
                return []
            finally:
                conn.close()
        else:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                if cursor.description:
                    return [dict(row) for row in cursor.fetchall()]
                return []
            finally:
                conn.close()

db = Database()

def init_db():
    """Initializes tables in PostgreSQL (Neon) or SQLite."""
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            elevenlabs_api_key TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            subscription_tier TEXT DEFAULT 'free',
            subscription_status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT NOT NULL,
            prompt TEXT,
            script TEXT,
            format_type TEXT DEFAULT 'short',
            niche TEXT DEFAULT 'custom',
            voice_provider TEXT DEFAULT 'edge-tts',
            voice_id TEXT DEFAULT 'en-US-ChristopherNeural',
            caption_style TEXT DEFAULT 'gold',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            scene_index INTEGER,
            narrative_text TEXT,
            image_url TEXT,
            duration REAL DEFAULT 4.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            user_id TEXT,
            title TEXT,
            format_type TEXT,
            filename TEXT,
            video_url TEXT,
            duration REAL,
            caption_style TEXT DEFAULT 'gold',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    ]
    
    if db.is_postgres:
        conn = db.get_connection()
        try:
            for sql in tables_sql:
                conn.run(sql)
            # Ensure columns exist if tables were created earlier
            migrations = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free';",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active';",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id TEXT;",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS caption_style TEXT DEFAULT 'gold';",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS user_id TEXT;",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS caption_style TEXT DEFAULT 'gold';"
            ]
            for m_sql in migrations:
                try:
                    conn.run(m_sql)
                except Exception as me:
                    pass
            print("[Database] Cloud PostgreSQL initialized & migrated successfully.")
        finally:
            conn.close()
    else:
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            for sql in tables_sql:
                cursor.execute(sql)
            # Migration checks for SQLite
            for tbl, col, col_type in [
                ("users", "is_admin", "BOOLEAN DEFAULT FALSE"),
                ("users", "subscription_tier", "TEXT DEFAULT 'free'"),
                ("users", "subscription_status", "TEXT DEFAULT 'active'"),
                ("projects", "user_id", "TEXT"),
                ("projects", "caption_style", "TEXT DEFAULT 'gold'"),
                ("videos", "user_id", "TEXT"),
                ("videos", "caption_style", "TEXT DEFAULT 'gold'")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type};")
                except Exception:
                    pass
            conn.commit()
            print("[Database] Local database initialized successfully.")
        finally:
            conn.close()

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return pw_hash, salt

def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    expected_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(expected_hash, pw_hash)

def create_user(email: str, username: str, password: str) -> dict:
    clean_email = email.strip().lower()
    clean_username = username.strip()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Valid email is required.")
    if len(clean_username) < 2:
        raise ValueError("Username must be at least 2 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
        
    existing = db.execute("SELECT id FROM users WHERE email = ?", (clean_email,))
    if existing:
        raise ValueError("An account with this email already exists.")
    
    # Auto-promote first user to administrator
    all_users = db.execute("SELECT COUNT(*) as count FROM users")
    is_first = (all_users and all_users[0].get("count", 0) == 0)
    is_admin = True if is_first else False
    
    user_id = str(uuid.uuid4())
    pw_hash, salt = hash_password(password)
    db.execute(
        "INSERT INTO users (id, email, username, password_hash, salt, is_admin, subscription_tier, subscription_status) VALUES (?, ?, ?, ?, ?, ?, 'free', 'active')",
        (user_id, clean_email, clean_username, pw_hash, salt, is_admin)
    )
    return {"id": user_id, "email": clean_email, "username": clean_username, "is_admin": is_admin, "subscription_tier": "free"}

def authenticate_user(identifier: str, password: str) -> dict:
    clean_id = identifier.strip().lower()
    users = db.execute("SELECT * FROM users WHERE email = ? OR LOWER(username) = ?", (clean_id, clean_id))
    if not users:
        return None
    user = users[0]
    if verify_password(password, user["password_hash"], user["salt"]):
        return {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "elevenlabs_api_key": user.get("elevenlabs_api_key"),
            "is_admin": bool(user.get("is_admin", False)),
            "subscription_tier": user.get("subscription_tier", "free"),
            "subscription_status": user.get("subscription_status", "active")
        }
    return None

def get_user_by_id(user_id: str) -> dict:
    users = db.execute("SELECT id, email, username, elevenlabs_api_key, is_admin, subscription_tier, subscription_status, created_at FROM users WHERE id = ?", (user_id,))
    if not users:
        return None
    u = dict(users[0])
    u["is_admin"] = bool(u.get("is_admin", False))
    if u.get("created_at"):
        u["created_at"] = str(u["created_at"])
    return u

def update_user_elevenlabs_key(user_id: str, key: str):
    db.execute("UPDATE users SET elevenlabs_api_key = ? WHERE id = ?", (key.strip(), user_id))

def update_user_profile(user_id: str, username: str = None, email: str = None, new_password: str = None):
    """Updates user profile credentials."""
    if username:
        db.execute("UPDATE users SET username = ? WHERE id = ?", (username.strip(), user_id))
    if email:
        db.execute("UPDATE users SET email = ? WHERE id = ?", (email.strip().lower(), user_id))
    if new_password and len(new_password) >= 6:
        pw_hash, salt = hash_password(new_password)
        db.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pw_hash, salt, user_id))


def get_all_users() -> list[dict]:
    """Admin function: returns all registered users with video project count."""
    try:
        users = db.execute("""
            SELECT u.id, u.email, u.username, u.is_admin, u.subscription_tier, u.subscription_status, u.created_at, COUNT(v.id) as videos_count 
            FROM users u 
            LEFT JOIN videos v ON u.id = v.user_id 
            GROUP BY u.id, u.email, u.username, u.is_admin, u.subscription_tier, u.subscription_status, u.created_at 
            ORDER BY u.created_at DESC
        """)
    except Exception:
        users = db.execute("SELECT id, email, username, is_admin, subscription_tier, subscription_status, created_at FROM users ORDER BY created_at DESC")
        
    results = []
    for u in users:
        d = dict(u)
        d["is_admin"] = bool(d.get("is_admin", False))
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        if "videos_count" not in d:
            d["videos_count"] = 0
        results.append(d)
    return results

def update_user_role(user_id: str, is_admin: bool):
    """Admin function: toggle user administrator rights."""
    db.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))

def update_user_subscription(user_id: str, tier: str, status: str = "active"):
    """Admin function: update user subscription tier and status."""
    db.execute("UPDATE users SET subscription_tier = ?, subscription_status = ? WHERE id = ?", (tier.lower(), status.lower(), user_id))

def get_platform_setting(key: str, default: str = "") -> str:
    rows = db.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
    if rows and rows[0].get("value") is not None:
        return rows[0]["value"]
    return default

def set_platform_setting(key: str, value: str):
    existing = db.execute("SELECT key FROM user_settings WHERE key = ?", (key,))
    if existing:
        db.execute("UPDATE user_settings SET value = ? WHERE key = ?", (value, key))
    else:
        db.execute("INSERT INTO user_settings (key, value) VALUES (?, ?)", (key, value))

# Auto-initialize on load
init_db()

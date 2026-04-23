"""
Resolva — Complaint Management System (Python FastAPI backend).

Run locally:
    pip install -r requirements.txt
    uvicorn backend.main:app --reload --port 8000
"""
import os
import sqlite3
import subprocess
import secrets
import hashlib
import json as _json
from collections import Counter
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Depends, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

# --------------------------------------------------------------------------
# Config (env-driven)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "complaints.db")))
CLASSIFIER_BIN = Path(os.getenv("CLASSIFIER_BIN", str(BASE_DIR.parent / "native" / "classifier")))
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET") or "change-me-in-production-please-1234567890"
ALGO = "HS256"
TOKEN_TTL_HOURS = 24

security = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar_url" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        c.execute("DELETE FROM users WHERE email=? AND role='admin'", ("admin@demo.io",))


# --------------------------------------------------------------------------
# Security helpers
# --------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32).hex()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False


def make_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (int(payload["sub"]),)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return dict(row)


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


# --------------------------------------------------------------------------
# C++ classifier integration
# --------------------------------------------------------------------------
def classify_priority(text: str) -> str:
    if not CLASSIFIER_BIN.exists():
        return "medium"
    try:
        res = subprocess.run(
            [str(CLASSIFIER_BIN)], input=text, capture_output=True, text=True, timeout=3,
        )
        out = res.stdout.strip().lower()
        if out in {"low", "medium", "high", "critical"}:
            return out
    except Exception:
        pass
    return "medium"


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ComplaintIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=10, max_length=4000)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|resolved|rejected)$")


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(title="Resolva — Complaint Management System", version="3.0.0")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def _health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/config.js")
def runtime_config():
    body = "window.RESOLVA_API_BASE = window.RESOLVA_API_BASE || location.origin;\n"
    return Response(content=body, media_type="application/javascript")


# ---- Auth: email/password ----
@app.post("/api/register")
def register(body: RegisterIn):
    name = body.name.strip()
    email = body.email.strip().lower()
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "Email already registered. Please sign in instead.")
        cur = c.execute(
            "INSERT INTO users(name,email,password_hash) VALUES (?,?,?)",
            (name, email, hash_password(body.password)),
        )
        uid = cur.lastrowid
    return {"token": make_token(uid, "user"),
            "user": {"id": uid, "name": name, "email": email, "role": "user"}}


@app.post("/api/login")
def login(body: LoginIn):
    email = body.email.strip().lower()
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row:
        raise HTTPException(401, "No account found with that email.")
    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect password.")
    return {"token": make_token(row["id"], row["role"]),
            "user": {"id": row["id"], "name": row["name"], "email": row["email"],
                     "role": row["role"], "avatar_url": row["avatar_url"]}}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"id": user["id"], "name": user["name"], "email": user["email"],
            "role": user["role"], "avatar_url": user.get("avatar_url")}


@app.get("/api/stats")
def stats(user=Depends(current_user)):
    with db() as c:
        if user["role"] == "admin":
            rows = c.execute("SELECT status, priority FROM complaints").fetchall()
        else:
            rows = c.execute(
                "SELECT status, priority FROM complaints WHERE user_id=?",
                (user["id"],),
            ).fetchall()

    statuses = Counter(row["status"] for row in rows)
    priorities = Counter(row["priority"] for row in rows)
    return {
        "total": len(rows),
        "by_status": {
            "pending": statuses.get("pending", 0),
            "in_progress": statuses.get("in_progress", 0),
            "resolved": statuses.get("resolved", 0),
            "rejected": statuses.get("rejected", 0),
        },
        "by_priority": {
            "critical": priorities.get("critical", 0),
            "high": priorities.get("high", 0),
            "medium": priorities.get("medium", 0),
            "low": priorities.get("low", 0),
        },
    }


# ---- Complaints ----
@app.post("/api/complaints")
def create_complaint(body: ComplaintIn, user=Depends(current_user)):
    priority = classify_priority(f"{body.title}. {body.description}")
    with db() as c:
        cur = c.execute(
            """INSERT INTO complaints(user_id,title,category,description,priority)
               VALUES (?,?,?,?,?)""",
            (user["id"], body.title, body.category, body.description, priority),
        )
        cid = cur.lastrowid
        row = c.execute("SELECT * FROM complaints WHERE id=?", (cid,)).fetchone()
    return dict(row)


@app.get("/api/complaints")
def list_complaints(user=Depends(current_user)):
    with db() as c:
        if user["role"] == "admin":
            rows = c.execute("""
                SELECT c.*, u.name AS user_name, u.email AS user_email
                FROM complaints c JOIN users u ON u.id = c.user_id
                ORDER BY
                  CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                  WHEN 'medium' THEN 2 ELSE 3 END,
                  c.created_at DESC
            """).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM complaints WHERE user_id=? ORDER BY created_at DESC",
                (user["id"],),
            ).fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/complaints/{cid}/status")
def update_status(cid: int, body: StatusIn, _admin=Depends(require_admin)):
    with db() as c:
        if not c.execute("SELECT 1 FROM complaints WHERE id=?", (cid,)).fetchone():
            raise HTTPException(404, "Complaint not found")
        c.execute(
            "UPDATE complaints SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (body.status, cid),
        )
        row = c.execute("SELECT * FROM complaints WHERE id=?", (cid,)).fetchone()
    return dict(row)


@app.delete("/api/complaints/{cid}")
def delete_complaint(cid: int, user=Depends(current_user)):
    with db() as c:
        row = c.execute("SELECT * FROM complaints WHERE id=?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Not found")
        if user["role"] != "admin" and row["user_id"] != user["id"]:
            raise HTTPException(403, "Not allowed")
        c.execute("DELETE FROM complaints WHERE id=?", (cid,))
    return {"ok": True}

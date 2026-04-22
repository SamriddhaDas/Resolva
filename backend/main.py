"""
Complaint Management System — Python FastAPI backend.

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""
import os
import sqlite3
import subprocess
import secrets
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "complaints.db")))
FRONTEND_DIR = BASE_DIR.parent / "frontend"
CLASSIFIER_BIN = Path(os.getenv("CLASSIFIER_BIN", str(BASE_DIR.parent / "native" / "classifier")))
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please-1234567890")
ALGO = "HS256"
TOKEN_TTL_HOURS = 24

security = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
@contextmanager
def db():
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
            password_hash TEXT NOT NULL,
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
        # Seed an admin if none
        cur = c.execute("SELECT COUNT(*) AS n FROM users WHERE role='admin'")
        if cur.fetchone()["n"] == 0:
            c.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)",
                ("Admin", "admin@demo.io", hash_password("admin123"), "admin"),
            )


# --------------------------------------------------------------------------
# Security helpers
# --------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32).hex()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: str) -> bool:
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
    """Call the native C++ classifier to compute priority. Falls back gracefully."""
    if not CLASSIFIER_BIN.exists():
        return "medium"
    try:
        res = subprocess.run(
            [str(CLASSIFIER_BIN)],
            input=text,
            capture_output=True,
            text=True,
            timeout=3,
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
app = FastAPI(title="Complaint Management System", version="2.0.0")
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def _health():
    return {"status": "ok"}


@app.on_event("startup")
def _startup():
    init_db()


# ---- Auth ----
@app.post("/api/register")
def register(body: RegisterIn):
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (body.email,)).fetchone():
            raise HTTPException(409, "Email already registered")
        cur = c.execute(
            "INSERT INTO users(name,email,password_hash) VALUES (?,?,?)",
            (body.name, body.email, hash_password(body.password)),
        )
        uid = cur.lastrowid
    return {"token": make_token(uid, "user"), "user": {"id": uid, "name": body.name, "email": body.email, "role": "user"}}


@app.post("/api/login")
def login(body: LoginIn):
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {
        "token": make_token(row["id"], row["role"]),
        "user": {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]},
    }


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


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
            raise HTTPException(403, "Forbidden")
        c.execute("DELETE FROM complaints WHERE id=?", (cid,))
    return {"ok": True}


@app.get("/api/stats")
def stats(user=Depends(current_user)):
    with db() as c:
        scope = "" if user["role"] == "admin" else f"WHERE user_id={user['id']}"
        total = c.execute(f"SELECT COUNT(*) n FROM complaints {scope}").fetchone()["n"]
        by_status = {r["status"]: r["n"] for r in c.execute(
            f"SELECT status, COUNT(*) n FROM complaints {scope} GROUP BY status")}
        by_priority = {r["priority"]: r["n"] for r in c.execute(
            f"SELECT priority, COUNT(*) n FROM complaints {scope} GROUP BY priority")}
    return {"total": total, "by_status": by_status, "by_priority": by_priority}


# ---- Static frontend ----
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def root():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{page}.html")
    def page(page: str):
        f = FRONTEND_DIR / f"{page}.html"
        if f.exists():
            return FileResponse(f)
        raise HTTPException(404)

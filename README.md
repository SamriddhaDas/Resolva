# Resolva — Complaint Management System (v2)

A modern rewrite of a classic PHP/MySQL complaint system using a focused, polyglot stack:

| Layer        | Tech                               |
|--------------|------------------------------------|
| Backend API  | **Python** (FastAPI + SQLite + JWT) |
| Native logic | **C++** priority classifier (CLI)  |
| Frontend     | **Tailwind CSS + vanilla JS**      |
| Dev server   | **Node.js** (zero-dep static + proxy) |

The original schema (users + complaints) is preserved and extended (categories, priorities, status workflow, roles).

## Project structure

```
.
├── backend/           # Python FastAPI app
│   ├── main.py
│   └── requirements.txt
├── native/            # C++ priority classifier
│   ├── classifier.cpp
│   └── Makefile
├── frontend/          # Tailwind + JS (no build step)
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── css/app.css
│   └── js/{api,auth,dashboard}.js
└── node-server/       # Optional Node static + API proxy
    ├── server.js
    └── package.json
```

## Quick start

### 1) Build the C++ classifier (optional — backend falls back if missing)
```bash
cd native
make            # produces ./classifier
cd ..
```

### 2) Run the Python backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
The backend serves the API **and** the frontend at <http://localhost:8000>.

### 3) (Optional) Run the Node dev server
Useful if you want to host the frontend separately.
```bash
cd node-server
node server.js          # http://localhost:3000, proxies /api/* → http://localhost:8000
```

## Accounts and persistence
- Any visitor can create a normal account with email/password.
- Google sign-in works once `GOOGLE_CLIENT_ID` is configured on the backend.
- User accounts and complaint records are stored in the SQLite database so returning users can sign in again without re-registering.

## Security notes (vs. the original PHP version)
- ❌ Plain-text passwords → ✅ scrypt hashing with per-user salt
- ❌ String-concat SQL (injection-prone) → ✅ parameterized queries everywhere
- ❌ PHP `$_SESSION` cookie → ✅ stateless JWT (`Authorization: Bearer …`)
- ❌ No authorization on complaints → ✅ row-level checks + admin-only status updates
- ❌ Single global `complaint` field → ✅ title, category, rich description, priority, status, timestamps

## How auto-prioritization works
On every new complaint the backend pipes the text into the C++ binary via stdin.
The classifier scores keywords (`urgent`, `hazard`, `injured`, `outage`, …),
exclamation density, and length, then prints one of: `low | medium | high | critical`.
Python stores that as the complaint's priority and the dashboard sorts by it.

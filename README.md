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

## Demo account
An admin user is auto-seeded on first run:
- **Email:** `admin@demo.io`
- **Password:** `admin123`

Change this immediately in any real deployment.

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

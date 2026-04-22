# Deploying Resolva (Vercel + Render)

Frontend → **Vercel** (static).  Backend (Python + C++ + SQLite) → **Render** (Docker).

## 1. Push to GitHub
```bash
git init && git add . && git commit -m "Resolva initial"
git branch -M main
git remote add origin https://github.com/<you>/resolva.git
git push -u origin main
```

## 2. Deploy backend on Render
1. https://render.com → **New** → **Blueprint** → select your repo.
   Render will detect `render.yaml` and provision the service + 1 GB disk.
   (Or: New → Web Service → Environment **Docker** → Dockerfile path `backend/Dockerfile` → Docker context `.`)
2. After deploy, copy the URL, e.g. `https://resolva-api.onrender.com`.
3. In **Environment**, set `ALLOWED_ORIGINS` to your Vercel URL (you'll get it in step 3). Multiple origins comma-separated.

Default admin (auto-seeded on first boot): `admin@demo.io` / `admin123` — change immediately.

## 3. Deploy frontend on Vercel
1. https://vercel.com → **Add New Project** → import the repo.
2. Framework: **Other**. Leave defaults — `vercel.json` sets output dir to `frontend/`.
3. Deploy. Copy URL, e.g. `https://resolva.vercel.app`.

## 4. Connect them
Edit **`frontend/js/config.js`**:
```js
window.RESOLVA_API_BASE = "https://resolva-api.onrender.com";
```
Commit & push — Vercel auto-redeploys in ~20s.

Then on Render, update `ALLOWED_ORIGINS=https://resolva.vercel.app` and redeploy.

## 5. Verify
- `https://resolva-api.onrender.com/api/health` → `{"status":"ok"}`
- Open Vercel URL → register → submit complaint → priority assigned by C++ engine.

## Local dev
```bash
# Backend
cd backend && pip install -r requirements.txt
cd ../native && make
cd ../backend && uvicorn main:app --reload --port 8000

# Frontend (Node static + proxy)
cd node-server && node server.js   # http://localhost:3000
```
For local dev, leave `RESOLVA_API_BASE = ""` so the Node proxy forwards `/api/*` to FastAPI.

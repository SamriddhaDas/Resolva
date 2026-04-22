# Resolva — Deploy Guide (Vercel + Render + Google Sign-In)

This guide gets you a working full-stack deployment with email/password
**and** Google sign-in.

---

## 0. What you'll set up

| Layer | Where | What |
|---|---|---|
| Frontend (HTML/Tailwind/JS) | **Vercel** | Static site from `frontend/` |
| Backend (FastAPI + SQLite + C++) | **Render** | Docker web service with persistent disk |
| Google Sign-In | **Google Cloud Console** | OAuth Client ID (Web application) |

---

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "Resolva v2.1 — Google auth"
git branch -M main
git remote add origin https://github.com/<you>/resolva.git
git push -u origin main
```

---

## 2. Create the Google OAuth Client

1. Open <https://console.cloud.google.com/apis/credentials>.
2. Create a new project (or pick an existing one).
3. Click **Create Credentials → OAuth client ID**.
   - If asked, configure the OAuth consent screen first:
     - User type: **External**
     - App name: `Resolva`
     - Support email: your email
     - Save and continue (you can leave scopes empty)
4. Application type: **Web application**
5. **Authorized JavaScript origins** (add ALL of these):
   - `http://localhost:3000`
   - `https://<your-app>.vercel.app`  ← your Vercel URL
6. **Authorized redirect URIs**: leave empty (we use Google Identity Services, not redirect flow).
7. Click **Create**, then **copy the Client ID** (looks like `1234567890-xxx.apps.googleusercontent.com`).

---

## 3. Deploy the backend on Render

1. Go to <https://render.com> → **New** → **Web Service** → connect your GitHub repo.
2. Render will detect `render.yaml`. Settings should auto-fill:
   - Environment: **Docker**
   - Dockerfile: `backend/Dockerfile`
   - Plan: **Free**
   - Health check path: `/api/health`
   - Disk: `/app/backend/data`, 1 GB
3. **Environment variables** — set these:
   - `SECRET_KEY` — leave (auto-generated)
   - `GOOGLE_CLIENT_ID` — **paste the Client ID from step 2**
   - `ALLOWED_ORIGINS` — set to `https://<your-app>.vercel.app` (or `*` while testing)
4. **Create Web Service**. Wait ~5 min for build.
5. Copy your URL, e.g. `https://resolva-api.onrender.com`.
6. Verify: open `https://resolva-api.onrender.com/api/health` — should return JSON with `"google_enabled": true`.

> ⚠️ **First request after idle is slow** (~30–50 s on free plan). The frontend handles this gracefully, but let users know.

---

## 4. Deploy the frontend on Vercel

1. Open `frontend/js/config.js` and set:
   ```js
   window.RESOLVA_API_BASE = "https://resolva-api.onrender.com"; // ← your Render URL
   ```
   Commit & push.
2. Go to <https://vercel.com> → **Add New Project** → import your GitHub repo.
3. Framework preset: **Other** (the `vercel.json` at the root handles routing).
4. Click **Deploy**. Done in ~30 s.
5. Copy your URL, e.g. `https://resolva.vercel.app`.

---

## 5. Wire it up

1. Go back to Google Cloud Console → your OAuth client → **Authorized JavaScript origins** → confirm your Vercel URL is listed. Save.
2. On Render, update `ALLOWED_ORIGINS` to your Vercel URL exactly (no trailing slash). Re-deploy if you changed it.
3. Visit your Vercel URL → `/login.html` → you should see **"Continue with Google"** button.

---

## 6. Test checklist

- [ ] `/api/health` returns `{"status":"ok","google_enabled":true}`
- [ ] `/login.html` shows the Google button
- [ ] Click Google button → pick account → redirected to `/dashboard.html`
- [ ] Email/password register → instant login → dashboard
- [ ] Email/password login with `admin@demo.io` / `admin123` → admin view

---

## Troubleshooting

**"NOT_FOUND" on Vercel when signing in**
You forgot step 4.1. Open `frontend/js/config.js`, set `RESOLVA_API_BASE` to your Render URL, push.

**"Cannot reach backend at..."**
Render free service is asleep. Wait 30–50 s, then retry. Or visit `/api/health` once to wake it.

**"Invalid Google token" / "Google sign-in not configured"**
The backend doesn't have `GOOGLE_CLIENT_ID` set. Add it on Render → restart.

**"popup_blocked_by_browser" or button doesn't appear**
Your Vercel domain isn't in **Authorized JavaScript origins** on Google Cloud Console. Add it and wait ~1 min.

**CORS errors**
Set `ALLOWED_ORIGINS` on Render to your exact Vercel origin (no path, no trailing slash).

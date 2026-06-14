# Deployment Guide

Stack: Vercel (frontend) · Railway (backend) · Supabase (DB) · Upstash (Redis)
All free tiers. No credit card needed.

---

## 1 — Push to GitHub

Open a terminal in `C:\Users\VineetSalian\Documents\Repo\ping me\Ping-me\`

```bash
git init
git add .
git commit -m "Initial commit: Ping salon booking system"
gh repo create ping-me --public --source=. --push
```

> If you don't have the `gh` CLI: go to github.com → New repository → name it `ping-me`
> → then run `git remote add origin https://github.com/YOUR_USERNAME/ping-me.git && git push -u origin master`

---

## 2 — Upstash Redis (free)

1. Go to **https://upstash.com** → Sign up → Create Database
2. Choose **Redis** → Region: Mumbai (ap-south-1) → Free tier
3. Click the database → **Connect** tab → copy the **REST URL** (starts with `rediss://`)
4. Save this as your `REDIS_URL`

---

## 3 — Deploy Backend to Railway

1. Go to **https://railway.app** → New Project → Deploy from GitHub repo
2. Select your `ping-me` repo
3. Click **Add service** → GitHub → select `ping-me`
4. In service settings → **Source** → set **Root Directory** to `backend`
5. Railway will auto-detect Python + `requirements.txt`
6. Go to **Variables** tab and add ALL of these:

| Variable | Value |
|----------|-------|
| `SUPABASE_URL` | your Supabase project URL |
| `SUPABASE_KEY` | your Supabase service role key |
| `SUPABASE_INVOICE_BUCKET` | `invoices` |
| `REDIS_URL` | your Upstash Redis URL from step 2 |
| `TWILIO_ACCOUNT_SID` | from Twilio console |
| `TWILIO_AUTH_TOKEN` | from Twilio console |
| `TWILIO_WHATSAPP_NUMBER` | `whatsapp:+14155238886` (sandbox) |
| `ADMIN_API_KEY` | any long random string (your master key) |
| `VERIFY_TWILIO_SIGNATURE` | `True` |
| `DEBUG` | `False` |
| `CORS_ORIGINS` | `*` for now, update after Vercel deploy |
| `PUBLIC_BASE_URL` | leave blank for now, fill in after Railway gives you a URL |

7. Click **Deploy**. Wait for the green checkmark.
8. Go to **Settings** → **Networking** → **Generate Domain**
9. Note your backend URL, e.g. `https://ping-me-production.up.railway.app`
10. Come back to Variables and update:
    - `PUBLIC_BASE_URL` = `https://ping-me-production.up.railway.app`

**Test it:** open `https://YOUR-RAILWAY-URL/health` → should return `{"status":"ok"}`

---

## 4 — Deploy Frontend to Vercel

1. Go to **https://vercel.com** → Add New Project → Import from GitHub
2. Select your `ping-me` repo
3. In **Configure Project**:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: click Edit → type `frontend`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL (e.g. `https://ping-me-production.up.railway.app`)
5. Click **Deploy**

6. After deploy, note your Vercel URL (e.g. `https://ping-me.vercel.app`)

---

## 5 — Wire up CORS (post-deploy)

Back in Railway → your service → Variables, update:

```
CORS_ORIGINS=https://ping-me.vercel.app
```

Click **Redeploy**.

---

## 6 — Update Twilio Webhook

1. Go to Twilio console → Messaging → Try it out → WhatsApp
2. Under **Sandbox Settings** → When a message comes in:
   ```
   https://YOUR-RAILWAY-URL/api/webhooks/whatsapp
   ```
   Method: **HTTP POST**
3. Save

---

## 7 — Run DB Migration

In Supabase → SQL Editor → run:

```sql
-- From backend/migrations/001_per_salon_api_keys.sql
ALTER TABLE salons ADD COLUMN IF NOT EXISTS api_key TEXT;
UPDATE salons SET api_key = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '') WHERE api_key IS NULL;
ALTER TABLE salons ALTER COLUMN api_key SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS salons_api_key_idx ON salons (api_key);
```

---

## 8 — Test end-to-end

1. Open your Vercel URL → you should see the Ping login page
2. Register a salon via WhatsApp sandbox: message `JOIN <your-sandbox-word>` to +1 415 523 8886
3. Then send `HI` → follow the booking flow → you'll get an API key
4. Enter the API key in the dashboard → you're in

---

## URLs for your resume

| What | URL |
|------|-----|
| Live dashboard | `https://ping-me.vercel.app` |
| Backend API | `https://YOUR-RAILWAY-URL` |
| API docs | `https://YOUR-RAILWAY-URL/docs` |
| GitHub | `https://github.com/YOUR_USERNAME/ping-me` |

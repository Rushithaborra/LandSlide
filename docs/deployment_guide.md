# Deployment Guide — Permanent Hosting

Moves the backend + database off this laptop onto free, permanent, publicly-reachable hosting: **Supabase** (Postgres + PostGIS database) + **Render** (the FastAPI app itself). Both confirmed free-tier, no credit card, as of this session (verified via live search, not assumed from memory).

**Photo storage**: `POST /reports` now uploads citizen-report photos to **Supabase Storage** (not local disk — a deployed host's filesystem is ephemeral and would wipe them on every restart). Same Supabase project as the database, so no extra service to set up — just one more bucket. `photo_url` in API responses is now a full, directly-viewable Supabase URL (previously a relative `/uploads/...` path needing the base URL prefixed — that's gone, this is simpler for E's frontend now).

## Part 1 — Database: Supabase (you do this)

1. Go to https://supabase.com, sign up (GitHub login is fastest since you already have that)
2. Create a new project — name it something like `landslide-ews`, pick a region close to India (Singapore is usually closest), set a database password (**save it somewhere** — you'll need it for the connection string)
3. Once the project is ready, go to **Database → Extensions**, search for `postgis`, enable it
4. Go to **Project Settings → Database**, copy the **Connection string** (URI format) — looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
   Replace `[YOUR-PASSWORD]` with the real password from step 2.
5. Go to **Storage** (left sidebar), click **New bucket**, name it `citizen-reports`, toggle **Public bucket** on (so `photo_url` values are directly viewable, matching how the local version worked)
6. Go to **Project Settings → API**, copy the **Project URL** (e.g. `https://xxxxxxxxxxxx.supabase.co`) and the **`service_role` secret key** (not the `anon`/`public` one — service_role is needed to write to storage from the backend)

**Give me the connection string, the Project URL, and the service_role key when ready.** These are project-scoped secrets for a project only you control (not a login/account credential), which is why I can use them directly — same category as the database URL. I won't send them anywhere beyond configuring this app.

## Part 2 — Push this repo to GitHub (you create it, I push)

1. Go to https://github.com/new
2. Repository name: e.g. `landslide-ews-backend` — **Private** is fine (Render can still access private repos once you connect your GitHub account to Render)
3. **Do not** initialize with a README/gitignore/license — leave it completely empty (we already have all that)
4. Click **Create repository**, then copy the repo URL it shows you (`https://github.com/<you>/landslide-ews-backend.git`)

**Give me that URL** — I'll add it as a git remote and push. The push will pop up your own browser to log into GitHub (via Git Credential Manager, already installed) — that part's on your side, I never see your GitHub password.

## Part 3 — Deploy to Render (mostly you, guided)

1. Go to https://render.com, sign up (GitHub login again is fastest, and lets Render read your repos directly)
2. Dashboard → **New → Blueprint**
3. Connect the `landslide-ews-backend` repo you just pushed — Render will detect `render.yaml` (already in this repo) and pre-fill the web service config
4. It'll ask you to fill in the values marked `sync: false` in `render.yaml` — these are the ones I can't safely commit to the repo:
   - `DATABASE_URL` → the Supabase connection string from Part 1
   - `SUPABASE_URL` → the Project URL from Part 1
   - `SUPABASE_SERVICE_ROLE_KEY` → the service_role key from Part 1
   - `RAINFALL_THRESHOLD__REGION` → `Sikkim (regional)`
   - `RAINFALL_THRESHOLD__COEFFICIENT` → `43.26`
   - `RAINFALL_THRESHOLD__EXPONENT` → `-0.78`
   - `RAINFALL_THRESHOLD__SOURCE` → `Harilal, Madhu, Ramesh & Pullarkatt (2019), Landslides 16(12), 2395-2408`
   - `RAINFALL_THRESHOLD__SOURCE_DOI` → `10.1007/s10346-019-01244-1`
5. Click **Apply** / **Deploy** — first build takes a few minutes

You'll get a permanent URL like `https://landslide-ews-backend.onrender.com`.

## Part 4 — I run the migration + verify (once you give me the URL + confirm deploy succeeded)

```bash
DATABASE_URL="<supabase connection string>" python scripts/migrate.py
curl https://landslide-ews-backend.onrender.com/health
```

Then re-run `scripts/integrate_zone_predictions.py` pointed at the new URL to reload the 3921 real zone predictions (they only exist in the local database right now).

## Part 5 — E's form hosting (separate, E's side — pointer only)

Since E's form is static HTML/JS with no server of its own: **Firebase Hosting**, **Vercel**, or **Netlify** are all free, permanent, and take about 5 minutes (drag-and-drop or a one-command CLI deploy). It just needs to point its `fetch()`/`axios` calls at the new Render URL instead of the old temporary tunnel URL. Not something I'll set up (it's not this repo), but happy to help E's side too if useful.

## Known limitations of this setup

- Render free tier **spins down after 15 minutes of inactivity** — the next request after that takes ~30-60s to wake up. Fine for a hackathon demo, not for a always-instant production feel. (Upgrading to a paid Render plan removes this — a decision for you, not something I can pay for.)
- Supabase free tier: 500MB database + 1GB file storage, more than enough for this project's current size.
- The `citizen-reports` bucket is **public** (anyone with a photo's URL can view it, matching how the old local `/uploads/` endpoint worked — no auth either way). Fine for a hackathon demo; revisit before any real deployment with actual citizen data.

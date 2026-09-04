# Citizen Report App

The citizen-facing "report ground conditions" form for the Landslide EWS. Submits directly to the backend's `POST /reports` (see `../docs/backend_api_for_E.md` for the full contract).

## Local dev

```bash
npm install
npm run dev
```

Talks to `http://localhost:8000` by default (the backend running locally). To point at a different backend, copy `.env.example` to `.env` and set `VITE_API_BASE_URL`.

## Production build

```bash
npm run build
```

Outputs a static site to `dist/` — deployable to Vercel/Netlify/any static host. Set `VITE_API_BASE_URL` in the host's dashboard to the live backend URL (e.g. the Render URL) before building.

## What's implemented

- Report type, severity, GPS-or-place-name location, optional photo, description (typed or voice via Web Speech API), optional reporter name/phone
- Offline-safe retries: a `client_report_id` (UUID) is generated per report attempt and reused if a submission is retried, so the backend can dedupe instead of creating a duplicate
- Backend reachability check on load (`GET /health`)
- Structured validation errors from the backend surfaced directly in the UI

## Known gap

The connectivity banner still says "offline queueing isn't wired up yet" — actual offline queueing (saving a report locally when there's no signal, syncing later) is not implemented in this version of the component. If that's needed, it's the next thing to build here.

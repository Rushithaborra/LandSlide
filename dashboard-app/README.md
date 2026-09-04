# SIH_draft_2 — Landslide Early Warning System

Frontend dashboard for the AI-based Landslide Early Warning System, built to
match the reference design and the 6-stage GIS data pipeline. It runs fully
on mock data today so the team isn't blocked on the backend — see
`LINKING_GUIDE.md` for exactly where to plug in real APIs later.

## Tech stack, and why

| Layer | Tool | Why |
|---|---|---|
| Framework | **React 19 + Vite** | Matches the "React + Leaflet/Mapbox" frontend called out in the pipeline diagram. Vite gives fast local dev and a simple `npm run build`. |
| Styling | **Tailwind CSS** | Lets the whole dashboard (cards, sidebar, tables) be styled quickly and consistently without writing a separate CSS file per component. |
| Routing | **react-router-dom** | Turns the sidebar into real, bookmarkable pages (Overview, Live Map, Alerts, etc). |
| Map | **Leaflet + react-leaflet + OpenStreetMap tiles** | 100% free and open-source — no Mapbox/Google Maps API key or billing needed, unlike the Mapbox option shown in the diagram. |
| Charts | **Recharts** | Free, React-native charting library for the rainfall trend bar chart. |
| Icons | **lucide-react** | Free icon set matching the clean line-icon style in the reference dashboard. |

Everything above is free and open-source — no paid API keys are required to
run this project as-is.

## Project structure

```
SIH_draft_2/
├── src/
│   ├── data/mockData.js        # all fake/sample data in one place
│   ├── services/api.js         # every backend hookup point (see LINKING_GUIDE.md)
│   ├── components/             # Sidebar, Topbar, StatCard, RiskMap, AlertTicker, charts, tables
│   ├── layouts/DashboardLayout.jsx
│   ├── pages/                  # one file per sidebar page
│   ├── App.jsx                 # route definitions
│   └── main.jsx                # React entry point
├── LINKING_GUIDE.md             # where teammates plug in real backend work
├── CHANGES_DRAFT_2.md            # what changed vs. draft 1 (palette + ticker)
├── .env.example                 # copy to .env once a backend URL exists
└── package.json
```

## Running the project (VS Code)

1. Open the `SIH_draft_2` folder in VS Code (`File -> Open Folder...`).
2. Open a terminal in VS Code (Ctrl+`) and run:

```bash
npm install
npm run dev
```

3. Open the printed local URL (usually `http://localhost:5173`) in your browser.

Other useful commands:

```bash
npm run build     # production build, output in dist/
npm run preview   # serve the production build locally
```

Recommended (optional) VS Code extensions: **ES7+ React/Redux snippets**,
**Tailwind CSS IntelliSense**, **Prettier**.

## What's real vs. mock right now

- **Real / working:** the whole UI, routing, the map (OpenStreetMap tiles,
  no key needed), charts, tables, the citizen-report submit form (stores in
  local component state).
- **Mock:** every number on screen comes from `src/data/mockData.js` through
  `src/services/api.js`, standing in for the backend team's FastAPI + PostGIS
  work described in the pipeline diagram.

See `LINKING_GUIDE.md` for the exact list of what each teammate needs to
build and where their output plugs in.


---

## What changed in draft 2

Only two things — the **colour palette** and a new **scrolling alert ticker**.
No data, no folder names, no component logic, no link spots were removed.
Full detail in `CHANGES_DRAFT_2.md`.

### 1. Colour palette — "Field Office"

Draft 1 used the stock blue / indigo / cold-slate combination that every
auto-generated dashboard ships with. Draft 2 replaces it with a warmer,
hand-picked set that reads like a real government field-office tool and
matches the earthy subject matter (soil, rain, hillsides):

| Token | Hex | Used for |
|---|---|---|
| `ink-950` | `#1d2723` | Sidebar, dark buttons |
| `ink-900` | `#26332e` | Headings, primary buttons |
| `paper-100` | `#f5f2ea` | Page background (warm, not blue-grey) |
| `paper-200` | `#e9e4d8` | Card borders, dividers |
| `paper-600` | `#6b6459` | Secondary text |
| `teal-600` | `#15606b` | Links, focus rings |
| `risk.high` | `#b4472f` | Terracotta — High risk |
| `risk.moderate` | `#c8871d` | Turmeric — Moderate risk |
| `risk.low` | `#5b8c4f` | Moss — Low risk |

All of these live in **`tailwind.config.js`**. To re-theme the entire app
later, edit that one file — every component references the colours by name.
Headings also use **Source Serif 4** for a printed-bulletin feel; body text
stays Inter for legibility at small sizes.

### 2. Scrolling alert ticker

A running warning strip, modelled on the marquee at the top of
[mausam.imd.gov.in](https://mausam.imd.gov.in/responsive/rainfallinformation.php).
It sits under the header on **every** page.

- File: `src/components/AlertTicker.jsx`
- Animation: `src/index.css` (`.ticker-track`, `@keyframes ticker-scroll`)
- Mounted in: `src/layouts/DashboardLayout.jsx`
- Data: `tickerBulletins` in `src/data/mockData.js`
- Backend hookup: **LINK SPOT I** → `getTickerBulletins()` in `src/services/api.js`

It pauses on hover, has a keyboard-accessible Pause/Play button, and turns
itself off for users who set "reduce motion" in their OS.

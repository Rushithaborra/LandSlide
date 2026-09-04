# Draft 1 → Draft 2: exactly what changed

Nothing was deleted, renamed, or restructured. Same folders, same file names,
same mock data, same LINK SPOTS A–H. Draft 2 adds a new colour palette, one
new component, and one new link spot (I).

---

## 1. Files ADDED (2)

| File | What it is |
|---|---|
| `src/components/AlertTicker.jsx` | The scrolling warning strip |
| `CHANGES_DRAFT_2.md` | This file |

## 2. Files EDITED (18)

| File | Change |
|---|---|
| `tailwind.config.js` | New `ink` / `paper` / `teal` / `risk` colour scales + marquee keyframes. **This is the only file you edit to re-theme everything.** |
| `src/index.css` | Warm page background, ticker animation CSS, reduced-motion fallback, Source Serif font import |
| `src/layouts/DashboardLayout.jsx` | Mounts `<AlertTicker />` under the header; fetches bulletins every 5 min |
| `src/data/mockData.js` | **Appended** section I (`tickerBulletins`). Nothing existing was touched. |
| `src/services/api.js` | **Appended** LINK SPOT I (`getTickerBulletins`). Nothing existing was touched. |
| `src/components/Sidebar.jsx` | Recoloured to the new dark `ink` surface |
| `src/components/Topbar.jsx` | Recoloured; serif page title |
| `src/components/StatCard.jsx` | Recoloured trend text |
| `src/components/AlertsPanel.jsx` | Recoloured severity badges |
| `src/components/RecentAlertsTable.jsx` | Recoloured severity badges |
| `src/components/RiskMap.jsx` | Map dot colours → earth pigments |
| `src/components/RiskLegend.jsx` | Legend colours → earth pigments |
| `src/components/RainfallChart.jsx` | Bar / grid / threshold-line colours |
| `src/pages/*.jsx` (9 pages) | Recoloured only — no logic or text changes |
| `index.html` | Added `theme-color` meta |
| `public/favicon.svg` | Replaced the default Vite purple bolt with a slope-and-sun mark in the new palette |
| `package.json` | `npm run lint` now scans `src` only (was scanning `node_modules` too) |
| `README.md` | Added a "What changed in draft 2" section |

**Untouched:** `vite.config.js`, `postcss.config.js`, `.env.example`,
`.oxlintrc.json`, `src/App.jsx` (routes), `LINKING_GUIDE.md` stages A–F.

---

## 3. Colour mapping (draft 1 → draft 2)

| Old (cold / stock) | New (warm / human) | Why |
|---|---|---|
| `navy-950 #0b1220` | `ink-950 #1d2723` | Pine-charcoal instead of tech-blue |
| `slate-100 #f1f5f9` | `paper-100 #f5f2ea` | Warm paper, not blue-grey |
| `slate-200` borders | `paper-200 #e9e4d8` | Softer, warmer edge |
| `slate-400/500` text | `paper-500/600` | Warm grey, better contrast |
| `blue-600` links | `teal-600 #15606b` | Deep monsoon teal |
| `#e5484d` High | `#b4472f` terracotta | Printed hazard-map pigment |
| `#f5a623` Moderate | `#c8871d` turmeric | Same |
| `#2fb344` Low | `#5b8c4f` moss | Same |
| `#93b4e8` chart bars | `#7ea6ac` muted teal | Sits on paper without glowing |

---

## 4. The ticker, in one paragraph

`AlertTicker.jsx` renders the same list of bulletins **twice** side by side,
then CSS slides the whole track left by exactly `-50%` (one full copy) on a
loop. The moment copy #2 reaches the start position, the animation restarts —
so the text appears to scroll forever with no jump. Hovering, or tabbing into
the strip, pauses it (`animation-play-state: paused`); there is also an explicit
Pause/Play button. Scroll duration is computed from total text length so a long
batch of bulletins does not race past. Users with "reduce motion" enabled get a
static, horizontally scrollable strip instead.

---

## 5. To go live with the ticker

Open `src/services/api.js`, find **LINK SPOT I**, and replace:

```js
return fakeDelay(tickerBulletins);
```

with:

```js
const res = await fetch(`${BASE_URL}/api/bulletins/ticker`);
return res.json();
```

The endpoint must return an array of:

```json
[
  { "id": "TK-1", "severity": "High", "text": "one sentence, plain text", "issuedAt": "issued 03 Sep, 08:30 IST" }
]
```

`severity` must be exactly `"High"`, `"Moderate"` or `"Low"` — that is what
picks the colour of the label in front of each line.

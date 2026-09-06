# Draft 2 → Draft 3: exactly what changed

Every requested change is listed below with the file it lives in.

**Preserved untouched:** the colour palette in `tailwind.config.js` (the seven
light-mode colours are byte-for-byte the same), the fonts, the scrolling alert
ticker, all mock data that existed before, all LINK SPOTS A–I, `vite.config.js`,
`postcss.config.js`, `.env.example`, `.oxlintrc.json`, `LINKING_GUIDE.md`
stages A–F, and `CHANGES_DRAFT_2.md`.

---

## 1. Overview page — `src/pages/Overview.jsx`, `src/components/AlertsPanel.jsx`

| # | Requested | Done |
|---|---|---|
| A1 | Remove the whole "Recent Alerts" box | The card, its import, its state and its API call are all gone from `Overview.jsx`. `RecentAlertsTable.jsx` itself is **kept** — the Alerts page still uses it. |
| A2 | Remove the "Go to Alerts →" button | Removed from `AlertsPanel.jsx`. The "View all" link at the top of the panel is untouched. |
| A3 | Remove "Alerts are based on rainfall thresholds and susceptibility analysis." | Removed with the same footer block. |
| A4 | Make the Rainfall Trend card a large rectangle | It now spans the full width of the page and is 340 px tall (was 256 px in a half-width card). `RainfallChart` gained an optional `height` prop; its default is the old 256 px, so nothing else changed. |

## 2. Admin details — `src/components/AdminDrawer.jsx` (new), `src/components/Topbar.jsx`

- New mock record `adminProfile` appended to `src/data/mockData.js` (section J).
- New **LINK SPOT J** in `src/services/api.js`: `getAdminProfile()` / `updateAdminProfile()`.
- Clicking the avatar in the top bar slides in a right-hand drawer with: full
  name, designation, department, employee ID, email, phone, district, region,
  alert channel and last login.
- Press **Edit details** to make every field an input, then **Save changes**
  (or **Cancel**). Closing: the **X**, clicking outside, or the Escape key.

## 3. Light / dark theme — `src/context/ThemeContext.jsx` (new), `src/components/ThemeToggle.jsx` (new)

- The toggle sits **to the right of the notification bell and to the left of the
  avatar**, exactly as asked.
- **Light mode is identical to draft 2.** Not one light-mode class was changed —
  the dark theme is added purely with Tailwind `dark:` variants that only apply
  when `<html>` carries the class `dark`.
- `darkMode: "class"` was added to `tailwind.config.js`, along with a new
  `night` colour scale (dark surfaces) and `risk.*On` colours (readable pigment
  text on dark). Nothing existing in that file was edited.
- The choice is saved in `localStorage`, so it survives a refresh. If the user
  has never chosen, the operating system's setting is followed.
- Things Tailwind classes cannot reach — `<body>`, the Leaflet map backdrop,
  Leaflet's own zoom buttons, the scrollbar — get a handful of `html.dark`
  rules at the end of `src/index.css`. The light rules above them are untouched.
- Two components read the theme in JavaScript because their colours are props,
  not classes: `RainfallChart` (grid, ticks, tooltip) and `RiskMap` (in dark it
  switches to CARTO's free dark basemap; light keeps OpenStreetMap). `StatCard`
  tints its icon chip in dark. All three keep their exact light values.

## 4. Citizen Reports — `src/pages/CitizenReports.jsx`, `src/components/CitizenReportModal.jsx` (new)

| # | Requested | Done |
|---|---|---|
| D1 | Remove the "Submit a report" block | Removed, along with its form state and the `submitCitizenReport` import. The API function itself is **kept** in `api.js` for the PWA team. |
| D2 | Centre the page, fill the empty space | The submissions list is now a centred column (`max-w-4xl mx-auto`) with larger rows and photo thumbnails. |
| D3 | Click a report → full details in a modal on the same page | `CitizenReportModal.jsx`. Shows the uploaded photo, area, location + coordinates + landmark, upload date and time, the submitter's name, type and phone, the weather when reported, and their comment. |
| D4 | Close (X) option | Top-right of the modal header. Clicking the backdrop or pressing Escape also closes it. |
| D5 | Verify button, right corner | Bottom-right of the modal. Pressing it calls **LINK SPOT K** and updates the badge **in the list behind the modal** to "Verified". Every other report keeps showing "Pending verification" until it is verified too. |

The two original reports kept all their original fields; the new detail fields
were added alongside. A third report (CR-202, Chungthang) was added so the
Incidents PDF for IN-88 has citizen reports from its own area to include.

## 5. Pages removed

| File deleted | Route removed | Sidebar link removed |
|---|---|---|
| `src/pages/LiveMap.jsx` | `/live-map` | Live Map |
| `src/pages/Settings.jsx` | `/settings` | Settings |
| `src/pages/Reports.jsx` | `/reports` | Reports |

The map component `RiskMap.jsx` is **kept** — it still renders on the Overview
page. Only the standalone Live Map page is gone.

## 6. Reports moved into Incidents — `src/pages/Incidents.jsx`, `src/services/incidentReport.js` (new)

- A new last column, **Report**, with a horizontally aligned **Download** button
  on every incident row.
- Pressing it produces a PDF named e.g. `IN-88_Chungthang_report.pdf`
  containing:
  1. Incident ID, location, area, date, severity, status, casualties, impact
  2. Weather report for the event
  3. Rainfall trend before the event — table values drawn as a bar chart, with
     bars above the 100 mm trigger threshold shown in terracotta
  4. Previous recorded activity in that area
  5. Response summary
  6. Every citizen report filed from the same area, with status, reporter,
     comment and coordinates
- Built in the browser with **jsPDF** (free, MIT). No backend needed.
- **LINK SPOT L** documents how to swap this for a server-rendered PDF later.

## 7. Files added (7)

```
src/context/ThemeContext.jsx          light / dark state
src/components/ThemeToggle.jsx        the toggle button
src/components/AdminDrawer.jsx        editable admin side drawer
src/components/CitizenReportModal.jsx report detail modal + verify
src/services/incidentReport.js        the PDF generator
public/photos/*.svg                   3 placeholder citizen photos
CHANGES_DRAFT_3.md                    this file
```

## 8. Dependency added (1)

`jspdf` — for the incident PDF. Free, MIT licensed, runs in the browser.

## 9. Verified

| Check | Result |
|---|---|
| `npm run build` | 0 errors |
| `npm run lint` | 0 warnings |
| Every page in light mode | Loads clean, no console errors |
| Every page in dark mode | Loads clean, no console errors |
| Toggle light → dark → light | Works both directions |
| Theme survives a page reload | Yes |
| Verify a report | Badge changes to "Verified" behind the modal; others stay "Pending verification" |
| Download an incident PDF | 2-page PDF produced and opened |

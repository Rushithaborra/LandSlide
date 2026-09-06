# Draft 4 → Draft 5

Two features built: **global search** and the **notification bell**. Both are
finished on the frontend and run on mock data, with their backend connection
points documented as LINK SPOT M and LINK SPOT N.

Nothing else changed — same palette, same fonts, same pages, same layout, same
existing link spots A–L.

---

## 1. Global search — LINK SPOT M

**New file:** `src/components/SearchBox.jsx`

Searches four things at once: **Zones, Alerts, Incidents and Citizen reports.**

| Behaviour | Detail |
|---|---|
| Live results | A dropdown opens as you type |
| Grouped | Results are split under Zones / Alerts / Incidents / Citizen reports headings |
| Highlighted | The matching part of each result is shown in bold |
| Keyboard | ↑ ↓ to move, Enter to open, Esc to close |
| Shortcut | **Ctrl+K** (Windows) or **Cmd+K** (Mac) jumps into the box from anywhere |
| Debounced | Waits 200 ms after you stop typing before searching, so the backend is not hit once per keystroke |
| States | Spinner while searching, "Nothing found for …" when empty |
| Navigation | Clicking or pressing Enter opens the page that result lives on |

**Where the data comes from:** `searchIndex` in `src/data/mockData.js`. It is
**built from the data already in that file** — zones, alerts, incidents and
citizen reports are mapped into one flat list — so nothing is duplicated and
it can never drift out of sync with the rest of the mock data.

**To go live**, the backend team replaces the body of `searchAll()` in
`src/services/api.js` with:

```js
const res = await fetch(`${BASE_URL}/api/search?q=${encodeURIComponent(query)}`);
return res.json();
```

The endpoint must return one merged array of
`{ id, type, title, subtitle, to }`, where `type` is one of
`"Zone" | "Alert" | "Incident" | "Citizen report"` and `to` is the frontend
route to open. **`SearchBox.jsx` does not change at all.**

## 2. Notification bell — LINK SPOT N

**New file:** `src/components/NotificationsPanel.jsx`

| Behaviour | Detail |
|---|---|
| Unread badge | A red count on the bell — 3 unread in the sample data |
| Panel | Click the bell for the list: title, one-line detail, severity colour, time |
| Navigate | Clicking an item marks it read and jumps to the relevant page |
| Mark all as read | Clears the badge in one press |
| Close | Click away or press Escape |

**One honest limitation, stated in the panel itself and in the Help page:**
"unread" means unread *by a particular officer*, and this project has no login
yet. So today every visitor sees the same list, and "Mark all as read" lasts
only until the page is reloaded. Once authentication is added, the backend
returns that officer's own list and the same code becomes personal — no
changes needed in this file.

**To go live:**
- `GET /api/notifications` → `getNotifications()`
- `POST /api/notifications/read` → `markNotificationsRead()`

Shape: `{ id, title, detail, severity, timeAgo, read, to }`.

## 3. Files changed

| File | Change |
|---|---|
| `src/components/SearchBox.jsx` | **New** — the search box and dropdown |
| `src/components/NotificationsPanel.jsx` | **New** — the bell and its panel |
| `src/components/Topbar.jsx` | The old dead input and dead bell icon replaced with the two new components. Theme toggle and avatar untouched, still in the same order. |
| `src/data/mockData.js` | **Appended** sections K (`searchIndex`) and L (`notifications`). Nothing existing touched. |
| `src/services/api.js` | **Appended** LINK SPOT M (`searchAll`) and LINK SPOT N (`getNotifications`, `markNotificationsRead`). Nothing existing touched. |
| `src/pages/HelpDocs.jsx` | The two Help answers about search and the bell rewritten, since both now work. |
| `LINKING_GUIDE.md`, `README.md` | Documented M and N. |

## 4. Verified in a real browser

| Check | Result |
|---|---|
| `npm run build` | 0 errors |
| `npm run lint` | 0 warnings |
| Search "mangan" | 2 results, correct ones |
| Search "sikkim" | 11 results across all 4 groups |
| Group headings | Zones, Alerts, Incidents, Citizen reports — in that order |
| ↓ ↓ then Enter | Navigates to the highlighted result |
| Search "zzzz" | "Nothing found" message shown |
| Ctrl+K | Focuses the search box |
| Bell badge | Shows 3 unread |
| Mark all as read | Badge clears, label becomes "none unread" |
| Click a notification | Navigates to the right page |
| Both features in dark mode | Correct dark surfaces, no white flash |
| Console errors | None |

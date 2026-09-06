# Draft 3 → Draft 4

Two changes only. Everything else — colours, fonts, layout, data, link spots,
the dark theme, the admin drawer, the report modal, the incident PDF — is
untouched.

---

## 1. The map no longer overlaps the top bar while scrolling

**Cause.** Leaflet gives its own internal layers z-index values from 200 up to
700. The sticky top bar was on z-index 10, so as soon as the page scrolled, the
map tiles painted straight over the header.

**Fix — three small edits:**

| File | Change |
|---|---|
| `src/index.css` | `.leaflet-container` now has `position: relative; z-index: 0; isolation: isolate`. This traps Leaflet's 200–700 layers inside one contained layer instead of letting them compete with the rest of the page. |
| `src/components/Topbar.jsx` | The sticky header moved from `z-10` to `z-30`, comfortably above the map layer and below the drawer (`z-40/50`) and the report modal (`z-50`). |
| `src/pages/Overview.jsx` | The map wrapper is now `relative z-0`, so the risk legend that sits on top of the map is also contained. |

**Verified in a real browser:** with the page scrolled so the map passes behind
the header, `document.elementFromPoint()` at three points across the header
returns header elements every time, never a map element.

## 2. "Help & Docs" is now "Help", with a proper admin Q&A

- Sidebar label and page title changed to **Help** (the route `/help` and the
  file `src/pages/HelpDocs.jsx` are unchanged, so no other file had to move).
- The page is now three grouped, click-to-open sections:

| Section | Covers |
|---|---|
| **Using this dashboard** | Is the search bar working? Is the bell working? Which numbers are real? How do I switch theme? Where do I edit my details? How do I download an incident report? How do I verify a citizen report? Can I pause the warning strip? |
| **How the dashboard updates** | Do the five Overview cards update by themselves? Will Alerts / Incidents / Citizen Reports fill in on their own? How often does the screen refresh? Who writes the scrolling warning text? What if a data feed stops working? |
| **About the data** | The three original questions, word for word, plus why the threshold is 100 mm and how citizens are warned without the dashboard. |

Each question is a collapsible row, so the page stays short and scannable.

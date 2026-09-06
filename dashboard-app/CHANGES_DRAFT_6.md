# Draft 5 → Draft 6

**One change: the Help page was rewritten as a proper help centre for the
officers who will use the deployed system.**

Nothing else was touched — same palette, same fonts, same pages, same layout,
same components, same mock data, same link spots A–N.

---

## Why it changed

Draft 4's Help page answered *development* questions: which parts were still
mock, whether the search box was wired up, what was coming next. Those were the
right questions while the project was being built, and completely the wrong
questions for a district officer sitting in front of a live system at 6 a.m.

Draft 6 replaces them with the questions a real user asks after deployment.

## What the page has now

**42 questions across 7 sections**, each a short, direct answer:

| Section | Questions | Examples |
|---|---|---|
| Everyday use | 6 | What should I check first thing in the morning? Can I leave this open on a wall display? The screen is too bright at night. |
| Reading the risk map | 6 | What do the coloured circles mean? What is susceptibility, and how is it different from risk? Why did a zone go to High with no new rain? |
| Alerts and warnings | 7 | An alert has appeared — what am I expected to do? Does the public get warned automatically? A landslide happened but no alert was raised. |
| Citizen reports and verification | 7 | How do I verify a report? What does Verified actually mean? Is the reporter's phone number confidential? |
| Records and reports | 5 | How do I get a report for a meeting? What is the difference between an Alert and an Incident? |
| When something looks wrong | 6 | The numbers have not changed all day. A data source says Not connected — should I stop trusting the dashboard? The map is blank. |
| Account and access | 5 | How do I update my contact details? Can I see other districts? Is it safe to leave the dashboard open? |

## New on the page

- **A search box at the top** that filters every question *and* answer as you
  type, with a live "3 of 42 answers match" count and a friendly empty state.
  Matching questions open automatically so you can read the answer without a
  second click.
- **A "Still stuck?" block** at the bottom with the control-room number and
  support email, and a note telling the officer exactly what information to
  give the technical desk. The contact details are marked as placeholders to
  be replaced before deployment.
- **A "How can we help?" header** stating how many answers there are and what
  they cover — the standard shape of a help centre.

## Tone

Answers are written for someone who has to act, not someone who is curious.
They say what to do, who is responsible, and when *not* to trust something —
for example, that a down SMS gateway should be escalated immediately, that
verification is not the same as raising an alarm, and that the screen shows
citizens' phone numbers so the computer should be locked when unattended.

## File changed

`src/pages/HelpDocs.jsx` — rewritten. The route stays `/help` and the sidebar
label stays "Help", so no other file needed to change.

## Verified

| Check | Result |
|---|---|
| `npm run build` | 0 errors |
| `npm run lint` | 0 warnings |
| Sections render | 7, in order |
| Questions render | 42 |
| Filter "verify" | 3 of 42, auto-opened |
| Filter with no match | Empty state shown |
| Dark mode | Correct |
| Console errors | None |

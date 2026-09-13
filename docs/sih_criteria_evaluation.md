# Self-Evaluation Against SIH Judging Criteria

**Team:** RESQ · **PS:** SIH26001 · **Purpose of this document:** an honest,
evidence-backed self-score against the criteria SIH judges actually use
(innovation, feasibility, scalability, impact — SIH's own guidance explicitly
rewards "numbers, not buzzwords" and penalizes overpromising without
reasoning). Every score below is justified with a real, checkable fact, and
every weakness is stated plainly, not buried. **Last updated:** 2026-09-13.

Scale used: 1 (weak) – 5 (strong), with justification. This is a working
self-assessment for the team's own prep, not a claim of how judges will
actually score it.

---

## 1. Innovation & Uniqueness — 4/5

**What's genuinely novel:**
- The two-layer architecture (static ML susceptibility × dynamic rainfall
  rule, deliberately never merged into one black-box number) is the one
  design decision worth defending on its own — it means "why did this alert
  fire" always has a two-part, inspectable answer.
- `SUSCEPTIBILITY_MULTIPLIERS` (scaling the rainfall danger threshold by a
  zone's ML-derived risk tier) is this team's own explainable rule, not
  copied from literature — a real, small piece of original design.
- Highway-corridor zoning (500m segments along real OSM road geometry,
  buffered) ties the abstract "risk map" concept to the thing that actually
  matters operationally: which road, which stretch.

**Where it's not novel:** the core technique (Random Forest susceptibility +
rainfall I-D threshold) is standard in landslide science, not a new
algorithm — the innovation is in the integration and honesty, not the ML
itself. Say this plainly if asked; overclaiming algorithmic novelty is
exactly the kind of thing SIH guidance warns against.

## 2. Technical Feasibility & Robustness — 5/5

This is the strongest category, and the one to lead with.

- **It already exists and runs.** Three live services, checkable right now:
  backend (`landslide-ews-backend.onrender.com`), officer dashboard, citizen
  app. Not a mockup, not a local demo.
- **Real, disclosed ML methodology:** two real trained models (765/766 and
  774/774 balanced positive/negative training data, road-distance-matched
  negatives to prevent shortcut-learning), evaluated with 5-fold spatially-
  buffered block cross-validation, not a naive random split. Held-out AUC
  0.774–0.782 and 0.735 respectively — both disclosed, including *why*
  they differ (split strictness), not picked to look better.
- **41 automated tests passing** (24 on the alert/data-pipeline logic, 17 on
  terrain-feature/negative-sampling/spatial-CV correctness).
- **Real bugs found and fixed by actually testing the live system**, not
  just reading code — a documented list exists (map basemap silently
  broken by a CARTO policy change, three separate pages that hung/rendered
  empty on any fetch failure, a citizen-report coordinate bug, a cascading-
  delete bug). Being able to name real bugs you found and fixed is stronger
  evidence of a working system than claiming nothing ever broke.

**Where feasibility is weaker:** no authentication on any endpoint (open
API); free-tier hosting sleeps and rate-limits at scale; SMS/IVR delivery is
designed but not built. All three are named honestly in §4 below, not hidden.

## 3. Scalability — 4/5

- **The pipeline is state-agnostic already**, not Sikkim-hardcoded: it
  consumes Copernicus GLO-30 DEM (global coverage), OpenStreetMap road
  geometry (global), and a state's own GSI landslide inventory — swapping in
  a different state's inventory is the documented next step, not a rebuild.
- **Cost scales linearly, not exponentially:** every service used (Render,
  Vercel, Supabase, Open-Meteo) is free or near-free at pilot scale; the
  real cost driver for NER-wide rollout is SMS/IVR volume and possibly a
  paid hosting tier, both bounded and estimable (see the SMS/IVR roadmap
  already drafted for this project).
- **What actually limits scale today:** the rainfall threshold's exact
  coefficients (43.26, −0.78) are sourced from a Sikkim-specific paper; a
  new state needs its own literature-sourced threshold or a locally
  recalibrated one, not a copy-paste. That's a real, bounded piece of work
  per state, not a blocker.

## 4. Social Impact & Real-World Relevance — 4/5

- **Grounded in a real, current disaster case, not a hypothetical:** the 4
  Oct 2023 South Lhonak GLOF (Sikkim) triggered 45 landslides in one event,
  destroyed 13 bridges and the Teesta-III dam, and affected 60,000+ people —
  this system's target scenario is not invented.
- **NH10, Sikkim's only lifeline highway, has had real, recent, multi-day
  closures in 2025** (5-day, then 6-day closures from single landslides) —
  the Highway Corridors feature (§6.4 of the PRD) speaks directly to this,
  not an abstract "roads matter" claim.
- **The citizen-reporting loop is genuinely two-way**, not just a
  broadcast: a real report reaches a real officer's dashboard for real
  verification — closing the loop SIH's own materials describe as
  "detect → alert → verify."
- **Where impact is still theoretical:** no real SMS/IVR delivery means no
  member of the public has actually received a warning from this system yet
  — the alert *exists*, it is not yet *received*. Say this precisely if
  asked; it is the honest boundary between "built" and "deployed."

## 5. Cost & Viability for Government Adoption — 5/5

- **Zero licensing cost today**, verified: FastAPI, PostgreSQL/PostGIS,
  scikit-learn, React, Leaflet, Render, Vercel, Supabase, Open-Meteo are all
  free/open-source or free-tier at this scale.
- **The only real future costs are named and bounded:** SMS/IVR gateway
  fees (~₹0.15–0.25/SMS, ~₹0.50–1.00/min IVR, both real Indian-provider
  estimates), and a paid hosting tier if traffic outgrows free-tier limits.
  No hidden cost, no vague "enterprise pricing" hand-wave.

## 6. Completeness & Presentation — 3/5 (the honest weak point)

This is where a rival team's polished demo video can outscore this system on
a fast pass, and it's worth saying so plainly rather than pretending
otherwise.

- **What's now covered** (added 2026-09-12 specifically to close this gap):
  Highway Corridors, Emergency Contacts, Alert Broadcast composer, one-touch
  SOS — matching a competing SIH26001 team's feature list point-for-point,
  using only data this system already had.
- **What's still thinner than a from-scratch UI mockup can look:** no
  AI-generated natural-language bulletins, no physical sensor telemetry
  display (deliberately, since no sensors exist — see PRD §5.2), no
  multi-state map view yet.
- **The actual trade being made:** a judge who only watches a demo for 90
  seconds may rate a polished mockup with fabricated-sounding precision
  higher. A judge who asks even one hard question — "what's your AUC,"
  "is that a live link," "show me the training data" — gets a real answer
  here and nothing verifiable from a UI-only competitor. **This system
  should actively invite that question, not wait for it** (hand over the
  live URL unprompted in the first 30 seconds of any pitch).

---

## Summary Table

| Criterion | Score | One-line justification |
|---|---|---|
| Innovation & Uniqueness | 4/5 | Two-layer honesty is the real idea; the ML itself is standard technique, not overclaimed |
| Technical Feasibility & Robustness | 5/5 | Live, tested, disclosed methodology, real bugs fixed |
| Scalability | 4/5 | State-agnostic pipeline; per-state rainfall threshold is the real bounded cost |
| Social Impact | 4/5 | Grounded in a real 2023 disaster + real 2025 highway closures; delivery not yet real |
| Cost & Viability | 5/5 | Zero cost today; future costs named and bounded, not hand-waved |
| Completeness & Presentation | 3/5 | Real gap vs a polished UI-only competitor; closed partially, not fully, this round |

## Prioritized Gaps Before the Next Stage

1. **Resolve the Sikkim-vs-NER scope question with the PS owner/mentor** —
   the literal problem statement says NER; this build is Sikkim only. This
   is the single highest-risk item and should not surface for the first
   time in a judge's question.
2. Decide whether to invest in real SMS/IVR delivery before the next stage,
   or keep presenting the roadmap as a credible, costed next step.
3. Keep the Emergency Contacts "unconfirmed" numbers exactly as flagged —
   do not let anyone quietly mark them verified without an actual check.

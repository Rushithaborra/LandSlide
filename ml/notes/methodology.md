# Methodology notes — susceptibility model + rainfall trigger

Owner: B (ML lead). Shared with the team so nobody relearns this separately.

## 1. Static susceptibility factors (what the ML model trains on)

GSI and the broader Indian landslide-susceptibility literature converge on the
same causative factor groups. We're using the ones A can actually source in
4 days (see `Data_Sources_Checklist.md`):

| Factor | Why it matters | Source |
|---|---|---|
| Slope | Steeper = higher gravitational driving force | Derived from DEM |
| Aspect | Slope-facing direction affects moisture retention, sun exposure | Derived from DEM |
| Drainage density | More water channels nearby = more saturation/erosion | Derived from DEM (or Bhuvan) |
| Lithology | Rock/soil type determines shear strength | GSI Bhukosh geology layer |
| Land use | Vegetation cover stabilizes soil; bare/built-up doesn't | Bhuvan LULC / ESA WorldCover |
| Rainfall (mean annual, as a static baseline feature) | Chronic wetness raises background susceptibility | Open-Meteo historical |

Broader literature (papers on Indian Himalayan susceptibility mapping) also
lists curvature, TWI (topographic wetness index), distance-to-road,
distance-to-stream, distance-to-fault, and NDVI as causative factors used in
15-factor frameworks — these are stretch/"good to have" additions if A
finishes core layers early (see checklist's optional tier), not required for
a defensible first model.

Common methods in the literature: Frequency Ratio, AHP, Shannon Entropy,
fuzzy logic, and ML (logistic regression / random forest / ANN). We're using
logistic regression + random forest — well-documented, explainable, and
appropriate for our data volume (a few hundred points), unlike deep learning.

Sources:
- [Landslide Hazard Zonation in India: A Review](https://www.academia.edu/73886756/Landslide_Hazard_Zonation_in_India_A_Review)
- [Assessment of landslide susceptibility in Tripura, India, using a Multi-Model Approach](https://cwejournal.org/vol2no2/passessment-of-landslide-susceptibility-in-the-himalayan-state-of-tripura-india-using-a-multi-model-approachp)
- [High resolution landslide susceptibility mapping using ensemble ML and geospatial big data](https://www.sciencedirect.com/science/article/abs/pii/S0341816223007440)

## 2. Dynamic rainfall trigger (Person C's layer, not ours — but we cite it here since it's the other half of the two-layer story)

**Use these published Sikkim-specific thresholds instead of inventing one.**
Rainfall intensity I (mm/day) vs. duration D (days) — a landslide is more
likely once cumulative rainfall crosses the curve:

- **Sikkim regional threshold**: I = 43.26 · D^(−0.78)
- **Gangtok-local threshold** (more precise, smaller area): I = 100 · D^(−0.92)
  — derived from daily rainfall + landslide events, 1990–2017, considering
  antecedent rainfall at 1/3/5/7/20-day cumulative windows.
- **North Sikkim Road Corridor**: threshold derived from 155 landslides
  matched against rainfall records — same paper family, road-corridor specific.
- **Lanta Khola (North Sikkim) alternative form**: landslide likely once
  15-day normalized cumulative rainfall exceeds 250 mm (saturation-based,
  not intensity-duration — useful as a cross-check / fallback rule).
- **Broader NE Himalaya threshold** (if Sikkim-specific data is sparse for a
  sub-region): I = 5.8294 · D^(−0.4141).

Hand the Sikkim regional and Gangtok-local formulas to Person C directly —
those are the two to wire into the rule engine. Cite Springer Nature Link
paper below in the pitch deck's "what's real vs simulated" slide.

Sources:
- [Towards establishing rainfall thresholds for a real-time landslide early warning system in Sikkim, India (Landslides, Springer)](https://link.springer.com/article/10.1007/s10346-019-01244-1)
- [Assessment of Rainfall Thresholds for Rain-Induced Landslide Activity in North Sikkim Road Corridor](https://www.academia.edu/104061040/Assessment_of_Rainfall_Thresholds_for_Rain_Induced_Landslide_Activity_in_North_Sikkim_Road_Corridor_in_Sikkim_Himalaya_India)
- [Rainfall thresholds for the initiation of landslide at Lanta Khola in north Sikkim (Natural Hazards, Springer)](https://link.springer.com/article/10.1007/s11069-009-9352-9)

## 3. What this means for the pitch's "Is this AI or just rules?" answer

"Two layers: a trained ML susceptibility model (static, factors above) ×
a rainfall-threshold trigger (dynamic, rule-based, sourced from a published
Sikkim-specific paper — not invented). We're not claiming the trigger layer
is ML — it doesn't need to be, and pretending otherwise would be the kind
of thing that falls apart under a follow-up question."

## 4. Fallback plan (Day 2 hard rule)

If the ML model isn't training on real data by end of Day 2, fall back to a
documented threshold-only model using the Sikkim/Gangtok formulas above,
say so explicitly in the pitch, and cite the papers. A working honest
fallback beats a broken ambitious claim.

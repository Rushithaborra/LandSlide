# Duplicate Resolution + Land-Cover Bias Audit

Generated 2026-09-02, before any model training — this is exactly the kind of check requested to happen before trusting a "great result" tomorrow. No model has been trained. Both scripts referenced here are read-only investigations; `build_training_dataset.py` was re-run to apply the duplicate fix, nothing else changed.

## Part 1 — Duplicate resolution

### Investigation: same event or genuinely distinct?

All 3 duplicate-coordinate pairs were pulled with their full source rows (`scripts/ml/resolve_duplicate_positives.py`, `run_investigation()`):

**Pair 1 — (27.393056, 88.635278), "Kabi Landslide"**
| | Slide_No | History |
|---|---|---|
| Row A | `.../2018/serial no.` (incomplete) | Mid-July 2018, 2 August 2018 |
| Row B | `.../2020/03` | Mid-July 2018, 2 August 2018, **24 May 2020** |

Same name, same location description ("State Highway; 4 km before Kabi village"), same material/movement. Row B's history is a strict superset of Row A's — this is GSI re-logging the **same recurring failure site** after it slid again in 2020. **Clear duplicate**, not two events.

**Pair 2 — (27.426361, 88.583028)**
Both rows: same year (2015), sequential serial numbers (`.../74`, `.../75`), identical district/location/material/movement, no name or history on either to differentiate, coordinates identical to 6 decimal places. **Ambiguous** — could be a duplicate entry, or two closely-spaced slides logged against the same rounded field GPS waypoint. No evidence in the record distinguishes them.

**Pair 3 — (27.437889, 88.601694), "Chawang"**
Same pattern as Pair 2 (2015, sequential serials `.../07`/`.../08`), one row has the place name "Chawang," the other doesn't. Same ambiguity.

### Resolution and why it's defensible either way

All three treated as duplicates and deduplicated. For Pair 1 this is close to certain. For Pairs 2 and 3, it's a judgment call — but a low-risk one: two rows at the **exact same coordinate** produce **identical DEM and land-cover feature values** (same pixel). Whether they're truly one event or two, keeping both adds zero new information and only inflates that one location's weight in training. Deduplicating costs nothing either way.

**Rows removed** (kept the more complete record — has a name, or the longer history — per pair):
| Dropped Slide_No | Coordinate | Reason |
|---|---|---|
| `State: Sikkim/district: North.../2018/serial no.` | 27.393056, 88.635278 | Superseded by the 2020-updated record for the same site |
| `SKM/NS/78A11/2015/75` | 27.426361, 88.583028 | No distinguishing info vs. `.../74`; lower serial kept |
| `SKM/NS/78A11/2015/08` | 27.437889, 88.601694 | No name vs. `.../07`, which has "Chawang" |

**777 → 774 positives.** Wired into `build_training_dataset.py` so this is now automatic on every rebuild, not a one-off manual fix.

### Re-run integrity checks (post-dedup)

| Check | Result |
|---|---|
| Exact duplicate coordinates | **0** (was 6) |
| Positive/negative coordinate overlap | 0 |
| Min inter-class distance | 203.7m (≥ 200m exclusion buffer) |
| Class balance | 774 / 774, ratio 1.000 |
| District proportions | Exact match, all districts |
| Missing / infinite values | None |
| Leakage-prone fields | None present |

Final dataset: **1548 rows** (774 + 774), same 9 columns as before (path unchanged: `data/processed/training_dataset.csv`).

---

## Part 2 — Land-cover bias investigation

### The question

The earlier review found built-up land cover at 9.0% of positives vs 0.3% of negatives (~30×). Before trusting that as genuine terrain signal, checked whether it's actually a restatement of the known road-survey bias (positives are GSI road-cut inspections — median distance to road is tiny; negatives are spread across a wider corridor).

**Important**: `distance_to_road` was computed here **purely as a diagnostic**. It is not, and will not be, added to `training_dataset.csv` or used as a model feature — using it as a feature would leak the sampling process itself into the model. Using it here to *check* for that leakage is the opposite move.

### What the numbers show

1. **Distance-to-road is a strong confound in this dataset**, as expected: point-biserial correlation between label and distance-to-road is **r = -0.545** (positives median 9.6m from a road; negatives median 127m). This is exactly why distance-to-road is correctly excluded as a feature — it would be close to the strongest "predictor" available, and it would just be re-encoding how positives were surveyed.

2. **Built-up land itself clusters near roads**, independent of label: median distance-to-road for built_up pixels (both classes combined) is 8.7m, vs. 29.6m for tree_cover. This is an expected, real geographic pattern — settlements and junctions sit on roads.

3. **The critical test — does the gap survive controlling for distance?** Stratifying by distance-to-road bin:

   | Distance to road | Positives built-up % | Negatives built-up % |
   |---|---|---|
   | 0–20m | 10.6% (67/633) | **0.0% (0/86)** |
   | 20–50m | 3.4% (3/89) | 1.0% (1/98) |
   | 50–150m | 0.0% (0/28) | 0.4% (1/258) |
   | 150m+ | ~0% | ~0% |

   If built-up were *purely* a road-proximity proxy, this gap should shrink to near-zero once distance is held constant — instead, at the same 0–20m proximity, positives are built-up **10.6% of the time and negatives 0%**. See `data/processed/landcover_bias_audit.png` — the bars don't converge.

4. **Is 0/86 just a small sample?** No — checked. If negatives near roads truly had built-up rate similar to positives' 10.6%, the probability of observing zero out of 86 by chance is roughly 1 in 10,000. This gap is real, not noise.

### Honest interpretation

Built-up land cover carries **signal beyond simple road proximity** — the confounding hypothesis ("it's just road distance in disguise") does not fully hold up. But two mechanisms remain equally plausible and this data can't separate them:
- **Genuine anthropogenic destabilization**: construction/road-cutting near settlements measurably weakens slopes — a real, literature-supported effect
- **Reporting/documentation bias**: GSI may be more likely to *log* a landslide that threatens a building or blocks a road near a settlement than one that fails unreported in remote forest — a bias in what gets into the inventory at all, not in the terrain itself

Either way, built-up land's association with landslides in this dataset is not simply the road-survey artifact restated. It's a real pattern in the data, with an honestly ambiguous cause.

---

## Two candidate feature sets, ready for approval

| Set | Features |
|---|---|
| **Baseline** | elevation, slope, curvature, distance_to_drainage |
| **Extended** | Baseline + land_cover_class (one-hot) |

Both are subsets of columns already in `data/processed/training_dataset.csv` — no rebuild needed to select either at training time. Per instruction, both will be trained and evaluated on the **same spatially defensible holdout** (not a naive random split, given how spatially clustered this data is) once you approve moving forward.

**Not yet done**: training either model. Waiting for the go-ahead.

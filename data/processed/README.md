# NER training datasets — read before using

Same 13-column schema as Sikkim's `training_table.csv`:
`lon, lat, elevation_m, slope_deg, aspect_deg, distance_to_stream_m,
landcover_class, soil_erodibility_k, rusle_ls_factor, rusle_c_factor,
rainfall_erosivity_r, soil_loss_tha_yr, label`

| File | Rows | Rainfall data quality |
|---|---|---|
| `training_dataset_manipur.csv` | 2,865 | Good — 384/506 rainfall grid points fetched (76%) |
| `training_dataset_nagaland.csv` | 3,128 | Good — 348/552 fetched (63%) |
| `training_dataset_mizoram.csv` | 3,751 | **Poor — only 24/496 fetched (4.8%)** |
| `training_dataset_meghalaya.csv` | 1,764 | **Very poor — only 12/540 fetched (2.2%)** |

## ⚠️ Mizoram and Meghalaya: `rainfall_erosivity_r` and `soil_loss_tha_yr` are unreliable

Every column in these two files is real *except* `rainfall_erosivity_r`
and the `soil_loss_tha_yr` column derived from it. Those were built by
interpolating from Open-Meteo API fetches, and the fetch succeeded for
almost none of the sample grid — Meghalaya's entire training set is
built from just **12 real points** (10 distinct values across the whole
state), Mizoram's from **24**. This is not a fabricated column — every
value traces to a real, if extremely sparse, source — but it does not
represent real spatial rainfall variation and should not be trusted as a
feature for these two states without redoing the fetch.

Root cause: Open-Meteo's archive API throttled this session's IP after
many hours of sustained use across all 6 states. Manipur and Nagaland
happened to run rainfall during less-throttled windows and are fine;
Mizoram and Meghalaya did not.

**Before using these two files for modeling**: either re-run
`scripts/21_compute_state_rainfall_erosivity.py mizoram` /
`... meghalaya` once Open-Meteo has recovered (check with the health-check
command in `HANDOFF_remaining_states.md` first), or drop
`rainfall_erosivity_r` and `soil_loss_tha_yr` as features for these two
states specifically rather than trusting the current values.

Full context, including Assam/Arunachal Pradesh's status and every bug
found while building this: `../HANDOFF_remaining_states.md` and
`../docs/dataset_inventory.md`.

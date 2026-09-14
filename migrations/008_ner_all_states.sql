-- NER expansion, phase 1 continued: zones.state's CHECK constraint only
-- allowed 'Sikkim', 'Assam', 'Mizoram' (migrations/004_zone_state.sql),
-- forcing a new migration every time the pipeline reached a new state.
-- Widen it to all 8 real North Eastern Region states now, so future phases
-- (sourcing each state's real GSI inventory and running the DEM/terrain/
-- training pipeline -- the actual hard part, see CLAUDE.md) can add real
-- zone rows directly without touching this constraint again. This does NOT
-- add any zones, DEM tiles, road bboxes, or rainfall thresholds for the
-- newly-allowed states -- see scripts/ml/ml_config.py's STATE_CONFIGS and
-- app.config.settings.rainfall_thresholds, both still populated only for
-- states with real, sourced data (Sikkim, Assam).

ALTER TABLE zones DROP CONSTRAINT IF EXISTS zones_state_check;
ALTER TABLE zones ADD CONSTRAINT zones_state_check CHECK (
    state IN (
        'Sikkim', 'Assam', 'Arunachal Pradesh', 'Manipur',
        'Meghalaya', 'Mizoram', 'Nagaland', 'Tripura'
    )
);

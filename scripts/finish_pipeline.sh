#!/bin/bash
# Self-healing reconciliation loop for the last 3 states (Nagaland, Assam,
# Arunachal Pradesh). Re-derives what still needs to run from what's
# actually on disk every cycle, rather than trusting any single process to
# survive to the end -- this environment has already killed background
# work once on a session restart, and DEM/WorldCover/road/rainfall-batch
# caching make every step safe to just re-launch.
#
# Plan: Nagaland alone first (in progress), then Assam + Arunachal Pradesh
# in parallel (safe now -- their memory-heavy hydrology step is already
# done for both, and their rainfall workload was coarsened from ~270/~193
# batches down to ~39/~28 by widening the sample grid for just these two
# states -- see scripts/21's COARSE_GRID_STATES).
set -u
cd "$(dirname "$0")/.."
LOGDIR=data/interim/ner_pipeline_logs
mkdir -p "$LOGDIR"

done_csv() { [ -f "data/processed/training_dataset_$1.csv" ]; }
running() { pgrep -f "run_all_ner_states.sh $1" > /dev/null; }

launch() {
  local state="$1"
  echo "[finish_pipeline] $(date) launching $state"
  nohup ./scripts/run_all_ner_states.sh "$state" > "$LOGDIR/_final_${state}.log" 2>&1 &
  disown
}

while true; do
  if done_csv nagaland && done_csv assam && done_csv arunachal_pradesh; then
    echo "[finish_pipeline] $(date) all 3 states have a training_dataset CSV -- done"
    break
  fi

  if ! done_csv nagaland; then
    # Nagaland is already running under a separate, pre-existing process
    # (started before this script existed) -- don't launch a competing
    # second instance that would race on the same output files. Just wait.
    # If that process has genuinely died (not just still working), the
    # pgrep check below will show it, and the run needs manual restart.
    if ! pgrep -f "21_compute_state_rainfall_erosivity.py nagaland|20_build_state_training_dataset.py nagaland|19_fetch_state_roads_and_negatives.py nagaland|18_run_state_pipeline.py nagaland" > /dev/null; then
      echo "[finish_pipeline] $(date) WARNING: nagaland not done and no nagaland process found running -- it may have died; launching fresh"
      launch nagaland
    fi
    sleep 60
    continue
  fi

  # Nagaland done -- Assam and Arunachal Pradesh run together.
  if ! done_csv assam; then
    running assam || launch assam
  fi
  if ! done_csv arunachal_pradesh; then
    running arunachal_pradesh || launch arunachal_pradesh
  fi
  sleep 60
done

echo "[finish_pipeline] $(date) FINISHED"
for s in nagaland assam arunachal_pradesh; do
  if done_csv "$s"; then
    echo "  $s: SUCCESS ($(wc -l < data/processed/training_dataset_${s}.csv) rows)"
  else
    echo "  $s: MISSING -- check $LOGDIR/${s}.log"
  fi
done

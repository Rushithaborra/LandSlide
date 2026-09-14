#!/bin/bash
# Sequential orchestrator for the states still outstanding, with per-state
# retry. Switched away from parallel lanes after finding that: (1) both
# remaining bottlenecks (Overpass, Open-Meteo) get MORE unreliable under
# concurrent load from the same IP, not faster in aggregate, and (2) a
# batch that exhausts retries is permanently skipped, so concurrent
# contention directly costs data completeness, not just wall-clock time.
# Order: smallest remaining workload first, to bank completions early --
# Arunachal Pradesh (193 rainfall batches, by far the largest) goes last.
set -u
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
PY=.venv/bin/python3
LOGDIR=data/interim/ner_pipeline_logs
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/_final_summary.txt"
: > "$SUMMARY"

STATES="nagaland assam arunachal_pradesh"
MAX_RETRIES=2

for state in $STATES; do
  final_csv="data/processed/training_dataset_${state}.csv"
  if [ -f "$final_csv" ]; then
    echo "$state: already has $final_csv, skipping" | tee -a "$SUMMARY"
    continue
  fi

  attempt=1
  ok=0
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    echo "############################################################"
    echo "# $state -- attempt $attempt/$MAX_RETRIES -- starting $(date)"
    echo "############################################################"
    log="$LOGDIR/${state}.log"
    : > "$log"

    step_ok=1
    echo "--- [18] terrain/landcover/soil ---" | tee -a "$log"
    $PY scripts/18_run_state_pipeline.py "$state" >> "$log" 2>&1 || step_ok=0

    if [ "$step_ok" = "1" ]; then
      echo "--- [19] roads + negatives ---" | tee -a "$log"
      $PY scripts/19_fetch_state_roads_and_negatives.py "$state" >> "$log" 2>&1 || step_ok=0
    fi

    if [ "$step_ok" = "1" ]; then
      echo "--- [21] rainfall erosivity ---" | tee -a "$log"
      $PY scripts/21_compute_state_rainfall_erosivity.py "$state" >> "$log" 2>&1 || step_ok=0
    fi

    if [ "$step_ok" = "1" ]; then
      echo "--- [20] assemble + bias check ---" | tee -a "$log"
      $PY scripts/20_build_state_training_dataset.py "$state" >> "$log" 2>&1 || step_ok=0
    fi

    if [ "$step_ok" = "1" ] && [ -f "$final_csv" ]; then
      ok=1
      break
    fi
    echo "[orchestrator] $state attempt $attempt failed, see $log"
    attempt=$((attempt + 1))
    sleep 20
  done

  if [ "$ok" = "1" ]; then
    echo "$state: SUCCESS $(date)" | tee -a "$SUMMARY"
  else
    echo "$state: FAILED after $MAX_RETRIES attempts $(date) -- see $LOGDIR/${state}.log" | tee -a "$SUMMARY"
  fi
done

echo "############################################################"
echo "# All remaining states processed. Final summary:"
cat "$SUMMARY"

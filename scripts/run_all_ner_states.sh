#!/bin/bash
# Drives scripts 18 -> 19 -> 21 -> 20 for every qualifying NER state in
# sequence. Sequential (not parallel) on purpose: states with overlapping
# bboxes (e.g. Manipur/Nagaland/Mizoram) can need the same DEM tile, and
# two processes downloading the same tile file at once would race/corrupt
# it. Continues to the next state on a failure rather than aborting the
# whole run -- a bad state gets logged, not silently dropped.
set -u
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
PY=.venv/bin/python3
LOGDIR=data/interim/ner_pipeline_logs
mkdir -p "$LOGDIR"

# Accept an explicit state list as args (for running 2 parallel lanes on
# disjoint subsets); default to the full sequential list if none given.
if [ "$#" -gt 0 ]; then
  STATES="$*"
else
  STATES="manipur mizoram nagaland meghalaya assam arunachal_pradesh"
fi
SUMMARY="$LOGDIR/_summary_$$.txt"
: > "$SUMMARY"

for state in $STATES; do
  echo "############################################################"
  echo "# $state -- starting $(date)"
  echo "############################################################"
  log="$LOGDIR/${state}.log"
  : > "$log"

  ok=1
  echo "--- [18] terrain/landcover/soil ---" | tee -a "$log"
  $PY scripts/18_run_state_pipeline.py "$state" >> "$log" 2>&1 || ok=0

  if [ "$ok" = "1" ]; then
    echo "--- [19] roads + negatives ---" | tee -a "$log"
    $PY scripts/19_fetch_state_roads_and_negatives.py "$state" >> "$log" 2>&1 || ok=0
  fi

  if [ "$ok" = "1" ]; then
    echo "--- [21] rainfall erosivity ---" | tee -a "$log"
    $PY scripts/21_compute_state_rainfall_erosivity.py "$state" >> "$log" 2>&1 || ok=0
  fi

  if [ "$ok" = "1" ]; then
    echo "--- [20] assemble + bias check ---" | tee -a "$log"
    $PY scripts/20_build_state_training_dataset.py "$state" >> "$log" 2>&1 || ok=0
  fi

  if [ "$ok" = "1" ]; then
    echo "$state: SUCCESS $(date)" | tee -a "$SUMMARY"
  else
    echo "$state: FAILED $(date) -- see $log" | tee -a "$SUMMARY"
  fi
done

echo "############################################################"
echo "# All states processed. Summary:"
cat "$SUMMARY"

#!/bin/bash
# Runs the NER zone pipeline (18 -> 19 -> 21 -> 23) for one or more states,
# ONE STATE AT A TIME (Open-Meteo throttles when rainfall runs overlap).
#
# usage (from the repo root, next to scripts/):   bash run_states.sh arunachal_pradesh assam
#
# Each step retries once -- on Windows, "Application Control policy blocked
# this file" DLL errors are often transient. Steps 18/19 skip work whose
# outputs already exist on disk, so re-running after a crash is safe, and
# script 21 caches every Open-Meteo batch, so it resumes instead of restarting.
cd "$(dirname "$0")" || exit 1
export PYTHONUNBUFFERED=1

if   [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python3 ];        then PY=.venv/bin/python3
else echo "No .venv found -- create it first (see the prompt's setup section)"; exit 1; fi

declare -A SCRIPT=(
  [18]=18_run_state_pipeline.py
  [19]=19_fetch_state_roads_and_negatives.py
  [21]=21_compute_state_rainfall_erosivity.py
  [23]=23_generate_state_zone_predictions.py
)
LOGDIR=data/interim/ner_pipeline_logs
mkdir -p "$LOGDIR"

for state in "$@"; do
  log="$LOGDIR/${state}_$(date +%Y%m%d_%H%M%S).log"
  echo "############ $state -- starting $(date) -- log: $log"
  ok=1
  for n in 18 19 21 23; do
    for attempt in 1 2; do
      echo "=== [$n] $state attempt $attempt $(date +%H:%M:%S) ===" | tee -a "$log"
      $PY "scripts/${SCRIPT[$n]}" "$state" 2>&1 | tee -a "$log"
      # tee masks python's exit code, so read it from PIPESTATUS
      rc=${PIPESTATUS[0]}
      if [ "$rc" = "0" ]; then break; fi
      echo "=== [$n] $state FAILED (attempt $attempt) ===" | tee -a "$log"
      if [ "$attempt" = "2" ]; then ok=0; fi
      sleep 5
    done
    [ "$ok" = "0" ] && break
  done
  if [ "$ok" = "1" ]; then echo "$state: DONE -> outputs/gis/${state}_road_susceptibility.geojson" | tee -a "$log"
  else echo "$state: FAILED -- see $log (continuing with the next state)" | tee -a "$log"; fi
done

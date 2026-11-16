#!/usr/bin/env bash
# Commit and push one screening study at :00 and :30 UTC until its run finishes.
#   tools/screening_push.sh health20 1440 [--now]     (math15 1080 for Phase 2)
# Each slot: analyze each batch -> verify each batch -> <study>_report.py -> commit ONLY
# pilot3_screening/<study>/, pilot3_design/<study>/ and logs/<study>.log -> push (3 retries, never
# force). A failed push sets last_error in STATUS.json; the run keeps going.
# --now pushes once immediately (the "right after launch" push). After the run is FINISHED, one last
# slot is pushed as "<study>: final" and the loop exits.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STUDY="$1"; TOTAL="$2"; NOW="${3:-}"
cd "$ROOT"
SCR="pilot3_screening/$STUDY"
PATHS=("$SCR" "pilot3_design/$STUDY" "logs/$STUDY.log")

status() { python3 -c "import json,sys;print(json.load(open('$SCR/STATUS.json')).get(sys.argv[1]))" "$1" 2>/dev/null; }

slot() {
  local final="${1:-}"
  for B in "$SCR"/batch*/; do
    B=${B%/}
    [[ -s "$B/results/generations.jsonl" ]] || continue
    (cd pilot && python3 run_pilot.py analyze --config "$ROOT/$B/config.json" --out "$ROOT/$B/results" >/dev/null 2>&1) \
      || echo "push: analyze failed for $B"
    python3 tools/verify_results.py --results "$B/results" --config "$B/config.json" --quiet >/dev/null 2>&1
  done
  python3 "tools/${STUDY}_report.py" || echo "push: report failed"
  local msg
  if [[ -n "$final" ]]; then msg="$STUDY: final"
  else msg="$STUDY: $(status answers_done)/$TOTAL answers, $(status stage)"; fi
  git add -- "${PATHS[@]}"
  if git diff --cached --quiet -- "${PATHS[@]}"; then
    echo "push: nothing new ($(date -u +%H:%M) UTC)"; return 0
  fi
  git commit -q -m "$msg" -- "${PATHS[@]}" || { echo "push: commit failed"; return 1; }
  local i
  for i in 1 2 3; do
    if git push -q origin HEAD 2>/dev/null; then
      echo "push: $(date -u +%H:%M) UTC pushed $(git rev-parse --short HEAD): $msg"
      [[ "$(status last_error)" == push* ]] && python3 "tools/${STUDY}_report.py" --last-error "" >/dev/null
      return 0
    fi
    git pull -q --rebase --autostash origin "$(git rev-parse --abbrev-ref HEAD)" 2>/dev/null
    sleep 20
  done
  python3 "tools/${STUDY}_report.py" --last-error "push failed 3 times at $(date -u +%Y-%m-%dT%H:%M:%SZ); commit kept locally" >/dev/null
  echo "push: FAILED 3 times; last_error set in STATUS.json"
}

[[ "$NOW" == "--now" ]] && slot
next=$(( ($(date -u +%s) / 1800 + 1) * 1800 ))
while true; do
  sleep 60
  if grep -q "^=== .* FINISHED $STUDY" "logs/$STUDY.log" 2>/dev/null; then
    slot final; echo "push: final pushed, loop exits"; exit 0
  fi
  if (( $(date -u +%s) >= next )); then
    slot; next=$(( ($(date -u +%s) / 1800 + 1) * 1800 ))
  fi
done

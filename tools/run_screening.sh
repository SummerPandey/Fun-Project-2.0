#!/usr/bin/env bash
# Run the screening batches for one study (health20 or math15), each batch through:
#   generate (one model per process) -> judge -> correct -> judge -> analyze -> sample
# Capability is skipped (measured in Pilot 2 with the same weights). Resumable: re-running skips
# answers already on disk. Stage markers ("=== <time> <batch> stage <name>") are what
# the report scripts read to show the current stage.
#
#   nohup tools/run_screening.sh health20 batchA batchB >> logs/health20.log 2>&1 &
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STUDY="$1"; shift
cd "$ROOT/pilot"
for B in "$@"; do
  CFG="$ROOT/pilot3_screening/$STUDY/$B/config.json"
  OUT="$ROOT/pilot3_screening/$STUDY/$B/results"
  mark() { echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) $B stage $1"; }
  MODELS=$(python3 -c "import json,sys;print(' '.join(m['name'] for m in json.load(open(sys.argv[1]))['models']))" "$CFG")
  for m in $MODELS; do
    mark "generate $m"
    python3 run_pilot.py generate --config "$CFG" --models "$m" --out "$OUT"
  done
  mark judge;   python3 run_pilot.py judge   --config "$CFG" --out "$OUT"
  mark correct; python3 run_pilot.py correct --config "$CFG" --out "$OUT"
  mark judge2;  python3 run_pilot.py judge   --config "$CFG" --out "$OUT"
  mark analyze; python3 run_pilot.py analyze --config "$CFG" --out "$OUT"
  mark sample;  python3 run_pilot.py sample  --config "$CFG" --out "$OUT"
  mark "done"
done
echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) FINISHED $STUDY"

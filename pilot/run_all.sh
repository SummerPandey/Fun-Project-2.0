#!/usr/bin/env bash
# Pilot 2: run every stage with one model per process (vLLM does not always free GPU memory
# between models in one process). Resumable: re-running skips answers already on disk.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-results}"
MODELS=$(python3 -c "import json;print(' '.join(m['name'] for m in json.load(open('config.json'))['models']))")
for m in $MODELS; do
  python3 run_pilot.py generate   --models "$m" --out "$OUT"
  python3 run_pilot.py capability --models "$m" --out "$OUT"
done
python3 run_pilot.py judge   --out "$OUT"   # judge runs alone on the GPU, after all six models
python3 run_pilot.py analyze --out "$OUT"
python3 run_pilot.py sample  --out "$OUT"
